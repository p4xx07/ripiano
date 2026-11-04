import hashlib
import json
import secrets
from datetime import timedelta
from uuid import UUID

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import AgentAudit, AgentGrant, Tag

SCOPES = {
    "documents:search": "Find document titles and filing metadata",
    "documents:text": "Read extracted document text",
    "documents:tag": "Change document tags",
}


def _owner(request):
    return request.user.is_authenticated and request.user.is_superuser


def grant_json(grant):
    return {
        "id": str(grant.id),
        "name": grant.name,
        "scopes": grant.scopes,
        "filter_tag_id": str(grant.filter_tag_id) if grant.filter_tag_id else None,
        "filter_tag_name": grant.filter_tag.name if grant.filter_tag_id else None,
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        "last_used_at": grant.last_used_at.isoformat() if grant.last_used_at else None,
        "created_at": grant.created_at.isoformat(),
    }


@require_http_methods(["GET", "POST"])
def grants(request):
    if not _owner(request):
        return JsonResponse({"error": "Owner access required"}, status=403)
    if request.method == "GET":
        return JsonResponse({
            "scopes": SCOPES,
            "grants": [grant_json(grant) for grant in AgentGrant.objects.filter(owner=request.user).select_related("filter_tag")[:100]],
        })
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = None
    if not isinstance(body, dict):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = body.get("name")
    scopes = body.get("scopes")
    days = body.get("expires_in_days", 30)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        return JsonResponse({"error": "Name must be 1–100 characters"}, status=400)
    if not isinstance(scopes, list) or not scopes or not all(isinstance(scope, str) for scope in scopes) or len(scopes) != len(set(scopes)) or any(scope not in SCOPES for scope in scopes):
        return JsonResponse({"error": "Choose valid, distinct permissions"}, status=400)
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 365:
        return JsonResponse({"error": "Expiry must be 1–365 days"}, status=400)
    filter_tag = None
    if body.get("filter_tag_id"):
        try:
            filter_tag = Tag.objects.filter(owner=request.user, pk=UUID(str(body["filter_tag_id"]))).first()
        except ValueError:
            pass
        if filter_tag is None:
            return JsonResponse({"error": "Filter tag not found"}, status=400)
    token = "rpa_" + secrets.token_urlsafe(32)
    grant = AgentGrant.objects.create(
        owner=request.user,
        name=name.strip(),
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        scopes=scopes,
        filter_tag=filter_tag,
        expires_at=timezone.now() + timedelta(days=days),
    )
    return JsonResponse({**grant_json(grant), "token": token}, status=201)


@require_http_methods(["DELETE"])
def grant_detail(request, grant_id):
    if not _owner(request):
        return JsonResponse({"error": "Owner access required"}, status=403)
    grant = AgentGrant.objects.filter(pk=grant_id, owner=request.user).first()
    if grant is None:
        return JsonResponse({"error": "Agent grant not found"}, status=404)
    if grant.revoked_at is None:
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])
    return JsonResponse({"revoked": True})


@require_http_methods(["GET"])
def events(request):
    if not _owner(request):
        return JsonResponse({"error": "Owner access required"}, status=403)
    return JsonResponse({"events": [{
        "agent": event.grant.name,
        "action": event.action,
        "document_id": str(event.document_id) if event.document_id else None,
        "outcome": event.outcome,
        "at": event.created_at.isoformat(),
    } for event in AgentAudit.objects.filter(grant__owner=request.user).select_related("grant")[:100]]})
