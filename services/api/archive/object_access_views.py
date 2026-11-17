"""Share tags, senders, document types, and saved views with people and groups."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import ObjectAccess
from .object_access import EDIT, MODELS, shared_objects

User = get_user_model()
NAMES = {"tag": "Tag", "correspondent": "Sender", "document_type": "Document type", "saved_view": "Saved view"}


OWN_ALREADY_ERRORS = {"tag": "You already own this tag", "correspondent": "You already own this sender",
               "document_type": "You already own this document type", "saved_view": "You already own this saved search"}

SHARED_EDIT_ERRORS = {
    "tag": "With edit access you can change only the name, color, and description of a shared tag",
    "correspondent": "With edit access you can change only the name of a shared sender",
    "document_type": "With edit access you can change only the name of a shared document type",
    "saved_view": "With edit access you can change only the name, search text, and dates of a shared saved search",
}

def _body(request):
    try:
        value = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _grant_json(grant):
    from .people_views import _grant_json as document_grant_json

    return document_grant_json(grant)  # same shape as document sharing, so the same panel shows both


def _owned(request, kind, object_id):
    if kind not in MODELS:
        return None
    return MODELS[kind].objects.filter(pk=object_id, owner=request.user).first()


@require_http_methods(["GET", "POST"])
def object_access(request, kind, object_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    item = _owned(request, kind, object_id)
    if item is None:
        return JsonResponse({"error": "Not found"}, status=404)
    grants = ObjectAccess.objects.filter(kind=kind, object_id=item.pk).select_related("user", "group")
    if request.method == "GET":
        return JsonResponse({"grants": [_grant_json(grant) for grant in grants]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    level = body.get("level", ObjectAccess.Level.VIEW)
    if level not in ObjectAccess.Level.values:
        return JsonResponse({"error": "Choose view or edit"}, status=400)
    has_user, has_group = body.get("user_id") is not None, body.get("group_id") is not None
    raw = body.get("user_id") if has_user else body.get("group_id")
    if has_user == has_group or not isinstance(raw, int) or isinstance(raw, bool):
        return JsonResponse({"error": "Choose one person or one group"}, status=400)
    if has_user:
        target = User.objects.filter(pk=raw, is_active=True).first()
        if target is None:
            return JsonResponse({"error": "Person not found"}, status=400)
        if target.pk == request.user.pk:
            return JsonResponse({"error": OWN_ALREADY_ERRORS[kind]}, status=400)
        lookup = {"user": target}
    else:
        target = Group.objects.filter(pk=raw).first()
        if target is None:
            return JsonResponse({"error": "Group not found"}, status=400)
        lookup = {"group": target}
    try:
        with transaction.atomic():
            grant, created = ObjectAccess.objects.update_or_create(kind=kind, object_id=item.pk, **lookup,
                                                                   defaults={"owner": request.user, "level": level})
    except IntegrityError:
        return JsonResponse({"error": "Could not share it; try again"}, status=409)
    grant = ObjectAccess.objects.select_related("user", "group").get(pk=grant.pk)
    return JsonResponse(_grant_json(grant), status=201 if created else 200)


@require_http_methods(["PATCH", "DELETE"])
def object_access_detail(request, kind, object_id, grant_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    item = _owned(request, kind, object_id)
    grant = ObjectAccess.objects.select_related("user", "group").filter(pk=grant_id, kind=kind, object_id=item.pk).first() if item else None
    if grant is None:
        return JsonResponse({"error": "Access not found"}, status=404)
    if request.method == "DELETE":
        grant.delete()
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None or body.get("level") not in ObjectAccess.Level.values:
        return JsonResponse({"error": "Choose view or edit"}, status=400)
    grant.level = body["level"]
    grant.save(update_fields=["level"])
    return JsonResponse(_grant_json(grant))


def _shared_json(item, level, kind):
    base = {"id": str(item.pk), "name": item.name, "level": level,
            "owner": {"id": item.owner_id, "name": item.owner.get_full_name() or item.owner.username}}
    if kind == "tag":
        base.update(color=item.color, description=item.description)
    if kind == "saved_view":
        from .metadata_views import _saved_view_json

        base.update({key: value for key, value in _saved_view_json(item).items() if key not in base})
    return base


@require_http_methods(["GET"])
def shared_filing(request):
    """Everything others shared with me, by kind."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    keys = {"tag": "tags", "correspondent": "correspondents", "document_type": "document_types", "saved_view": "saved_views"}
    return JsonResponse({keys[kind]: sorted((_shared_json(item, level, kind) for item, level in shared_objects(request.user, kind).items()),
                                            key=lambda value: value["name"].casefold()) for kind in MODELS})


@require_http_methods(["PATCH"])
def shared_filing_edit(request, kind, object_id):
    """A recipient with edit access renames or adjusts a shared object. Deleting stays with the owner."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    if kind not in MODELS:
        return JsonResponse({"error": "Not found"}, status=404)
    levels = shared_objects(request.user, kind)
    item = next((candidate for candidate in levels if candidate.pk == object_id), None)
    if item is None:
        return JsonResponse({"error": "Not found"}, status=404)
    if levels[item] != EDIT:
        return JsonResponse({"error": "You can use this but not change it"}, status=403)
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    allowed = {"tag": {"name", "color", "description"}, "correspondent": {"name"}, "document_type": {"name"},
               "saved_view": {"name", "query", "date_from", "date_to"}}[kind]
    if set(body) - allowed:
        return JsonResponse({"error": SHARED_EDIT_ERRORS[kind]}, status=403)
    model = MODELS[kind]
    with transaction.atomic():
        item = model.objects.select_for_update().get(pk=item.pk)
        if "name" in body:
            name = body["name"].strip() if isinstance(body["name"], str) else ""
            if not name or len(name) > 100 or model.objects.filter(owner=item.owner, name__iexact=name).exclude(pk=item.pk).exists():
                return JsonResponse({"error": "Invalid or duplicate name"}, status=400)
            item.name = name
        if "color" in body:
            from .metadata_views import COLOR

            if not isinstance(body["color"], str) or not COLOR.fullmatch(body["color"]):
                return JsonResponse({"error": "Invalid tag color"}, status=400)
            item.color = body["color"]
        if "description" in body:
            if not isinstance(body["description"], str) or len(body["description"]) > 500:
                return JsonResponse({"error": "Invalid description"}, status=400)
            item.description = body["description"].strip()
        if "query" in body:
            if not isinstance(body["query"], str) or len(body["query"]) > 200:
                return JsonResponse({"error": "Invalid search"}, status=400)
            item.query = body["query"].strip()
        for key in ("date_from", "date_to"):
            if key in body:
                try:
                    setattr(item, key, date.fromisoformat(body[key]) if body[key] else None)
                except (TypeError, ValueError):
                    return JsonResponse({"error": "Use dates like 2026-01-31"}, status=400)
        item.save()
    return JsonResponse(_shared_json(model.objects.select_related("owner").get(pk=item.pk), EDIT, kind))
