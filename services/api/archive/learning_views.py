"""Status and retraining of a person's learned filing model."""

import json
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .auto_filing import AUTO_THRESHOLD, MIN_HELD_OUT_PRECISION, MIN_TESTED_SUGGESTIONS
from .learning import THRESHOLD, request_training, status_of
from .models import AutoFilingPolicy, FilingModel

logger = logging.getLogger(__name__)


def _json(model, auto_apply=False):
    status, error = status_of(model)
    if model is None:
        return {"status": status, "trained_at": None, "examples": 0, "metrics": {}, "threshold": THRESHOLD, "error": "",
                "auto_apply": auto_apply, "auto_threshold": AUTO_THRESHOLD, "auto_min_precision": MIN_HELD_OUT_PRECISION,
                "auto_min_tested": MIN_TESTED_SUGGESTIONS}
    return {
        "status": status, "trained_at": model.trained_at.isoformat() if model.trained_at else None,
        "examples": model.examples, "metrics": model.metrics, "threshold": THRESHOLD, "error": error,
        "auto_apply": auto_apply, "auto_threshold": AUTO_THRESHOLD, "auto_min_precision": MIN_HELD_OUT_PRECISION,
        "auto_min_tested": MIN_TESTED_SUGGESTIONS,
    }


def _enqueue(owner_id):
    from .tasks import train_filing_model

    try:
        train_filing_model.delay(owner_id)
    except Exception:
        logger.exception("Could not queue filing-model training for owner %s", owner_id)
        FilingModel.objects.filter(owner_id=owner_id, status=FilingModel.Status.QUEUED).update(
            status=FilingModel.Status.FAILED, error="Learning could not start. Check that the background worker is running.")


@require_http_methods(["GET", "POST", "PATCH"])
def filing_model(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    if request.method == "GET":
        return JsonResponse(_json(FilingModel.objects.filter(owner=request.user).first(),
                                  AutoFilingPolicy.objects.filter(owner=request.user, enabled=True).exists()))
    if request.method == "PATCH":
        try:
            body = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            body = None
        if not isinstance(body, dict) or set(body) != {"auto_apply"} or not isinstance(body["auto_apply"], bool):
            return JsonResponse({"error": "Choose whether local automatic filing is on or off"}, status=400)
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            policy, _ = AutoFilingPolicy.objects.select_for_update().get_or_create(owner=request.user)
            policy.enabled = body["auto_apply"]
            policy.save(update_fields=["enabled", "updated_at"])
        return JsonResponse(_json(FilingModel.objects.filter(owner=request.user).first(), policy.enabled))
    record, refusal = request_training(request.user.pk)
    if refusal:
        return JsonResponse({**_json(record, AutoFilingPolicy.objects.filter(owner=request.user, enabled=True).exists()),
                             "error": refusal}, status=409 if "running" in refusal else 429)
    owner_id = request.user.pk
    transaction.on_commit(lambda: _enqueue(owner_id))
    return JsonResponse(_json(record, AutoFilingPolicy.objects.filter(owner=request.user, enabled=True).exists()), status=202)
