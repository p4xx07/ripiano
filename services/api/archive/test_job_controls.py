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


def _doc(owner, title, status, **values):
    from archive.models import Document
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path=f"originals/aa/{title}.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10, status=status, **values)


@pytest.mark.django_db
def test_queued_document_can_be_cancelled_and_the_worker_then_skips_it():
    from archive.job_views import CANCELLED_PROCESSING
    from archive.models import Document, ProcessingClaim
    from archive.tasks import process_document

    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    stranger = get_user_model().objects.create_user("stranger", password="secure-password-2")
    queued = _doc(owner, "queued", Document.Status.PENDING)
    running = _doc(owner, "running", Document.Status.PROCESSING, processing_started_at=timezone.now())
    ProcessingClaim.objects.create(document=running)  # a worker is on it right now
    client = Client()
    client.force_login(stranger)
    assert client.post(f"/api/documents/{queued.id}/cancel-processing").status_code == 404
    client.force_login(owner)
    response = client.post(f"/api/documents/{queued.id}/cancel-processing")
    assert response.status_code == 200 and response.json()["error"] == CANCELLED_PROCESSING
    queued.refresh_from_db()
    assert queued.status == Document.Status.FAILED
    with patch("archive.tasks.subprocess.run") as ocr:
        process_document(str(queued.id))  # a task already in the queue finds nothing to do
    ocr.assert_not_called()
    assert client.post(f"/api/documents/{queued.id}/cancel-processing").status_code == 409
    refused = client.post(f"/api/documents/{running.id}/cancel-processing")
    assert refused.status_code == 409 and "midway" in refused.json()["error"]
    with patch("archive.tasks.process_document.delay"):
        assert client.post(f"/api/documents/{queued.id}/retry").status_code == 202  # retry works as for any failure


@pytest.mark.django_db
def test_jobs_overview_lists_only_my_waiting_and_failed_work():
    from archive.models import Document, FilingModel, ProcessingClaim, PurgeJob, Workflow, WorkflowRun

    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    stranger = get_user_model().objects.create_user("stranger", password="secure-password-2")
    _doc(owner, "waiting", Document.Status.PENDING)
    ProcessingClaim.objects.create(document=_doc(owner, "busy", Document.Status.PROCESSING, processing_started_at=timezone.now()))
    failed = _doc(owner, "broken", Document.Status.FAILED, error="OCR failed")
    _doc(owner, "fine", Document.Status.READY)
    _doc(owner, "binned", Document.Status.FAILED, trashed_at=timezone.now())
    _doc(stranger, "theirs", Document.Status.FAILED)
    PurgeJob.objects.create(owner=owner, document_id="00000000-0000-0000-0000-000000000001", status=PurgeJob.Status.FAILED, error="disk")
    PurgeJob.objects.create(owner=owner, document_id="00000000-0000-0000-0000-000000000002", status=PurgeJob.Status.COMPLETE)
    FilingModel.objects.create(owner=owner, status=FilingModel.Status.FAILED, error="worker down")
    flow = Workflow.objects.create(owner=owner, name="Notify", trigger=Workflow.Trigger.ADDED)
    WorkflowRun.objects.create(workflow=flow, document=failed, trigger="added", status=WorkflowRun.Status.FAILED, detail="webhook refused (500)")

    client = Client()
    assert client.get("/api/jobs").status_code == 401
    client.force_login(owner)
    body = client.get("/api/jobs").json()
    assert body["documents_waiting"]["total"] == 2
    assert [(item["title"], item["can_cancel"]) for item in body["documents_waiting"]["items"]] == [("waiting", True), ("busy", False)]
    assert body["documents_failed"]["total"] == 1 and body["documents_failed"]["items"][0]["error"] == "OCR failed"
    assert [(job["status"], job["can_retry"]) for job in body["purges"]] == [("failed", True)]
    assert body["training"] == {**body["training"], "status": "failed", "can_retry": True}
    assert body["workflow_failures"][0]["detail"] == "webhook refused (500)"
    client.force_login(stranger)
    other = client.get("/api/jobs").json()
    assert other["documents_failed"]["total"] == 1 and other["purges"] == [] and other["training"] is None
