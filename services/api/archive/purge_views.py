"""Owner-only permanent deletion requests and cleanup status."""

import logging

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Document, PhysicalCopy, PurgeJob
from .tasks import purge_document

logger = logging.getLogger(__name__)


def _unauthorized(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _job_json(job):
    return {
        "id": str(job.id),
        "document_id": str(job.document_id),
        "title": job.title,
        "status": job.status,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def _enqueue(job):
    try:
        purge_document.delay(str(job.id))
    except Exception:
        logger.exception("Permanent deletion queue unavailable; pending job will be reconciled: %s", job.id)


@require_http_methods(["POST"])
def purge_document_request(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(
            pk=document_id, owner=request.user, trashed_at__isnull=False,
        ).first()
        if document is None:
            return JsonResponse({"error": "Document not found in Trash"}, status=404)
        job = PurgeJob.objects.create(
            owner=request.user, document_id=document.id, title=document.title,
            original_path=document.original_path, archive_path=document.archive_path,
            original_sha256=document.original_sha256,
        )
        # Physical copies deliberately protect their parent from implicit deletion.
        # A confirmed purge explicitly retires their stickers and movement history.
        PhysicalCopy.objects.filter(document=document).delete()
        document.delete()
    _enqueue(job)
    return JsonResponse(_job_json(job), status=202)


@require_http_methods(["GET"])
def purge_jobs(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    own_jobs = PurgeJob.objects.filter(owner=request.user)
    incomplete = list(own_jobs.exclude(status=PurgeJob.Status.COMPLETE).order_by("-created_at")[:50])
    recent_complete = list(own_jobs.filter(status=PurgeJob.Status.COMPLETE).order_by("-created_at")[:10])
    return JsonResponse({"jobs": [_job_json(job) for job in incomplete + recent_complete]})


@require_http_methods(["POST"])
def retry_purge_job(request, job_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    with transaction.atomic():
        job = PurgeJob.objects.select_for_update().filter(pk=job_id, owner=request.user).first()
        if job is None:
            return JsonResponse({"error": "Deletion job not found"}, status=404)
        if job.status != PurgeJob.Status.FAILED:
            return JsonResponse({"error": "Only failed file cleanup can be retried"}, status=409)
        job.status = PurgeJob.Status.PENDING
        job.error = ""
        job.started_at = None
        job.save(update_fields=["status", "error", "started_at"])
    _enqueue(job)
    return JsonResponse(_job_json(job), status=202)
