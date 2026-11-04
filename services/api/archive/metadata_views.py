import json
import logging
import re
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import ClassificationRule, Tag
from .tasks import reclassify_owner

logger = logging.getLogger(__name__)
COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


def _body(request):
    try:
        value = json.loads(request.body)
        return value if isinstance(value, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _unauthorized(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _queue_reclassification(owner_id):
    try:
        reclassify_owner.delay(owner_id)
    except Exception:
        logger.exception("Could not queue rule reclassification for owner %s", owner_id)


def _tag_json(tag):
    return {
        "id": str(tag.id), "name": tag.name, "color": tag.color,
        "description": tag.description,
        "parent_id": str(tag.parent_id) if tag.parent_id else None,
    }


@require_http_methods(["GET", "POST"])
def tags(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        return JsonResponse({"tags": [_tag_json(tag) for tag in Tag.objects.filter(owner=request.user)]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = str(body.get("name", "")).strip()
    color = str(body.get("color", "#5d8b66"))
    description = str(body.get("description", "")).strip()
    keywords = body.get("keywords", [])
    if not name or len(name) > 100 or not COLOR.fullmatch(color) or len(description) > 500:
        return JsonResponse({"error": "Invalid tag name, color, or description"}, status=400)
    if not isinstance(keywords, list) or len(keywords) > 20 or any(not isinstance(value, str) or not value.strip() or len(value.strip()) > 200 for value in keywords):
        return JsonResponse({"error": "Keywords must be a list of up to 20 short phrases"}, status=400)
    parent = None
    if body.get("parent_id"):
        try:
            parent = Tag.objects.filter(pk=UUID(str(body["parent_id"])), owner=request.user).first()
        except ValueError:
            pass
        if parent is None:
            return JsonResponse({"error": "Parent tag not found"}, status=400)
    if Tag.objects.filter(owner=request.user, name__iexact=name).exists():
        return JsonResponse({"error": "A tag with that name already exists"}, status=409)
    try:
        with transaction.atomic():
            tag = Tag.objects.create(owner=request.user, name=name, color=color, description=description, parent=parent)
            for keyword in dict.fromkeys(value.strip() for value in keywords):
                ClassificationRule.objects.create(owner=request.user, tag=tag, pattern=keyword)
    except IntegrityError:
        return JsonResponse({"error": "A tag with that name already exists"}, status=409)
    if keywords:
        _queue_reclassification(request.user.id)
    return JsonResponse(_tag_json(tag), status=201)


@require_http_methods(["PATCH", "DELETE"])
def tag_detail(request, tag_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    tag = Tag.objects.filter(pk=tag_id, owner=request.user).first()
    if tag is None:
        return JsonResponse({"error": "Tag not found"}, status=404)
    if request.method == "DELETE":
        try:
            tag.delete()
        except ProtectedError:
            return JsonResponse({"error": "Move or delete child tags first"}, status=409)
        _queue_reclassification(request.user.id)
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    changes = []
    if "name" in body:
        name = str(body["name"]).strip()
        if not name or len(name) > 100 or Tag.objects.filter(owner=request.user, name__iexact=name).exclude(pk=tag.id).exists():
            return JsonResponse({"error": "Invalid or duplicate tag name"}, status=400)
        tag.name = name
        changes.append("name")
    if "color" in body:
        if not isinstance(body["color"], str) or not COLOR.fullmatch(body["color"]):
            return JsonResponse({"error": "Invalid tag color"}, status=400)
        tag.color = body["color"]
        changes.append("color")
    if "description" in body:
        if not isinstance(body["description"], str) or len(body["description"]) > 500:
            return JsonResponse({"error": "Invalid tag description"}, status=400)
        tag.description = body["description"].strip()
        changes.append("description")
    try:
        if changes:
            tag.save(update_fields=changes)
    except IntegrityError:
        return JsonResponse({"error": "Duplicate tag name"}, status=409)
    return JsonResponse(_tag_json(tag))


@require_http_methods(["GET", "POST"])
def rules(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        return JsonResponse({"rules": [{
            "id": str(rule.id), "tag_id": str(rule.tag_id), "tag_name": rule.tag.name,
            "pattern": rule.pattern, "field": rule.field, "enabled": rule.enabled,
        } for rule in ClassificationRule.objects.filter(owner=request.user).select_related("tag")]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    try:
        tag = Tag.objects.filter(pk=UUID(str(body.get("tag_id", ""))), owner=request.user).first()
    except ValueError:
        tag = None
    pattern = body.get("pattern", "")
    field = body.get("field", ClassificationRule.Field.EITHER)
    if tag is None or not isinstance(pattern, str) or not pattern.strip() or len(pattern.strip()) > 200 or field not in ClassificationRule.Field.values:
        return JsonResponse({"error": "Choose a tag, phrase, and valid field"}, status=400)
    try:
        rule = ClassificationRule.objects.create(owner=request.user, tag=tag, pattern=pattern.strip(), field=field)
    except IntegrityError:
        return JsonResponse({"error": "This rule already exists"}, status=409)
    _queue_reclassification(request.user.id)
    return JsonResponse({"id": str(rule.id), "tag_id": str(tag.id), "tag_name": tag.name, "pattern": rule.pattern, "field": rule.field, "enabled": True}, status=201)


@require_http_methods(["DELETE"])
def rule_detail(request, rule_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    rule = ClassificationRule.objects.filter(pk=rule_id, owner=request.user).first()
    if rule is None:
        return JsonResponse({"error": "Rule not found"}, status=404)
    rule.delete()
    _queue_reclassification(request.user.id)
    return JsonResponse({"deleted": True})
