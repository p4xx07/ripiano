"""Queued jobs can be cancelled before workers claim them and retried with an audit trail."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.models import BackupRun, BrowseExportRun
from archive.tasks import backup_archive, build_browse_export, reconcile_backup_runs


@pytest.mark.django_db
def test_backup_cancel_is_claim_safe_and_retry_keeps_history():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    user = get_user_model().objects.create_user("user", password="secure-password-2")
    run = BackupRun.objects.create(trigger="manual")
    client = Client()
    client.force_login(user)
    assert client.post(f"/api/backups/{run.id}/cancel").status_code == 403
    client.force_login(owner)
    assert client.get("/api/backups").json()["runs"][0]["can_cancel"] is True
    cancelled = client.post(f"/api/backups/{run.id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == BackupRun.Status.CANCELLED
    with patch("archive.tasks.create_snapshot") as snapshot:
        backup_archive(str(run.id))
    snapshot.assert_not_called()
    assert client.post(f"/api/backups/{run.id}/cancel").status_code == 409
    with patch("archive.job_views.backup_archive.delay") as enqueue:
        response = client.post(f"/api/backups/{run.id}/retry")
    assert response.status_code == 202
    new = BackupRun.objects.get(pk=response.json()["id"])
    assert new.retry_of_id == run.id and new.status == BackupRun.Status.PENDING
    enqueue.assert_called_once_with(str(new.id))
    assert client.post(f"/api/backups/{run.id}/retry").status_code == 409
    listed = client.get("/api/backups").json()["runs"]
    assert listed[0]["can_cancel"] is True and listed[1]["can_retry"] is False
    with patch("archive.tasks.create_snapshot", return_value=SimpleNamespace(name="verified-snapshot")):
        backup_archive(str(new.id))
    new.refresh_from_db()
    assert new.status == BackupRun.Status.COMPLETE and new.snapshot_name == "verified-snapshot"
    assert client.post(f"/api/backups/{new.id}/cancel").status_code == 409


@pytest.mark.django_db
def test_failed_backup_retry_and_queue_outage_are_visible():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)
    failed = BackupRun.objects.create(status=BackupRun.Status.FAILED, error="storage unavailable")
    with patch("archive.job_views.backup_archive.delay", side_effect=ConnectionError("broker down")):
        result = client.post(f"/api/backups/{failed.id}/retry")
    assert result.status_code == 503
    retry = BackupRun.objects.get(retry_of=failed)
    assert retry.status == BackupRun.Status.FAILED and retry.error == "Backup queue unavailable"
    assert client.get("/api/backups").json()["runs"][1]["can_retry"] is False


@pytest.mark.django_db
def test_running_jobs_cannot_be_cancelled_or_retried():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)
    backup = BackupRun.objects.create(status=BackupRun.Status.RUNNING, started_at=timezone.now())
    browse = BrowseExportRun.objects.create(owner=owner, status=BrowseExportRun.Status.RUNNING, started_at=timezone.now())
    for path in (f"/api/backups/{backup.id}", f"/api/browse-exports/{browse.id}"):
        assert client.post(f"{path}/cancel").status_code == 409
        assert client.post(f"{path}/retry").status_code == 409
    backup.refresh_from_db()
    browse.refresh_from_db()
    assert backup.status == BackupRun.Status.RUNNING
    assert browse.status == BrowseExportRun.Status.RUNNING


@pytest.mark.django_db
def test_browse_cancel_and_retry_keep_owner_boundary_and_one_active_copy():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    other = get_user_model().objects.create_superuser("other", password="secure-password-2")
    run = BrowseExportRun.objects.create(owner=owner)
    client = Client()
    client.force_login(other)
    assert client.post(f"/api/browse-exports/{run.id}/cancel").status_code == 404
    assert client.post(f"/api/browse-exports/{run.id}/retry").status_code == 404
    client.force_login(owner)
    assert client.get("/api/browse-exports").json()["runs"][0]["can_cancel"] is True
    assert client.post(f"/api/browse-exports/{run.id}/cancel").status_code == 200
    with patch("archive.tasks.build_browse_tree") as build:
        build_browse_export(str(run.id))
    build.assert_not_called()
    active = BrowseExportRun.objects.create(owner=owner)
    assert client.post(f"/api/browse-exports/{run.id}/retry").status_code == 409
    active.status = BrowseExportRun.Status.FAILED
    active.save(update_fields=["status"])
    with patch("archive.job_views.build_browse_export.delay") as enqueue:
        result = client.post(f"/api/browse-exports/{run.id}/retry")
    assert result.status_code == 202
    retry = BrowseExportRun.objects.get(pk=result.json()["id"])
    assert retry.owner == owner and retry.retry_of_id == run.id
    enqueue.assert_called_once_with(str(retry.id))
    assert client.post(f"/api/browse-exports/{run.id}/retry").status_code == 409
    listed = client.get("/api/browse-exports").json()["runs"]
    assert listed[0]["can_cancel"] is True and listed[-1]["can_retry"] is False
    with patch("archive.tasks.build_browse_tree", return_value=("verified-folder", 2)):
        with patch("archive.tasks.prune_old_browse_trees"):
            build_browse_export(str(retry.id))
    retry.refresh_from_db()
    assert retry.status == BrowseExportRun.Status.COMPLETE and retry.document_count == 2


@pytest.mark.django_db
def test_reconcile_requeues_only_old_pending_backups():
    old = BackupRun.objects.create(trigger="manual")
    BackupRun.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(minutes=3))
    BackupRun.objects.create(trigger="manual")
    BackupRun.objects.create(status=BackupRun.Status.CANCELLED)
    stale = BackupRun.objects.create(status=BackupRun.Status.RUNNING, started_at=timezone.now() - timedelta(hours=8))
    with patch("archive.tasks.backup_archive.delay") as enqueue:
        reconcile_backup_runs()
    enqueue.assert_called_once_with(str(old.id))
    stale.refresh_from_db()
    assert stale.status == BackupRun.Status.FAILED and stale.completed_at is not None
