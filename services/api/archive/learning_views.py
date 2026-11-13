"""Status and retraining of a person's learned filing model."""

import logging

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .learning import THRESHOLD, request_training, status_of
from .models import FilingModel

logger = logging.getLogger(__name__)


def _json(model):
    status, error = status_of(model)
    if model is None:
        return {"status": status, "trained_at": None, "examples": 0, "metrics": {}, "threshold": THRESHOLD, "error": ""}
    return {
        "status": status, "trained_at": model.trained_at.isoformat() if model.trained_at else None,
        "examples": model.examples, "metrics": model.metrics, "threshold": THRESHOLD, "error": error,
    }


def _enqueue(owner_id):
    from .tasks import train_filing_model

    try:
        train_filing_model.delay(owner_id)
    except Exception:
        logger.exception("Could not queue filing-model training for owner %s", owner_id)
        FilingModel.objects.filter(owner_id=owner_id, status=FilingModel.Status.QUEUED).update(
            status=FilingModel.Status.FAILED, error="Learning could not start. Check that the background worker is running.")


@require_http_methods(["GET", "POST"])
def filing_model(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    if request.method == "GET":
        return JsonResponse(_json(FilingModel.objects.filter(owner=request.user).first()))
    record, refusal = request_training(request.user.pk)
    if refusal:
        return JsonResponse({**_json(record), "error": refusal}, status=409 if "running" in refusal else 429)
    owner_id = request.user.pk
    transaction.on_commit(lambda: _enqueue(owner_id))
    return JsonResponse(_json(record), status=202)
