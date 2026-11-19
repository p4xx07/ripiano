"""Owner-scoped control and status for disposable NAS browse copies."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import BrowseExportRun
from .tasks import build_browse_export


def _run_json(run):
    relative = Path("browse") / "owners" / str(run.owner_id) / "complete" / run.folder_name if run.folder_name else None
    available = bool(relative and (Path(settings.RIPIANO_BACKUP_ROOT) / relative).is_dir())
    return {
        "id": str(run.id), "status": run.status, "document_count": run.document_count,
        "folder": relative.as_posix() if available else None, "error": run.error,
        "created_at": run.created_at.isoformat(), "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "can_cancel": run.status == BrowseExportRun.Status.PENDING,
        "can_retry": run.status in {BrowseExportRun.Status.FAILED, BrowseExportRun.Status.CANCELLED} and not hasattr(run, "retry_run"),
        "retry_of": str(run.retry_of_id) if run.retry_of_id else None,
    }


@require_http_methods(["GET", "POST"])
def browse_exports(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"error": "Owner access required"}, status=403)
    if request.method == "GET":
        runs = BrowseExportRun.objects.filter(owner=request.user).select_related("retry_run")[:20]
        return JsonResponse({"runs": [_run_json(run) for run in runs]})
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        active = BrowseExportRun.objects.filter(
            owner=request.user, status__in=[BrowseExportRun.Status.PENDING, BrowseExportRun.Status.RUNNING],
        ).first()
        if active:
            return JsonResponse({"error": "A NAS browse copy is already running", "id": str(active.id)}, status=409)
        run = BrowseExportRun.objects.create(owner=request.user)
    try:
        build_browse_export.delay(str(run.id))
    except Exception:
        run.status = BrowseExportRun.Status.FAILED
        run.error = "Browse export queue unavailable"
        run.save(update_fields=["status", "error"])
        return JsonResponse({"error": run.error}, status=503)
    return JsonResponse(_run_json(run), status=202)
