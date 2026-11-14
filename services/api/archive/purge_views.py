"""Owner-only permanent deletion requests and cleanup status."""

import json
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Document, PurgeJob, TrashRetentionPolicy
from .purge import record_purge
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
        job = record_purge(document)
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


@require_http_methods(["GET", "PUT"])
def trash_retention(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "PUT":
        try:
            body = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            body = None
        if not isinstance(body, dict) or set(body) != {"enabled", "days"}:
            return JsonResponse({"error": "Provide enabled and days"}, status=400)
        enabled, days = body["enabled"], body["days"]
        if not isinstance(enabled, bool) or isinstance(days, bool) or not isinstance(days, int) or not 30 <= days <= 3650:
            return JsonResponse({"error": "Choose 30 to 3650 days"}, status=400)
        with transaction.atomic():
            policy, _ = TrashRetentionPolicy.objects.select_for_update().get_or_create(owner=request.user)
            policy.enabled = enabled
            policy.days = days
            policy.save(update_fields=["enabled", "days", "updated_at"])
    else:
        policy = TrashRetentionPolicy.objects.filter(owner=request.user).first()
    days = policy.days if policy else 90
    if request.method == "GET" and "days" in request.GET:
        raw_days = request.GET["days"]
        if len(raw_days) > 4 or not raw_days.isascii() or not raw_days.isdigit() or not 30 <= int(raw_days) <= 3650:
            return JsonResponse({"error": "Choose 30 to 3650 days"}, status=400)
        days = int(raw_days)
    cutoff = timezone.now() - timedelta(days=days)
    return JsonResponse({
        "enabled": policy.enabled if policy else False,
        "days": days,
        "eligible_count": Document.objects.filter(owner=request.user, trashed_at__lte=cutoff).count(),
        "updated_at": policy.updated_at.isoformat() if policy else None,
    })
