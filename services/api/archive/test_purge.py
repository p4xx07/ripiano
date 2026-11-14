import fcntl
import hashlib
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from archive.backup import create_snapshot, verify_snapshot
from archive.models import Document, DocumentNote, PhysicalCopy, PurgeJob
from archive.tasks import purge_document, reconcile_purge_jobs


def make_document(owner, media, name="sample", *, original_bytes=b"preserved original"):
    original = media / "originals" / f"{name}.pdf"
    archive = media / "archive" / f"{name}.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(original_bytes)
    archive.write_bytes(b"searchable archive")
    document = Document.objects.create(
        owner=owner, title=name, original_name=f"{name}.pdf",
        original_path=f"originals/{name}.pdf", archive_path=f"archive/{name}.pdf",
        original_mime="application/pdf", original_sha256=hashlib.sha256(original_bytes).hexdigest(),
        original_size=len(original_bytes), status=Document.Status.READY,
    )
    return document, original, archive


@pytest.mark.django_db
def test_purge_waits_for_snapshot_then_removes_live_files_and_linked_data(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    media, backups = tmp_path / "media", tmp_path / "backups"
    document, original, archive = make_document(owner, media)
    note = DocumentNote.objects.create(document=document, author=owner, body="Private note")
    copy = PhysicalCopy.objects.create(document=document, sticker_code="R-PURGE123")
    client = Client()
    path = f"/api/documents/{document.id}/purge"

    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backups):
        assert client.post(path).status_code == 401
        client.force_login(other)
        assert client.post(path).status_code == 404
        client.force_login(owner)
        assert client.post(path).status_code == 404  # Active documents must enter Trash first.
        with patch("archive.backup._database_command", side_effect=lambda command, dump, **kwargs: dump.write_bytes(b"database")):
            snapshot = create_snapshot()
        assert client.post(f"/api/documents/{document.id}/trash").status_code == 200
        with patch("archive.purge_views.purge_document.delay") as enqueue:
            response = client.post(path)
        assert response.status_code == 202
        job_id = response.json()["id"]
        enqueue.assert_called_once_with(job_id)
        assert not Document.objects.filter(pk=document.id).exists()
        assert not DocumentNote.objects.filter(pk=note.id).exists()
        assert not PhysicalCopy.objects.filter(pk=copy.id).exists()
        assert client.get(f"/api/stickers/{copy.sticker_code}").status_code == 404
        assert original.exists() and archive.exists()
        assert client.get("/api/purge-jobs").json()["jobs"][0]["status"] == "pending"
        client.force_login(other)
        assert client.get("/api/purge-jobs").json()["jobs"] == []
        client.force_login(owner)

        # The backup copied the files before its lock was released. A new cleanup waits.
        with (backups / ".lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            purge_document(job_id)
            assert original.exists() and archive.exists()
            assert PurgeJob.objects.get(pk=job_id).status == PurgeJob.Status.PENDING
            fcntl.flock(lock, fcntl.LOCK_UN)
        purge_document(job_id)
        assert not original.exists() and not archive.exists()
        job = PurgeJob.objects.get(pk=job_id)
        assert job.status == PurgeJob.Status.COMPLETE
        assert not job.title and not job.original_path and not job.archive_path and not job.original_sha256
        assert (snapshot / "media/originals/sample.pdf").read_bytes() == b"preserved original"
        assert verify_snapshot(snapshot)["database"]["sha256"]
        with patch("archive.backup._database_command", side_effect=lambda command, dump, **kwargs: dump.write_bytes(b"database")):
            newer = create_snapshot()
        assert newer != snapshot and verify_snapshot(newer)["files"] == []


@pytest.mark.django_db
def test_failed_purge_keeps_files_and_can_be_retried(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    media, backups = tmp_path / "media", tmp_path / "backups"
    document, original, archive = make_document(owner, media, original_bytes=b"expected")
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backups):
        assert client.post(f"/api/documents/{document.id}/trash").status_code == 200
        with patch("archive.purge_views.purge_document.delay", side_effect=RuntimeError("Broker unavailable")):
            response = client.post(f"/api/documents/{document.id}/purge")
        assert response.status_code == 202
        job_id = response.json()["id"]
        with patch("archive.tasks.purge_document.delay") as enqueue:
            reconcile_purge_jobs()
        enqueue.assert_called_once_with(job_id)
        original.write_bytes(b"unexpected change")
        purge_document(job_id)
        job = PurgeJob.objects.get(pk=job_id)
        assert job.status == PurgeJob.Status.FAILED
        assert "checksum" in job.error
        assert original.exists() and archive.exists()
        with patch("archive.purge_views.purge_document.delay"):
            assert client.post(f"/api/purge-jobs/{job_id}/retry").status_code == 202
        original.write_bytes(b"expected")
        purge_document(job_id)
        assert PurgeJob.objects.get(pk=job_id).status == PurgeJob.Status.COMPLETE
        assert not original.exists() and not archive.exists()
        assert client.post(f"/api/purge-jobs/{job_id}/retry").status_code == 409


@pytest.mark.django_db
def test_purge_rejects_unsafe_media_paths(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    media, backups = tmp_path / "media", tmp_path / "backups"
    media.mkdir()
    document = Document.objects.create(
        owner=owner, title="Unsafe", original_name="unsafe.pdf",
        original_path="originals/../../outside.pdf", original_mime="application/pdf",
        original_sha256=hashlib.sha256(b"outside").hexdigest(), original_size=7,
        status=Document.Status.READY,
    )
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backups):
        assert client.post(f"/api/documents/{document.id}/trash").status_code == 200
        with patch("archive.purge_views.purge_document.delay"):
            job_id = client.post(f"/api/documents/{document.id}/purge").json()["id"]
        purge_document(job_id)
        assert outside.read_bytes() == b"outside"
        assert PurgeJob.objects.get(pk=job_id).status == PurgeJob.Status.FAILED

@pytest.mark.django_db
def test_storage_permission_failure_is_visible_and_retryable(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    media, backups = tmp_path / "media", tmp_path / "backups"
    document, original, archive = make_document(owner, media, "permissions")
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backups):
        assert client.post(f"/api/documents/{document.id}/trash").status_code == 200
        with patch("archive.purge_views.purge_document.delay"):
            job_id = client.post(f"/api/documents/{document.id}/purge").json()["id"]
        with patch("archive.tasks.backup_media_lock", side_effect=PermissionError("Backup volume is not writable")):
            purge_document(job_id)
        job = PurgeJob.objects.get(pk=job_id)
        assert job.status == PurgeJob.Status.FAILED
        assert "not writable" in job.error
        assert original.exists() and archive.exists()
        assert client.get("/api/purge-jobs").json()["jobs"][0]["status"] == "failed"
        with patch("archive.purge_views.purge_document.delay"):
            assert client.post(f"/api/purge-jobs/{job_id}/retry").status_code == 202
        purge_document(job_id)
        assert PurgeJob.objects.get(pk=job_id).status == PurgeJob.Status.COMPLETE
        assert not original.exists() and not archive.exists()
