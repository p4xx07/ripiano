"""Personal API tokens: `Authorization: Token rip_…` on /api/ requests, acting as the token's owner."""

import hashlib
import json
import secrets
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import ApiToken

PREFIX = "rip_"
# Anonymous share downloads stay usable even if a client sends a stale token header.
PUBLIC_PREFIXES = ("/api/share-links/", "/api/share-bundles/")
# Tokens cannot mint other credentials, create public links, or change how people sign in.
BLOCKED_PREFIXES = ("/api/account/", "/api/session", "/api/setup", "/api/agents", "/api/share-bundles")


def _blocked(request):
    if request.path.startswith(BLOCKED_PREFIXES):
        return True
    return request.method != "GET" and request.path.startswith("/api/documents/") and "/shares" in request.path


def revoke_tokens_on_password_change(sender, instance, **kwargs):
    """A new password ends every API token, like it ends other sessions."""
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).values_list("password", flat=True).first()
    if previous is not None and previous != instance.password:
        ApiToken.objects.filter(user_id=instance.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class ApiTokenMiddleware:
    """Authenticate API requests that carry a token. Token requests need no CSRF token and cannot manage account security."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if request.path.startswith("/api/") and header.startswith("Token ") and not (
                request.method == "GET" and request.path.startswith(PUBLIC_PREFIXES) and request.path.count("/") == 3):
            token = header[6:].strip()
            record = None
            if token.startswith(PREFIX) and len(token) < 100:
                record = ApiToken.objects.select_related("user").filter(token_hash=_hash(token)).first()
            now = timezone.now()
            if record is None or record.revoked_at or record.expires_at <= now or not record.user.is_active:
                return JsonResponse({"error": "Invalid or expired API token"}, status=401)
            if _blocked(request):
                return JsonResponse({"error": "API tokens cannot manage sign-in, security, agent access, or public links"}, status=403)
            request.user = record.user
            request._dont_enforce_csrf_checks = True
            if not record.last_used_at or now - record.last_used_at > timedelta(minutes=5):
                ApiToken.objects.filter(pk=record.pk).update(last_used_at=now)
        return self.get_response(request)


def _json(item):
    return {"id": str(item.id), "name": item.name, "prefix": item.prefix, "created_at": item.created_at.isoformat(),
            "expires_at": item.expires_at.isoformat(), "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
            "active": item.revoked_at is None and item.expires_at > timezone.now()}


@require_http_methods(["GET", "POST"])
def tokens(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    if request.method == "GET":
        return JsonResponse({"tokens": [_json(item) for item in ApiToken.objects.filter(user=request.user, revoked_at__isnull=True)[:50]]})
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = None
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    from .throttle import record_sign_in_failure, sign_in_blocked, sign_in_throttle_key

    keys = sign_in_throttle_key(request, request.user.get_username())
    if sign_in_blocked(keys):
        return JsonResponse({"error": "Too many attempts. Wait a few minutes and try again."}, status=429)
    if not request.user.check_password(str(body.get("password", ""))):
        record_sign_in_failure(keys)
        return JsonResponse({"error": "Your password is not correct"}, status=400)
    name, days = body.get("name", ""), body.get("expires_in_days", 90)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return JsonResponse({"error": "Give the token a name (up to 100 characters)"}, status=400)
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 365:
        return JsonResponse({"error": "Expiry must be 1–365 days"}, status=400)
    if ApiToken.objects.filter(user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()).count() >= 20:
        return JsonResponse({"error": "Revoke an unused token before creating another"}, status=409)
    token = PREFIX + secrets.token_urlsafe(32)
    item = ApiToken.objects.create(user=request.user, name=name.strip(), token_hash=_hash(token), prefix=token[:10],
                                   expires_at=timezone.now() + timedelta(days=days))
    return JsonResponse({**_json(item), "token": token}, status=201)


@require_http_methods(["DELETE"])
def token_detail(request, token_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    updated = ApiToken.objects.filter(pk=token_id, user=request.user, revoked_at__isnull=True).update(revoked_at=timezone.now())
    if not updated:
        return JsonResponse({"error": "Token not found"}, status=404)
    return JsonResponse({"revoked": True})


def _find_methods(view, seen=None):
    seen = seen if seen is not None else set()
    if id(view) in seen:
        return None
    seen.add(id(view))
    for cell in getattr(view, "__closure__", None) or ():
        value = cell.cell_contents
        if isinstance(value, (list, tuple)) and value and all(isinstance(item, str) and item.isupper() for item in value):
            return [item.lower() for item in value]
    for cell in getattr(view, "__closure__", None) or ():
        value = cell.cell_contents
        if callable(value):
            found = _find_methods(value, seen)
            if found:
                return found
    return None


def _methods(view):
    """HTTP methods allowed by a view decorated with require_http_methods (read from its closures)."""
    return _find_methods(view) or ["get"]


@require_http_methods(["GET"])
def schema(request):
    """A generated OpenAPI 3.1 outline of every /api/ route (paths, path parameters, and methods)."""
    import re

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)

    from django.urls import URLPattern, get_resolver

    paths = {}
    for pattern in get_resolver().url_patterns:
        if not isinstance(pattern, URLPattern):
            continue
        route = str(pattern.pattern)
        if not route.startswith("api/"):
            continue
        parameters = []
        def replace(match):
            kind, name = match.group(1), match.group(2)
            parameters.append({"name": name, "in": "path", "required": True,
                               "schema": {"type": "integer"} if kind == "int" else {"type": "string", **({"format": "uuid"} if kind == "uuid" else {})}})
            return "{" + name + "}"
        path = "/" + re.sub(r"<(?:(\w+):)?(\w+)>", replace, route)
        operations = {}
        for method in _methods(pattern.callback):
            operations[method] = {
                "operationId": f"{method}_{pattern.callback.__name__}",
                "summary": (pattern.callback.__doc__ or pattern.callback.__name__.replace("_", " ")).strip().splitlines()[0],
                "parameters": parameters, "responses": {"200": {"description": "JSON response"}},
            }
        paths[path] = operations
    return JsonResponse({
        "openapi": "3.1.0",
        "info": {"title": "Ripiano API", "version": "1"},
        "components": {"securitySchemes": {
            "session": {"type": "apiKey", "in": "cookie", "name": "sessionid"},
            "token": {"type": "apiKey", "in": "header", "name": "Authorization", "description": "Token rip_…"},
        }},
        "security": [{"session": []}, {"token": []}],
        "paths": dict(sorted(paths.items())),
    })
