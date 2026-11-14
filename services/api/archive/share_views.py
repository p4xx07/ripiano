"""Owner-created, expiring links to immutable original document bytes."""

import hashlib
import json
import re
import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .export_views import _media_path
from .models import Document, ShareLink


def _share_json(share):
    return {
        "id": str(share.id),
        "created_at": share.created_at.isoformat(),
        "expires_at": share.expires_at.isoformat(),
        "revoked_at": share.revoked_at.isoformat() if share.revoked_at else None,
        "active": share.revoked_at is None and share.expires_at > timezone.now(),
    }


@require_http_methods(["GET", "POST"])
def document_shares(request, document_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    if request.method == "GET":
        document = Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
        if document is None:
            return JsonResponse({"error": "Document not found"}, status=404)
        return JsonResponse({"shares": [_share_json(item) for item in document.share_links.all()[:50]]})
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = None
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    days = body.get("expires_in_days", 7)
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 30:
        return JsonResponse({"error": "Expiry must be 1–30 days"}, status=400)
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
        if document is None:
            return JsonResponse({"error": "Document not found"}, status=404)
        active_count = ShareLink.objects.filter(document=document, revoked_at__isnull=True, expires_at__gt=timezone.now()).count()
        if active_count >= 20:
            return JsonResponse({"error": "Revoke an active link before creating another"}, status=409)
        token = secrets.token_urlsafe(32)
        share = ShareLink.objects.create(
            document=document, owner=request.user,
            token_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
            expires_at=timezone.now() + timedelta(days=days),
        )
    url = f"{settings.PUBLIC_ORIGIN.rstrip('/')}/api/share-links/{token}"
    return JsonResponse({**_share_json(share), "url": url}, status=201)


@require_http_methods(["DELETE"])
def document_share_detail(request, document_id, share_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id, owner=request.user).first()
        if document is None:
            return JsonResponse({"error": "Share link not found"}, status=404)
        share = ShareLink.objects.select_for_update().filter(pk=share_id, document=document, owner=request.user).first()
        if share is None:
            return JsonResponse({"error": "Share link not found"}, status=404)
        if share.revoked_at is None:
            share.revoked_at = timezone.now()
            share.save(update_fields=["revoked_at"])
    return JsonResponse(_share_json(share))


@require_http_methods(["GET"])
def shared_original(request, token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return JsonResponse({"error": "Link not found"}, status=404)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    identity = ShareLink.objects.filter(token_hash=token_hash).values_list("pk", "document_id").first()
    if identity is None:
        return JsonResponse({"error": "Link not found"}, status=404)
    share_id, document_id = identity
    with transaction.atomic():
        # Match the lock order used by Trash and revoke, then open while authorized.
        document = Document.objects.select_for_update().filter(pk=document_id).first()
        share = ShareLink.objects.select_for_update().filter(pk=share_id, token_hash=token_hash).first()
        if document is None or share is None or share.revoked_at is not None or share.expires_at <= timezone.now() or document.trashed_at is not None:
            return JsonResponse({"error": "Link not found"}, status=404)
        try:
            path = _media_path(document.original_path, "originals")
            if path.stat().st_size != document.original_size:
                raise ValueError("Original size changed")
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != document.original_sha256:
                raise ValueError("Original checksum changed")
            response = FileResponse(path.open("rb"), content_type=document.original_mime, as_attachment=True, filename=Path(document.original_name).name)
        except (OSError, ValueError):
            return JsonResponse({"error": "Shared file is unavailable"}, status=503)
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response
