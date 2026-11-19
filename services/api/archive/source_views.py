"""Owner-scoped management of external storage sources."""

import json
import re
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Correspondent, DocumentType, StorageSource, Tag
from .storage_sources import CLOUD_KINDS, FILE_TYPES, SourceError, preview
from .field_labels import label

MAX_SOURCES = 20


def _signed_in(request):
    return None if request.user.is_authenticated else JsonResponse({"error": "Sign in required"}, status=401)


def _json(source):
    return {
        "id": str(source.id), "name": source.name, "kind": source.kind, "enabled": source.enabled, "builtin": source.builtin,
        "endpoint": source.endpoint, "region": source.region, "bucket": source.bucket, "addressing": source.addressing,
        "username": source.username, "has_secret": bool(source.secret),
        "connected": bool(source.secret) if source.kind in CLOUD_KINDS else None,
        "path": source.path, "recursive": source.recursive, "include_patterns": source.include_patterns,
        "exclude_patterns": source.exclude_patterns, "file_types": source.file_types, "max_size_mb": source.max_size_mb,
        "modified_after": source.modified_after.isoformat() if source.modified_after else None,
        "after": source.after, "processed_path": source.processed_path, "retention_days": source.retention_days,
        "tag_ids": [str(tag.id) for tag in source.tags.all()],
        "correspondent_id": str(source.correspondent_id) if source.correspondent_id else None,
        "document_type_id": str(source.document_type_id) if source.document_type_id else None,
        "poll_minutes": source.poll_minutes,
        "allowed_chats": source.allowed_chats, "pending_chats": source.pending_chats, "reply_language": source.reply_language,
        "status": {
            "running": source.running_since is not None,
            "last_checked_at": source.last_checked_at.isoformat() if source.last_checked_at else None,
            "last_error": source.last_error, "last_imported": source.last_imported, "total_imported": source.total_imported,
        },
    }


def _text(body, key, limit, current, required=False, name=None):
    name = name or label(key)
    value = body.get(key, current)
    if not isinstance(value, str) or len(value.strip()) > limit:
        raise ValueError(f"{name} must be text up to {limit} characters")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Enter the {name.lower()}")
    return value


def _number(body, key, current, low, high, label):
    value = body.get(key, current)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


def _owned(model, owner, value, label):
    if value in (None, ""):
        return None
    try:
        item = model.objects.filter(pk=value, owner=owner).first() if isinstance(value, str) else None
    except ValidationError:
        item = None
    if item is None:
        raise ValueError(f"{label} not found")
    return item


def _apply(source, body, owner):
    from .mail import MailError, encrypt_secret

    source.name = _text(body, "name", 100, source.name, required=True)
    kind = source.kind if source.builtin else body.get("kind", source.kind)
    if kind not in StorageSource.Kind.values:
        raise ValueError("Choose a storage kind")
    source.kind = kind
    for key in ("enabled", "recursive"):
        value = body.get(key, getattr(source, key))
        if not isinstance(value, bool):
            raise ValueError(f"{label(key)} must be true or false")
        setattr(source, key, value)
    reply_language = body.get("reply_language", source.reply_language)
    if reply_language not in ("en", "it"):
        raise ValueError("Choose English or Italian for the bot's replies")
    source.reply_language = reply_language
    s3 = source.kind == StorageSource.Kind.S3
    folder = source.kind == StorageSource.Kind.FOLDER
    if folder and not owner.is_superuser:
        raise ValueError("Only the archive owner can import from folders on the NAS")
    credentials = source.kind in (StorageSource.Kind.S3, StorageSource.Kind.WEBDAV)
    cloud = source.kind in CLOUD_KINDS  # signed in with "Connect account" after saving
    files = credentials or folder or cloud  # storages with folders, files, and after-import actions
    source.endpoint = _text(body, "endpoint", 300, source.endpoint, required=credentials).rstrip("/")
    source.region = _text(body, "region", 50, source.region) or "us-east-1"
    source.bucket = _text(body, "bucket", 100, source.bucket, required=s3)
    addressing = body.get("addressing", source.addressing)
    if addressing not in StorageSource.Addressing.values:
        raise ValueError("Choose path or virtual-hosted addressing")
    source.addressing = addressing
    source.username = _text(body, "username", 200, source.username, required=credentials, name="Access key" if s3 else None)
    if "secret" in body and not folder and not cloud:
        secret = body["secret"]
        if not isinstance(secret, str) or not 0 < len(secret) <= 500:
            raise ValueError("Enter the secret" if credentials else "Enter the bot token")
        secret = secret.strip() if not credentials else secret
        if not credentials and not re.fullmatch(r"\d{5,15}:[A-Za-z0-9_-]{30,60}", secret):
            raise ValueError("That does not look like a Telegram bot token (it looks like 123456789:AA…)")
        try:
            source.secret = encrypt_secret(secret)
        except MailError as exc:
            raise ValueError(str(exc)) from exc
    if not source.secret and not folder and not cloud:
        raise ValueError(("Enter the secret key" if s3 else "Enter the password") if credentials else "Enter the bot token")
    source.path = _text(body, "path", 500, source.path).lstrip("/")
    source.include_patterns = _text(body, "include_patterns", 500, source.include_patterns)
    source.exclude_patterns = _text(body, "exclude_patterns", 500, source.exclude_patterns)
    types = body.get("file_types", source.file_types)
    if not isinstance(types, list) or not set(types) <= set(FILE_TYPES):
        raise ValueError("Unknown file type")
    source.file_types = sorted(set(types))
    source.max_size_mb = _number(body, "max_size_mb", source.max_size_mb, 1, 25, "Largest file size (MB)")
    after_date = body.get("modified_after", source.modified_after.isoformat() if source.modified_after else None)
    if after_date in (None, ""):
        source.modified_after = None
    else:
        try:
            source.modified_after = date.fromisoformat(after_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("Use a date like 2026-01-31") from exc
    after = body.get("after", source.after)
    if after not in StorageSource.After.values:
        raise ValueError("Choose what happens after import")
    source.after = after
    source.processed_path = _text(body, "processed_path", 500, source.processed_path).lstrip("/")
    if not files:
        source.after, source.recursive = StorageSource.After.KEEP, False  # nothing to move or traverse in a chat
        source.max_size_mb = min(source.max_size_mb, 20)  # Telegram bots cannot download larger files
    if source.after == StorageSource.After.MOVE:
        if not source.processed_path:
            raise ValueError("Enter the processed folder")
        root = source.path.rstrip("/") + "/" if source.path else ""
        processed = source.processed_path.rstrip("/") + "/"
        if root and root.startswith(processed):
            raise ValueError("The source folder cannot be inside the processed folder")
    source.retention_days = _number(body, "retention_days", source.retention_days, 0, 3650, "Days to keep processed files")
    source.poll_minutes = _number(body, "poll_minutes", source.poll_minutes, 1 if folder else 5, 1440, "Check interval (minutes)")
    if "correspondent_id" in body:
        source.correspondent = _owned(Correspondent, owner, body["correspondent_id"], "Sender")
    if "document_type_id" in body:
        source.document_type = _owned(DocumentType, owner, body["document_type_id"], "Document type")
    tags = None
    if "tag_ids" in body:
        values = body["tag_ids"]
        if not isinstance(values, list) or len(values) > 20 or not all(isinstance(item, str) for item in values):
            raise ValueError("Tags must be a list")
        try:
            tags = list(Tag.objects.filter(owner=owner, pk__in=values))
        except ValidationError:
            tags = []
        if len(tags) != len(set(values)):
            raise ValueError("Tag not found")
    return tags


def _save(source, body, owner):
    try:
        with transaction.atomic():
            tags = _apply(source, body, owner)
            source.save()
            if tags is not None:
                source.tags.set(tags)
    except IntegrityError as exc:
        raise ValueError("You already have a source with this name") from exc


def _body(request):
    try:
        value = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


@require_http_methods(["GET", "POST"])
def sources(request):
    denied = _signed_in(request)
    if denied:
        return denied
    if request.method == "GET":
        items = StorageSource.objects.filter(owner=request.user).prefetch_related("tags")
        return JsonResponse({"sources": [_json(item) for item in items], "file_types": sorted(FILE_TYPES)})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if StorageSource.objects.filter(owner=request.user).count() >= MAX_SOURCES:
        return JsonResponse({"error": f"You can connect up to {MAX_SOURCES} sources"}, status=400)
    source = StorageSource(owner=request.user)
    try:
        _save(source, body, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_json(source), status=201)


def _mine(request, source_id):
    return StorageSource.objects.select_related("owner").filter(pk=source_id, owner=request.user).first()


@require_http_methods(["PATCH", "DELETE"])
def source_detail(request, source_id):
    denied = _signed_in(request)
    if denied:
        return denied
    source = _mine(request, source_id)
    if source is None:
        return JsonResponse({"error": "Source not found"}, status=404)
    if request.method == "DELETE":
        if source.builtin:
            return JsonResponse({"error": "The consume folder is built in. Pause it instead, or unmount RIPIANO_CONSUME_PATH."}, status=409)
        source.delete()  # imported documents stay in the archive
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    try:
        _save(source, body, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_json(source))


@require_http_methods(["POST"])
def source_preview(request, source_id):
    """Connect and list what the next check would import, without importing or changing anything."""
    denied = _signed_in(request)
    if denied:
        return denied
    source = _mine(request, source_id)
    if source is None:
        return JsonResponse({"error": "Source not found"}, status=404)
    try:
        return JsonResponse({"ok": True, **preview(source)})
    except SourceError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)


@require_http_methods(["POST"])
def source_chats(request, source_id):
    """Allow a waiting Telegram chat, or remove an allowed one: {"allow": id} or {"remove": id}."""
    denied = _signed_in(request)
    if denied:
        return denied
    body = _body(request) or {}
    with transaction.atomic():
        source = StorageSource.objects.select_for_update().filter(pk=source_id, owner=request.user, kind=StorageSource.Kind.TELEGRAM).first()
        if source is None:
            return JsonResponse({"error": "Telegram source not found"}, status=404)
        chat_id = body.get("allow", body.get("remove"))
        if not isinstance(chat_id, int) or isinstance(chat_id, bool):
            return JsonResponse({"error": "Choose a chat"}, status=400)
        if "allow" in body:
            waiting = next((item for item in source.pending_chats if item["id"] == chat_id), None)
            if waiting is None:
                return JsonResponse({"error": "That chat is not waiting for approval"}, status=404)
            source.pending_chats = [item for item in source.pending_chats if item["id"] != chat_id]
            source.allowed_chats = [item for item in source.allowed_chats if item["id"] != chat_id] + [waiting]
        else:
            source.allowed_chats = [item for item in source.allowed_chats if item["id"] != chat_id]
            source.pending_chats = [item for item in source.pending_chats if item["id"] != chat_id]
        source.save(update_fields=["allowed_chats", "pending_chats"])
    return JsonResponse(_json(source))


@require_http_methods(["POST"])
def source_run(request, source_id):
    """Check the source now instead of waiting for its interval."""
    denied = _signed_in(request)
    if denied:
        return denied
    source = _mine(request, source_id)
    if source is None:
        return JsonResponse({"error": "Source not found"}, status=404)
    if not source.enabled:
        return JsonResponse({"error": "Turn the source on first"}, status=409)
    from .tasks import poll_storage_source

    try:
        poll_storage_source.delay(str(source.id))
    except Exception:  # noqa: BLE001
        return JsonResponse({"error": "The background worker is not reachable"}, status=503)
    return JsonResponse({"queued": True}, status=202)




@require_http_methods(["POST"])
def source_connect(request, source_id):
    """Start the provider sign-in for a cloud drive source; returns the address to open."""
    from .cloud_sources import authorization_url

    denied = _signed_in(request)
    if denied:
        return denied
    source = _mine(request, source_id)
    if source is None or source.kind not in CLOUD_KINDS:
        return JsonResponse({"error": "Cloud drive source not found"}, status=404)
    try:
        return JsonResponse({"url": authorization_url(request.user, source)})
    except SourceError as exc:
        return JsonResponse({"error": str(exc)}, status=409)


@require_http_methods(["GET"])
def source_oauth_callback(request):
    from urllib.parse import urlencode

    from django.http import HttpResponseRedirect

    from .cloud_sources import exchange_code, read_state
    from .mail import encrypt_secret

    def back(**params):
        return HttpResponseRedirect("/?" + urlencode({"view": "sources", **params}))

    if not request.user.is_authenticated:
        return back(source_error="Sign in to Ripiano first, then use Connect account again.")
    if request.GET.get("error"):
        return back(source_error="The sign-in was cancelled.")
    try:
        state = read_state(request.GET.get("state", ""))
        if state.get("user") != request.user.pk:
            raise SourceError("This sign-in belongs to another Ripiano account.")
        source = StorageSource.objects.filter(pk=state.get("source"), owner=request.user, kind__in=CLOUD_KINDS).first()
        if source is None:
            raise SourceError("The source was removed while signing in.")
        refresh = exchange_code(source.kind, request.GET.get("code", ""))
    except SourceError as exc:
        return back(source_error=str(exc))
    StorageSource.objects.filter(pk=source.pk).update(secret=encrypt_secret(refresh), last_error="")
    return back(source_connected=source.name)


@require_http_methods(["GET", "PUT"])
def source_apps(request):
    """Archive owner: the OAuth apps registered with Google, Microsoft, and Dropbox."""
    from django.conf import settings

    from .cloud_sources import PROVIDERS, redirect_uri
    from .mail import MailError, encrypt_secret
    from .models import CloudApp

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    if request.method == "PUT":
        if not request.user.is_superuser:
            return JsonResponse({"error": "Archive owner access required"}, status=403)
        body = _body(request) or {}
        provider = body.get("provider")
        if provider not in PROVIDERS:
            return JsonResponse({"error": "Unknown provider"}, status=400)
        client_id, secret = body.get("client_id", ""), body.get("client_secret")
        if not isinstance(client_id, str) or len(client_id.strip()) > 300 or (secret is not None and (not isinstance(secret, str) or len(secret) > 500)):
            return JsonResponse({"error": "Enter the client ID and secret"}, status=400)
        if not client_id.strip():
            CloudApp.objects.filter(provider=provider).delete()
        else:
            app = CloudApp.objects.filter(provider=provider).first() or CloudApp(provider=provider)
            app.client_id = client_id.strip()
            if secret:
                try:
                    app.client_secret = encrypt_secret(secret.strip())
                except MailError as exc:
                    return JsonResponse({"error": str(exc)}, status=400)
            if not app.client_secret:
                return JsonResponse({"error": "Enter the client secret"}, status=400)
            app.save()
    apps = {app.provider: app for app in CloudApp.objects.all()}
    return JsonResponse({"redirect_uri": redirect_uri(), "providers": [{
        "provider": key, "label": value["label"], "console": value["console"],
        "client_id": apps[key].client_id if key in apps and request.user.is_superuser else "",
        "configured": key in apps or bool(value["fallback"] and settings.RIPIANO_MAIL_OAUTH.get(value["fallback"])),
        "from_environment": key not in apps and bool(value["fallback"] and settings.RIPIANO_MAIL_OAUTH.get(value["fallback"])),
    } for key, value in PROVIDERS.items()]})
