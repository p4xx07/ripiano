"""Explicit controls for queued and failed archive maintenance jobs."""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import BackupRun, BrowseExportRun
from .tasks import backup_archive, build_browse_export

logger = logging.getLogger(__name__)


def _owner_required(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"error": "Owner access required"}, status=403)
    return None


@require_http_methods(["POST"])
def backup_run_action(request, run_id, action):
    denied = _owner_required(request)
    if denied:
        return denied
    if action not in {"cancel", "retry"}:
        return JsonResponse({"error": "Unknown action"}, status=404)
    with transaction.atomic():
        run = BackupRun.objects.select_for_update().filter(pk=run_id).first()
        if run is None:
            return JsonResponse({"error": "Backup run not found"}, status=404)
        if action == "cancel":
            if run.status != BackupRun.Status.PENDING:
                return JsonResponse({"error": "Only a queued backup can be cancelled"}, status=409)
            run.status = BackupRun.Status.CANCELLED
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at"])
            return JsonResponse({"id": str(run.id), "status": run.status})
        if run.status not in {BackupRun.Status.FAILED, BackupRun.Status.CANCELLED}:
            return JsonResponse({"error": "Only a failed or cancelled backup can be retried"}, status=409)
        if BackupRun.objects.filter(retry_of=run).exists():
            return JsonResponse({"error": "This backup already has a retry"}, status=409)
        retry = BackupRun.objects.create(trigger="retry", retry_of=run)
    try:
        backup_archive.delay(str(retry.id))
    except Exception:
        logger.exception("Backup queue unavailable: %s", retry.id)
        BackupRun.objects.filter(pk=retry.id, status=BackupRun.Status.PENDING).update(status=BackupRun.Status.FAILED, error="Backup queue unavailable", completed_at=timezone.now())
        return JsonResponse({"error": "Backup queue unavailable", "id": str(retry.id)}, status=503)
    return JsonResponse({"id": str(retry.id), "status": retry.status, "retry_of": str(run.id)}, status=202)


@require_http_methods(["POST"])
def browse_run_action(request, run_id, action):
    denied = _owner_required(request)
    if denied:
        return denied
    if action not in {"cancel", "retry"}:
        return JsonResponse({"error": "Unknown action"}, status=404)
    with transaction.atomic():
        # The normal start endpoint uses the same owner lock to enforce one active copy.
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        run = BrowseExportRun.objects.select_for_update().filter(pk=run_id, owner=request.user).first()
        if run is None:
            return JsonResponse({"error": "NAS browse copy not found"}, status=404)
        if action == "cancel":
            if run.status != BrowseExportRun.Status.PENDING:
                return JsonResponse({"error": "Only a queued NAS browse copy can be cancelled"}, status=409)
            run.status = BrowseExportRun.Status.CANCELLED
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at"])
            return JsonResponse({"id": str(run.id), "status": run.status})
        if run.status not in {BrowseExportRun.Status.FAILED, BrowseExportRun.Status.CANCELLED}:
            return JsonResponse({"error": "Only a failed or cancelled NAS browse copy can be retried"}, status=409)
        if BrowseExportRun.objects.filter(retry_of=run).exists():
            return JsonResponse({"error": "This NAS browse copy already has a retry"}, status=409)
        if BrowseExportRun.objects.filter(owner=request.user, status__in=[BrowseExportRun.Status.PENDING, BrowseExportRun.Status.RUNNING]).exists():
            return JsonResponse({"error": "A NAS browse copy is already running"}, status=409)
        retry = BrowseExportRun.objects.create(owner=request.user, retry_of=run)
    try:
        build_browse_export.delay(str(retry.id))
    except Exception:
        logger.exception("NAS browse copy queue unavailable: %s", retry.id)
        BrowseExportRun.objects.filter(pk=retry.id, status=BrowseExportRun.Status.PENDING).update(status=BrowseExportRun.Status.FAILED, error="Browse export queue unavailable", completed_at=timezone.now())
        return JsonResponse({"error": "Browse export queue unavailable", "id": str(retry.id)}, status=503)
    return JsonResponse({"id": str(retry.id), "status": retry.status, "retry_of": str(run.id)}, status=202)
