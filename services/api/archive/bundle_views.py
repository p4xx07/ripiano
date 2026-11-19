"""Share several originals behind one expiring link, and email a document from Ripiano.

A bundle's ZIP is built once in the background, verifying each original while it is copied, and is then
served as a plain file. Bundles are immutable: moving a document to Trash or adding a new version revokes
every bundle containing it, and an ended link's ZIP is deleted.
"""

import hashlib
import json
import logging
import os
import re
import secrets
import unicodedata
from datetime import timedelta
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F, Q
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .export_views import _media_path
from .models import Document, DocumentEmailSend, ShareBundle

logger = logging.getLogger(__name__)
MAX_BUNDLE_DOCUMENTS = 50
MAX_BUNDLE_BYTES = 200 * 1024 * 1024
EMAIL_RECIPIENTS_PER_HOUR = 30
STALE_EMAIL_MINUTES = 15


def _signed_in(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _bundle_json(bundle):
    now = timezone.now()
    return {
        "id": str(bundle.id), "title": bundle.title, "documents": [{"id": str(item.id), "title": item.title} for item in bundle.documents.all()],
        "created_at": bundle.created_at.isoformat(), "expires_at": bundle.expires_at.isoformat(),
        "revoked_at": bundle.revoked_at.isoformat() if bundle.revoked_at else None, "downloads": bundle.downloads,
        "active": bundle.revoked_at is None and bundle.expires_at > now, "status": bundle.zip_status,
    }


def bundle_dir():
    return Path(settings.MEDIA_ROOT) / "bundles"


def remove_bundle_files(bundles):
    for bundle in bundles:
        if bundle.zip_path:
            (Path(settings.MEDIA_ROOT) / bundle.zip_path).unlink(missing_ok=True)
    ShareBundle.objects.filter(pk__in=[item.pk for item in bundles]).update(zip_path="", zip_size=0)


def revoke_bundles_containing(document_ids, when=None):
    """Revoke live bundles that include any of these documents and delete their ZIPs. Returns the count."""
    when = when or timezone.now()
    bundles = list(ShareBundle.objects.filter(documents__in=document_ids, revoked_at__isnull=True).distinct())
    if bundles:
        ShareBundle.objects.filter(pk__in=[item.pk for item in bundles]).update(revoked_at=when)
        transaction.on_commit(lambda: remove_bundle_files(bundles))
    return len(bundles)


def _safe_name(value, used):
    name = unicodedata.normalize("NFC", Path(str(value)).name)
    stem, suffix = os.path.splitext(name)
    stem = re.sub(r"[^\w.\- ]+", "_", stem).strip(" .")[:150] or "document"
    suffix = re.sub(r"[^\w.]+", "", suffix)[:10]
    candidate, number = f"{stem}{suffix}", 2
    while candidate.casefold() in used:
        candidate, number = f"{stem} ({number}){suffix}", number + 1
    used.add(candidate.casefold())
    return candidate


def build_bundle(bundle_id):
    """Write the bundle ZIP once, hashing each original as it is copied; mark it ready or failed."""
    bundle = ShareBundle.objects.filter(pk=bundle_id, zip_status="building").first()
    if bundle is None:
        return
    documents = list(bundle.documents.filter(trashed_at__isnull=True, is_split_source=False, owner=bundle.owner).order_by("title", "id"))
    bundle_dir().mkdir(parents=True, exist_ok=True)
    relative = f"bundles/{bundle.id}.zip"
    target = Path(settings.MEDIA_ROOT) / relative
    partial = target.with_suffix(".part")
    try:
        used = set()
        with ZipFile(partial, "w", compression=ZIP_STORED) as archive:
            for document in documents:
                path = _media_path(document.original_path, "originals")
                digest, size = hashlib.sha256(), 0
                with path.open("rb") as source, archive.open(_safe_name(document.original_name, used), "w") as entry:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size += len(chunk)
                        entry.write(chunk)
                if digest.hexdigest() != document.original_sha256 or size != document.original_size:
                    raise ValueError("Original checksum changed")
        os.replace(partial, target)
    except (OSError, ValueError):
        logger.warning("Bundle %s could not be built", bundle_id, exc_info=True)
        partial.unlink(missing_ok=True)
        ShareBundle.objects.filter(pk=bundle.pk).update(zip_status="failed")
        return
    updated = ShareBundle.objects.filter(pk=bundle.pk, revoked_at__isnull=True, zip_status="building").update(
        zip_status="ready", zip_path=relative, zip_size=target.stat().st_size)
    if not updated:  # revoked while building
        target.unlink(missing_ok=True)


@require_http_methods(["GET", "POST"])
def share_bundles(request):
    from .tasks import build_share_bundle

    denied = _signed_in(request)
    if denied:
        return denied
    if request.method == "GET":
        bundles = ShareBundle.objects.filter(owner=request.user).prefetch_related("documents")[:50]
        return JsonResponse({"bundles": [_bundle_json(item) for item in bundles]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    ids = body.get("document_ids")
    days = body.get("expires_in_days", 7)
    title = body.get("title", "")
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_BUNDLE_DOCUMENTS or not all(isinstance(item, str) for item in ids):
        return JsonResponse({"error": f"Choose 1–{MAX_BUNDLE_DOCUMENTS} documents"}, status=400)
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 30:
        return JsonResponse({"error": "Expiry must be 1–30 days"}, status=400)
    if not isinstance(title, str) or len(title.strip()) > 200:
        return JsonResponse({"error": "Title must be up to 200 characters"}, status=400)
    try:
        documents = list(Document.objects.filter(owner=request.user, trashed_at__isnull=True, is_split_source=False, pk__in=set(ids)))
    except ValidationError:
        documents = []
    if len(documents) != len(set(ids)):
        return JsonResponse({"error": "Document not found"}, status=404)
    if sum(item.original_size for item in documents) > MAX_BUNDLE_BYTES:
        return JsonResponse({"error": "Together these files are larger than 200 MB. Share fewer documents."}, status=400)
    if ShareBundle.objects.filter(owner=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()).count() >= 20:
        return JsonResponse({"error": "Revoke an active bundle before creating another"}, status=409)
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        bundle = ShareBundle.objects.create(owner=request.user, title=title.strip() or f"{len(documents)} documents",
                                            token_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
                                            expires_at=timezone.now() + timedelta(days=days))
        bundle.documents.set(documents)
        transaction.on_commit(lambda: build_share_bundle.delay(str(bundle.id)), robust=True)
    url = f"{settings.PUBLIC_ORIGIN.rstrip('/')}/api/share-bundles/{token}"
    return JsonResponse({**_bundle_json(bundle), "url": url}, status=201)


@require_http_methods(["DELETE"])
def share_bundle_detail(request, bundle_id):
    denied = _signed_in(request)
    if denied:
        return denied
    with transaction.atomic():
        bundle = ShareBundle.objects.select_for_update().filter(pk=bundle_id, owner=request.user).first()
        if bundle is None:
            return JsonResponse({"error": "Bundle not found"}, status=404)
        if bundle.revoked_at is None:
            bundle.revoked_at = timezone.now()
            bundle.save(update_fields=["revoked_at"])
            transaction.on_commit(lambda: remove_bundle_files([bundle]))
    return JsonResponse(_bundle_json(bundle))


@require_http_methods(["GET"])
def shared_bundle(request, token):
    """Anonymous download of the prebuilt, verified ZIP."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return JsonResponse({"error": "Link not found"}, status=404)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    with transaction.atomic():
        bundle = ShareBundle.objects.select_for_update().filter(token_hash=token_hash).first()
        if bundle is None or bundle.revoked_at is not None or bundle.expires_at <= timezone.now():
            return JsonResponse({"error": "Link not found"}, status=404)
        if bundle.zip_status == "building":
            response = JsonResponse({"error": "This bundle is still being prepared. Try again in a minute."}, status=503)
            response["Retry-After"] = "30"
            return response
        if bundle.zip_status != "ready" or not bundle.zip_path:
            return JsonResponse({"error": "Shared files are unavailable"}, status=503)
        try:
            handle = (Path(settings.MEDIA_ROOT) / bundle.zip_path).open("rb")
        except OSError:
            return JsonResponse({"error": "Shared files are unavailable"}, status=503)
        ShareBundle.objects.filter(pk=bundle.pk).update(downloads=F("downloads") + 1)
    name = re.sub(r"[^\w.\- ]+", "_", bundle.title).strip()[:100] or "documents"
    response = FileResponse(handle, content_type="application/zip", as_attachment=True, filename=f"{name}.zip")
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def expire_bundles():
    """Delete ZIPs of bundles whose links have ended."""
    ended = list(ShareBundle.objects.exclude(zip_path="").filter(Q(revoked_at__isnull=False) | Q(expires_at__lte=timezone.now())))
    remove_bundle_files(ended)
    return len(ended)


def _email_json(item):
    return {"id": str(item.id), "recipients": item.recipients, "status": item.status, "detail": item.detail, "created_at": item.created_at.isoformat()}


@require_http_methods(["GET", "POST"])
def document_email(request, document_id):
    """Email one document (original or searchable PDF). Needs RIPIANO_DOCUMENT_EMAIL=1 and SMTP settings."""
    from django.contrib.auth import get_user_model

    from .tasks import send_document_email

    denied = _signed_in(request)
    if denied:
        return denied
    document = Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    enabled = bool(settings.EMAIL_HOST) and settings.RIPIANO_DOCUMENT_EMAIL
    if request.method == "GET":
        DocumentEmailSend.objects.filter(document=document, status=DocumentEmailSend.Status.QUEUED,
                                         created_at__lt=timezone.now() - timedelta(minutes=STALE_EMAIL_MINUTES)).update(
            status=DocumentEmailSend.Status.FAILED, detail="Sending did not finish. Try again.")
        return JsonResponse({"configured": enabled, "sends": [_email_json(item) for item in DocumentEmailSend.objects.filter(document=document)[:20]]})
    if not enabled:
        return JsonResponse({"error": "Emailing documents is not turned on for this server."}, status=409)
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    raw, message, attachment = body.get("to", ""), body.get("message", ""), body.get("attachment", "original")
    if not isinstance(raw, str) or len(raw) > 1000 or not isinstance(message, str) or len(message) > 2000 or attachment not in ("original", "searchable"):
        return JsonResponse({"error": "Check the recipients, message, and attachment"}, status=400)
    recipients = list(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))
    if not 1 <= len(recipients) <= 10:
        return JsonResponse({"error": "Add 1–10 email addresses, separated by commas"}, status=400)
    for address in recipients:
        try:
            validate_email(address)
        except ValidationError:
            return JsonResponse({"error": f"“{address}” is not an email address"}, status=400)
    if attachment == "searchable":
        try:
            ready = document.status == Document.Status.READY and bool(document.archive_path) and _media_path(document.archive_path, "archive").is_file()
            size = _media_path(document.archive_path, "archive").stat().st_size if ready else 0
        except (OSError, ValueError):
            ready = False
        if not ready:
            return JsonResponse({"error": "The searchable PDF is not ready yet"}, status=409)
    else:
        size = document.original_size
    if size > settings.RIPIANO_EMAIL_ATTACH_MAX_BYTES:
        return JsonResponse({"error": f"This file is larger than {settings.RIPIANO_EMAIL_ATTACH_MAX_BYTES // (1024 * 1024)} MB. Share a link instead."}, status=400)
    with transaction.atomic():
        get_user_model().objects.select_for_update().filter(pk=request.user.pk).first()  # serialise the hourly limit
        recent = DocumentEmailSend.objects.filter(owner=request.user, created_at__gte=timezone.now() - timedelta(hours=1)).values_list("recipients", flat=True)
        if sum(len(item.split(",")) for item in recent) + len(recipients) > EMAIL_RECIPIENTS_PER_HOUR:
            return JsonResponse({"error": "You have emailed many people in the last hour. Try again later."}, status=429)
        send = DocumentEmailSend.objects.create(document=document, owner=request.user, recipients=", ".join(recipients),
                                                attachment=attachment, message=message.strip())
        transaction.on_commit(lambda: send_document_email.delay(str(send.id)), robust=True)
    return JsonResponse(_email_json(send), status=202)
