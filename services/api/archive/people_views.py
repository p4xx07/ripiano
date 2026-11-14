"""People, groups, and who can open a document.

Every signed-in person can see the active people and the groups, so they can share a document.
Only an instance admin adds people, resets passwords, turns accounts off, and edits groups.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Document, DocumentAccess
from .security_views import _password_ok

User = get_user_model()


def _signed_in(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _admin(request):
    denied = _signed_in(request)
    if denied:
        return denied
    if not request.user.is_superuser:
        return JsonResponse({"error": "Only an admin can manage people and groups"}, status=403)
    return None


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _int_ids(raw):
    if not isinstance(raw, list) or len(raw) > 500 or not all(isinstance(item, int) and not isinstance(item, bool) for item in raw):
        return None
    return set(raw)


def _person_json(user, admin):
    payload = {"id": user.pk, "username": user.get_username(), "name": user.get_full_name()}
    if admin:
        payload.update(
            is_active=user.is_active, is_admin=user.is_superuser,
            last_login=user.last_login.isoformat() if user.last_login else None,
            groups=sorted(group.pk for group in user.groups.all()),
        )
    return payload


def _group_json(group, admin):
    payload = {"id": group.pk, "name": group.name}
    if admin:
        payload["member_ids"] = sorted(member.pk for member in group.user_set.all())
    return payload


def _password_error(password, user=None):
    if not isinstance(password, str) or len(password) < 12:
        return "Use a password of at least 12 characters"
    try:
        validate_password(password, user)
    except ValidationError as exc:
        return " ".join(exc.messages)
    return None


@require_http_methods(["GET", "POST"])
def people(request):
    if request.method == "GET":
        denied = _signed_in(request)
        if denied:
            return denied
        admin = request.user.is_superuser
        users = User.objects.order_by("username").prefetch_related("groups")
        if not admin:
            users = users.filter(is_active=True)
        groups = Group.objects.order_by("name").prefetch_related("user_set")
        return JsonResponse({
            "people": [_person_json(user, admin) for user in users[:1000]],
            "groups": [_group_json(group, admin) for group in groups[:500]],
            "admin": admin,
        })
    denied = _admin(request)
    if denied:
        return denied
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    ok, refused = _password_ok(request, body.get("current_password"))
    if not ok:
        return refused
    username = str(body.get("username", "")).strip()
    if not username or len(username) > 150:
        return JsonResponse({"error": "Choose a username of up to 150 characters"}, status=400)
    try:
        User.username_validator(username)
    except ValidationError:
        return JsonResponse({"error": "Use letters, numbers, and @ . + - _ in the username"}, status=400)
    candidate = User(username=username)
    error = _password_error(body.get("password"), candidate)
    if error:
        return JsonResponse({"error": error}, status=400)
    group_ids = _int_ids(body.get("groups", []))
    if group_ids is None:
        return JsonResponse({"error": "Groups must be a list of group IDs"}, status=400)
    groups = list(Group.objects.filter(pk__in=group_ids))
    if len(groups) != len(group_ids):
        return JsonResponse({"error": "Group not found"}, status=400)
    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"error": "That username is taken"}, status=409)
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=username, password=body["password"], first_name=str(body.get("name", "")).strip()[:150])
            user.groups.set(groups)
    except IntegrityError:
        return JsonResponse({"error": "That username is taken"}, status=409)
    return JsonResponse(_person_json(user, True), status=201)


@transaction.atomic
@require_http_methods(["PATCH"])
def person_detail(request, person_id):
    denied = _admin(request)
    if denied:
        return denied
    user = User.objects.select_for_update().filter(pk=person_id).first()
    if user is None:
        return JsonResponse({"error": "Person not found"}, status=404)
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if "password" in body or "is_active" in body:
        # Who can sign in is changed only after the admin confirms their own password.
        ok, refused = _password_ok(request, body.get("current_password"))
        if not ok:
            return refused
    if "password" in body and user.pk == request.user.pk:
        return JsonResponse({"error": "Change your own password under Security"}, status=400)
    if "password" in body and user.is_superuser:
        return JsonResponse({"error": "Another admin changes their own password"}, status=403)
    fields = []
    if "is_active" in body:
        if not isinstance(body["is_active"], bool):
            return JsonResponse({"error": "Choose on or off"}, status=400)
        if user.pk == request.user.pk and not body["is_active"]:
            return JsonResponse({"error": "You can't turn off your own account"}, status=400)
        # Lock every active admin, so two admins can't turn each other off at the same moment.
        admins = list(User.objects.select_for_update().filter(is_superuser=True, is_active=True).values_list("pk", flat=True))
        if user.is_superuser and not body["is_active"] and not [pk for pk in admins if pk != user.pk]:
            return JsonResponse({"error": "Keep at least one active admin"}, status=400)
        user.is_active = body["is_active"]
        fields.append("is_active")
    if "name" in body:
        if not isinstance(body["name"], str) or len(body["name"].strip()) > 150:
            return JsonResponse({"error": "Name must be at most 150 characters"}, status=400)
        user.first_name = body["name"].strip()
        fields.append("first_name")
    if "password" in body:
        error = _password_error(body["password"], user)
        if error:
            return JsonResponse({"error": error}, status=400)
        user.set_password(body["password"])
        fields.append("password")
    groups = None
    if "groups" in body:
        group_ids = _int_ids(body["groups"])
        if group_ids is None:
            return JsonResponse({"error": "Groups must be a list of group IDs"}, status=400)
        groups = list(Group.objects.filter(pk__in=group_ids))
        if len(groups) != len(group_ids):
            return JsonResponse({"error": "Group not found"}, status=400)
    if fields:
        # Saving the password through save() fires the signal that ends the person's API tokens.
        user.save(update_fields=fields)
    if groups is not None:
        user.groups.set(groups)
    return JsonResponse(_person_json(user, True))


@require_http_methods(["POST"])
def groups(request):
    denied = _admin(request)
    if denied:
        return denied
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    return _save_group(Group(), body)


@transaction.atomic
@require_http_methods(["PATCH", "DELETE"])
def group_detail(request, group_id):
    denied = _admin(request)
    if denied:
        return denied
    group = Group.objects.select_for_update().filter(pk=group_id).first()
    if group is None:
        return JsonResponse({"error": "Group not found"}, status=404)
    if request.method == "DELETE":
        # Documents shared with the group stop being visible to its members.
        group.delete()
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    return _save_group(group, body)


def _save_group(group, body):
    creating = group.pk is None
    if creating or "name" in body:
        name = body.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 150:
            return JsonResponse({"error": "Group name must be 1–150 characters"}, status=400)
        group.name = name.strip()
        if Group.objects.filter(name__iexact=group.name).exclude(pk=group.pk).exists():
            return JsonResponse({"error": "A group with that name exists"}, status=409)
    members = None
    if "member_ids" in body:
        member_ids = _int_ids(body["member_ids"])
        if member_ids is None:
            return JsonResponse({"error": "Members must be a list of person IDs"}, status=400)
        members = list(User.objects.filter(pk__in=member_ids))
        if len(members) != len(member_ids):
            return JsonResponse({"error": "Person not found"}, status=400)
    try:
        with transaction.atomic():
            group.save()
            if members is not None:
                group.user_set.set(members)
    except IntegrityError:
        return JsonResponse({"error": "A group with that name exists"}, status=409)
    group = Group.objects.prefetch_related("user_set").get(pk=group.pk)
    return JsonResponse(_group_json(group, True), status=201 if creating else 200)


def _grant_json(grant):
    if grant.user_id:
        target = {"kind": "person", "id": grant.user_id, "name": grant.user.get_username(), "active": grant.user.is_active}
    else:
        target = {"kind": "group", "id": grant.group_id, "name": grant.group.name, "active": True}
    return {"id": str(grant.id), "level": grant.level, "target": target, "created_at": grant.created_at.isoformat()}


def _owned_document(request, document_id, lock=False):
    queryset = Document.objects.select_for_update() if lock else Document.objects
    return queryset.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()


@transaction.atomic
@require_http_methods(["GET", "POST"])
def document_access(request, document_id):
    denied = _signed_in(request)
    if denied:
        return denied
    document = _owned_document(request, document_id, lock=request.method == "POST")
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    if request.method == "GET":
        grants = document.access_grants.select_related("user", "group")
        return JsonResponse({"grants": [_grant_json(grant) for grant in grants]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    level = body.get("level", DocumentAccess.Level.VIEW)
    if level not in DocumentAccess.Level.values:
        return JsonResponse({"error": "Choose view or edit"}, status=400)
    has_user, has_group = body.get("user_id") is not None, body.get("group_id") is not None
    if has_user == has_group:
        return JsonResponse({"error": "Choose one person or one group"}, status=400)
    raw = body.get("user_id") if has_user else body.get("group_id")
    if not isinstance(raw, int) or isinstance(raw, bool):
        return JsonResponse({"error": "Invalid person or group"}, status=400)
    if has_user:
        target = User.objects.filter(pk=raw, is_active=True).first()
        if target is None:
            return JsonResponse({"error": "Person not found"}, status=400)
        if target.pk == request.user.pk:
            return JsonResponse({"error": "You already own this document"}, status=400)
        lookup = {"user": target}
    else:
        target = Group.objects.filter(pk=raw).first()
        if target is None:
            return JsonResponse({"error": "Group not found"}, status=400)
        lookup = {"group": target}
    if document.access_grants.count() >= 200 and not document.access_grants.filter(**lookup).exists():
        return JsonResponse({"error": "A document can be shared with up to 200 people or groups"}, status=400)
    grant, created = DocumentAccess.objects.update_or_create(document=document, **lookup, defaults={"level": level})
    grant = DocumentAccess.objects.select_related("user", "group").get(pk=grant.pk)
    return JsonResponse(_grant_json(grant), status=201 if created else 200)


@transaction.atomic
@require_http_methods(["PATCH", "DELETE"])
def document_access_detail(request, document_id, grant_id):
    denied = _signed_in(request)
    if denied:
        return denied
    document = _owned_document(request, document_id, lock=True)
    grant = document.access_grants.select_related("user", "group").filter(pk=grant_id).first() if document else None
    if grant is None:
        return JsonResponse({"error": "Access not found"}, status=404)
    if request.method == "DELETE":
        grant.delete()
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None or body.get("level") not in DocumentAccess.Level.values:
        return JsonResponse({"error": "Choose view or edit"}, status=400)
    grant.level = body["level"]
    grant.save(update_fields=["level"])
    return JsonResponse(_grant_json(grant))
