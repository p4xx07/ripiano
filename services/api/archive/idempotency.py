"""Replay protection for POSTs: the same ``Idempotency-Key`` from the same person on the same path within ten
minutes gets the first answer again instead of doing the work twice (round-10 review, M3).

The web app gives up waiting after 20 seconds while the server usually finishes the request; the retry then carries
the same key. Applies to every POST under ``/api/`` from a signed-in person (or API token) that sends the header:

- the key is any 1-64 printable ASCII characters (the app sends a UUID); anything else answers 400;
- only a successful (2xx) JSON answer is kept, encrypted, for ten minutes, and replayed with ``Idempotent-Replay: true``;
  a refused or failed request keeps nothing, so the retry simply runs;
- while the first request is still running, the second waits for it (up to 15 seconds) and then gets its answer, or
  409 if it is still not done;
- a key is tied to the person and the path: another person's identical key is unrelated, and the same key on another
  path answers 422 instead of replaying anything.

Requests without the header are untouched. Records live in one small table (a unique row per person and key is what
makes two simultaneous requests safe across the web processes) and are deleted after ten minutes.
"""

import logging
import re
import time
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from .models import IdempotencyRecord

logger = logging.getLogger(__name__)
HEADER = "Idempotency-Key"
KEEP = timedelta(minutes=10)
# A request that has not answered after this long is gone (the web server stops a request after 60 seconds).
ABANDONED = timedelta(seconds=90)
WAIT_SECONDS = 15
POLL_SECONDS = 0.25
MAX_BODY = 256 * 1024
_KEY = re.compile(r"[\x21-\x7e]{1,64}")
IN_PROGRESS = "This request is still being handled. Check whether it was saved before trying again"
OTHER_REQUEST = "This Idempotency-Key was already used for a different request"
BAD_KEY = "Idempotency-Key must be 1 to 64 letters, digits, or symbols without spaces"


def _replay(record):
    from .mail import decrypt_secret

    response = HttpResponse(decrypt_secret(record.body), status=record.status, content_type="application/json")
    response["Idempotent-Replay"] = "true"
    return response


def _claim(user, key, path):
    """Return (record, None) when this request may run, or (None, response) when it must not."""
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        now = timezone.now()
        IdempotencyRecord.objects.filter(created_at__lt=now - KEEP).delete()
        IdempotencyRecord.objects.filter(user=user, key=key, status__isnull=True, created_at__lt=now - ABANDONED).delete()
        try:
            with transaction.atomic():
                return IdempotencyRecord.objects.create(user=user, key=key, path=path), None
        except IntegrityError:
            pass
        record = IdempotencyRecord.objects.filter(user=user, key=key).first()
        if record is None:
            continue  # The first request just failed and released the key: this one runs.
        if record.path != path:
            return None, JsonResponse({"error": OTHER_REQUEST}, status=422)
        if record.status is not None:
            return None, _replay(record)
        if time.monotonic() >= deadline:
            return None, JsonResponse({"error": IN_PROGRESS}, status=409)
        time.sleep(POLL_SECONDS)


class IdempotencyMiddleware:
    """See the module docstring. Placed after authentication; acts in ``process_view``, so after the CSRF check."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        record = getattr(request, "_idempotency_record", None)
        if record is None:
            return response
        try:
            body = response.content if not getattr(response, "streaming", False) else None
            if (body is not None and 200 <= response.status_code < 300 and len(body) <= MAX_BODY
                    and response.get("Content-Type", "").startswith("application/json")):
                from .mail import encrypt_secret

                IdempotencyRecord.objects.filter(pk=record.pk).update(status=response.status_code, body=encrypt_secret(body.decode("utf-8") or " "))
            else:
                IdempotencyRecord.objects.filter(pk=record.pk).delete()
        except Exception:  # noqa: BLE001 - the request itself succeeded; losing the replay record must not fail it
            logger.warning("Could not record the answer for an idempotency key", exc_info=True)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        key = request.headers.get(HEADER)
        if key is None or request.method != "POST" or not request.path.startswith("/api/") or not request.user.is_authenticated:
            return None
        if not _KEY.fullmatch(key):
            return JsonResponse({"error": BAD_KEY}, status=400)
        record, response = _claim(request.user, key, request.path[:300])
        if record is not None:
            request._idempotency_record = record
        return response

    def process_exception(self, request, exception):
        record = getattr(request, "_idempotency_record", None)
        if record is not None:
            request._idempotency_record = None
            try:
                IdempotencyRecord.objects.filter(pk=record.pk).delete()
            except Exception:  # noqa: BLE001 - e.g. the database went away; the record expires by itself
                logger.warning("Could not release an idempotency key", exc_info=True)
        return None
