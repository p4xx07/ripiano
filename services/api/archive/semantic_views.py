"""Settings and search endpoints for optional semantic search."""

import json
import logging
from urllib.parse import urlsplit

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Document, SemanticDocument, SemanticSettings
from .semantic import (DEFAULT_NAS_MODEL, DEFAULT_OLLAMA_MODEL, SemanticError, clear_error, embed, ensure_storage, model_name,
                       pending_documents, pgvector_available, search, storage_ready)

logger = logging.getLogger(__name__)


def _status(config):
    ready = storage_ready()
    total = Document.objects.filter(status=Document.Status.READY, trashed_at__isnull=True, is_split_source=False).count()
    waiting = pending_documents(config).count() if config.mode != SemanticSettings.Mode.OFF else None
    return {
        "mode": config.mode, "ollama_url": config.ollama_url, "model_name": config.model_name, "keep_loaded": config.keep_loaded,
        "effective_model": model_name(config) if config.mode != SemanticSettings.Mode.OFF else None,
        "defaults": {"ollama": DEFAULT_OLLAMA_MODEL, "nas": DEFAULT_NAS_MODEL},
        "database_supported": pgvector_available(), "storage_ready": ready,
        "documents": {"total": total, "waiting": waiting,
                      "indexed": SemanticDocument.objects.filter(model_name=model_name(config)).count() if config.mode != SemanticSettings.Mode.OFF else None},
        "last_error": config.last_error, "last_error_at": config.last_error_at.isoformat() if config.last_error_at else None,
    }


def _admin(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"error": "Archive owner access required"}, status=403)
    return None


def _validated(body, config):
    mode = body.get("mode", config.mode)
    if mode not in SemanticSettings.Mode.values:
        raise ValueError("Choose Off, Ollama, or On the NAS")
    url = body.get("ollama_url", config.ollama_url)
    if not isinstance(url, str) or len(url) > 300:
        raise ValueError("Enter the Ollama address")
    url = url.strip().rstrip("/")
    if url:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.path not in ("", "/"):
            raise ValueError("Enter the Ollama address like http://192.168.1.30:11434")
    if mode == SemanticSettings.Mode.OLLAMA and not url:
        raise ValueError("Enter the Ollama address")
    name = body.get("model_name", config.model_name)
    if not isinstance(name, str) or len(name.strip()) > 200:
        raise ValueError("The model name is too long")
    keep = body.get("keep_loaded", config.keep_loaded)
    if not isinstance(keep, bool):
        raise ValueError("Choose whether to keep the model loaded")
    config.mode, config.ollama_url, config.model_name, config.keep_loaded = mode, url, name.strip(), keep
    return config


@require_http_methods(["GET", "PATCH"])
def semantic_settings(request):
    denied = _admin(request)
    if denied:
        return denied
    config = SemanticSettings.current()
    if request.method == "GET":
        return JsonResponse(_status(config))
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    try:
        with transaction.atomic():
            config = _validated(body, SemanticSettings.objects.select_for_update().get(pk=config.pk))
            if config.mode != SemanticSettings.Mode.OFF:
                ensure_storage()
            config.last_error, config.last_error_at = "", None
            config.save()
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except SemanticError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    if config.mode != SemanticSettings.Mode.OFF:
        from .tasks import semantic_index

        transaction.on_commit(lambda: semantic_index.delay(), robust=True)
    return JsonResponse(_status(config))


@require_http_methods(["POST"])
def semantic_test(request):
    """Embed one short text with the saved settings, so the owner knows the connection works before indexing."""
    denied = _admin(request)
    if denied:
        return denied
    config = SemanticSettings.current()
    if config.mode == SemanticSettings.Mode.OFF:
        return JsonResponse({"error": "Semantic search is off"}, status=409)
    try:
        # A NAS model may need to download and load first, so this can take a minute on first use.
        vector = embed(config, ["Ripiano connection test"], timeout=300)[0]
    except SemanticError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)
    clear_error()
    return JsonResponse({"ok": True, "dimensions": len(vector), "model": model_name(config)})


@require_http_methods(["GET"])
def semantic_search(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    query = request.GET.get("q", "").strip()
    if not query or len(query) > 500:
        return JsonResponse({"error": "Ask a question of up to 500 characters"}, status=400)
    config = SemanticSettings.current()
    if config.mode == SemanticSettings.Mode.OFF:
        return JsonResponse({"enabled": False, "results": []})
    try:
        results = search(request.user, query, allowed=Document.objects.filter(owner=request.user, trashed_at__isnull=True, is_split_source=False))
    except SemanticError as exc:
        return JsonResponse({"enabled": True, "results": [], "error": str(exc)}, status=503)
    return JsonResponse({"enabled": True, "results": results})


@require_http_methods(["GET"])
def semantic_availability(request):
    """Whether the Library should offer meaning-based results (any signed-in person)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    config = SemanticSettings.current()
    return JsonResponse({"enabled": config.mode != SemanticSettings.Mode.OFF and storage_ready()})
