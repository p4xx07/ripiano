"""Opt-in age-based Trash cleanup through the same durable purge path."""

import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from archive.models import Document, PhysicalCopy, PurgeJob, TrashRetentionPolicy
from archive.tasks import purge_document, purge_expired_trash


def document(owner, media, name, trashed_days=None):
    original = media / "originals" / f"{name}.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    data = name.encode()
    original.write_bytes(data)
    item = Document.objects.create(
        owner=owner, title=name, original_name=f"{name}.pdf",
        original_path=f"originals/{name}.pdf", original_mime="application/pdf",
        original_sha256=hashlib.sha256(data).hexdigest(), original_size=len(data),
        status=Document.Status.READY,
    )
    if trashed_days is not None:
        Document.objects.filter(pk=item.pk).update(trashed_at=timezone.now() - timedelta(days=trashed_days))
    return item, original


def put_policy(client, enabled, days):
    return client.put("/api/trash-retention", json.dumps({"enabled": enabled, "days": days}), content_type="application/json")


@pytest.mark.django_db
def test_retention_is_opt_in_owner_scoped_and_uses_durable_purge(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    media, backups = tmp_path / "media", tmp_path / "backup"
    old, old_file = document(owner, media, "old", 91)
    recent, recent_file = document(owner, media, "recent", 20)
    active, active_file = document(owner, media, "active")
    foreign, foreign_file = document(other, media, "foreign", 91)
    paper = PhysicalCopy.objects.create(document=old, sticker_code="R-RETENTION1")
    client = Client()
    assert client.get("/api/trash-retention").status_code == 401
    client.force_login(owner)
    assert client.get("/api/trash-retention").json() == {
        "enabled": False, "days": 90, "eligible_count": 1, "updated_at": None,
    }
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backups):
        with patch("archive.tasks.purge_document.delay") as enqueue:
            purge_expired_trash()
            enqueue.assert_not_called()
        response = put_policy(client, True, 90)
        assert response.status_code == 200
        assert response.json()["eligible_count"] == 1
        with patch("archive.tasks.purge_document.delay", side_effect=RuntimeError("queue down")):
            purge_expired_trash()
        job = PurgeJob.objects.get(document_id=old.id)
        assert job.status == PurgeJob.Status.PENDING
        assert not Document.objects.filter(pk=old.id).exists()
        assert not PhysicalCopy.objects.filter(pk=paper.id).exists()
        assert old_file.exists()
        assert put_policy(client, False, 90).json()["enabled"] is False
        purge_document(str(job.id))
        assert not old_file.exists()
        assert all(Document.objects.filter(pk=item.pk).exists() for item in (recent, active, foreign))
        assert all(path.exists() for path in (recent_file, active_file, foreign_file))
        assert not TrashRetentionPolicy.objects.get(owner=owner).enabled
        client.force_login(other)
        assert client.get("/api/trash-retention").json()["enabled"] is False
        assert client.get("/api/purge-jobs").json()["jobs"] == []


@pytest.mark.django_db
def test_retention_validation_disable_and_age_threshold(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    media = tmp_path / "media"
    thirty_one, _ = document(owner, media, "thirty-one", 31)
    twenty_nine, _ = document(owner, media, "twenty-nine", 29)
    client = Client()
    client.force_login(owner)
    for body in ({"enabled": True, "days": 29}, {"enabled": True, "days": 3651},
                 {"enabled": True, "days": True}, {"enabled": "true", "days": 30},
                 {"enabled": True}, {"enabled": True, "days": 30, "extra": 1}):
        assert client.put("/api/trash-retention", json.dumps(body), content_type="application/json").status_code == 400
    assert client.put("/api/trash-retention", "{", content_type="application/json").status_code == 400
    assert not TrashRetentionPolicy.objects.filter(owner=owner).exists()
    assert client.get("/api/trash-retention?days=30").json()["eligible_count"] == 1
    assert client.get("/api/trash-retention?days=29").status_code == 400
    assert client.get("/api/trash-retention?days=" + "9" * 10).status_code == 400
    assert put_policy(client, True, 30).json()["eligible_count"] == 1
    assert put_policy(client, False, 30).json()["enabled"] is False
    with patch("archive.tasks.purge_document.delay") as enqueue:
        purge_expired_trash()
        enqueue.assert_not_called()
    assert Document.objects.filter(pk=thirty_one.pk).exists()
    assert Document.objects.filter(pk=twenty_nine.pk).exists()
