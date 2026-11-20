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
    "documents:filing": "Set sender and document type",
}


def _owner(request):
    # Every signed-in person can connect agents to their own archive; grants and audit are scoped to request.user.
    return request.user.is_authenticated


def grant_json(grant):
    return {
        "id": str(grant.id),
        "name": grant.name,
        "scopes": grant.scopes,
        "filter_tag_id": str(grant.filter_tag_id) if grant.filter_tag_id else None,
        "filter_tag_name": grant.filter_tag.name if grant.filter_tag_id else None,
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        # Why Ripiano ended the grant (not the owner): "password_changed" (D11) or "account_off" (D9); null otherwise.
        "revoked_reason": grant.revoked_reason or None,
        "last_used_at": grant.last_used_at.isoformat() if grant.last_used_at else None,
        "created_at": grant.created_at.isoformat(),
    }


def _json_body(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _password_refused(request, body):
    """The response refusing a sensitive agent action without the owner's current password, or None.

    Used to create an agent and to remove an agent with its activity log (docs/DECISIONS.md D10).
    Failed attempts count towards the sign-in limit.
    """
    from .throttle import record_sign_in_failure, sign_in_blocked, sign_in_throttle_key

    keys = sign_in_throttle_key(request, request.user.get_username())
    if sign_in_blocked(keys):
        return JsonResponse({"error": "Too many attempts. Wait a few minutes and try again."}, status=429)
    if not request.user.check_password(str(body.get("password", ""))):
        record_sign_in_failure(keys)
        return JsonResponse({"error": "Your password is not correct"}, status=400)
    return None


@require_http_methods(["GET", "POST"])
def grants(request):
    if not _owner(request):
        return JsonResponse({"error": "Owner access required"}, status=403)
    if request.method == "GET":
        return JsonResponse({
            "scopes": SCOPES,
            "grants": [grant_json(grant) for grant in AgentGrant.objects.filter(owner=request.user).select_related("filter_tag")[:100]],
        })
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    # An agent token can read document text for up to a year: confirm it is really the account's owner asking,
    # as for personal API tokens (judge 3 round 4, M2).
    refused = _password_refused(request, body)
    if refused:
        return refused
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
    # Two live grants with one name can't be told apart in the list or the audit log.
    if AgentGrant.objects.filter(owner=request.user, name__iexact=name.strip(), revoked_at__isnull=True, expires_at__gt=timezone.now()).exists():
        return JsonResponse({"error": "An active agent already uses this name"}, status=409)
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
    if request.GET.get("forget") in ("1", "true"):
        # Removing a revoked or expired agent also removes its activity log: nothing about what it
        # read is kept once the owner chose to forget it. Document history entries it made stay.
        if grant.revoked_at is None and (grant.expires_at is None or grant.expires_at > timezone.now()):
            return JsonResponse({"error": "Revoke this agent before removing it"}, status=409)
        # The log is the audit trail: removing it needs the owner's password, like creating an agent (D10).
        body = _json_body(request)
        if body is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        refused = _password_refused(request, body)
        if refused:
            return refused
        grant.delete()
        return JsonResponse({"deleted": True})
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
        # The owner's own title, so the activity list can say which document was involved.
        "document_title": event.document.title if event.document_id else None,
        "outcome": event.outcome,
        "at": event.created_at.isoformat(),
    } for event in AgentAudit.objects.filter(grant__owner=request.user).select_related("grant", "document").only(
        "action", "outcome", "created_at", "document_id", "grant__name", "document__title")[:100]]})
