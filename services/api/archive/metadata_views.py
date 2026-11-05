import json
import logging
import re
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import ClassificationRule, Correspondent, DocumentType, FilingRule, Tag
from .tasks import reclassify_filing_candidates, reclassify_tag_candidates

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


def _queue_tag_candidates(owner_id, tag_id, phrases, deleted=False):
    try:
        reclassify_tag_candidates.delay(owner_id, str(tag_id), phrases, deleted)
    except Exception:
        logger.exception("Could not queue tag recheck for owner %s", owner_id)


def _queue_filing_candidates(owner_id, kind, target_id, pattern, field, deleted=False):
    try:
        reclassify_filing_candidates.delay(owner_id, kind, str(target_id), pattern, field, deleted)
    except Exception:
        logger.exception("Could not queue filing recheck for owner %s", owner_id)


def _tag_json(tag):
    return {
        "id": str(tag.id), "name": tag.name, "color": tag.color,
        "description": tag.description,
        "parent_id": str(tag.parent_id) if tag.parent_id else None,
    }


def _vocabulary_json(item):
    return {"id": str(item.id), "name": item.name}


def _vocabulary(request, model, key):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        return JsonResponse({key: [_vocabulary_json(item) for item in model.objects.filter(owner=request.user)]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = body.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return JsonResponse({"error": "Name must be 1–100 characters"}, status=400)
    try:
        with transaction.atomic():
            item = model.objects.create(owner=request.user, name=name.strip())
    except IntegrityError:
        return JsonResponse({"error": "This name already exists"}, status=409)
    return JsonResponse(_vocabulary_json(item), status=201)


def _vocabulary_detail(request, model, item_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    item = model.objects.filter(pk=item_id, owner=request.user).first()
    if item is None:
        return JsonResponse({"error": "Filing item not found"}, status=404)
    if request.method == "DELETE":
        try:
            item.delete()
        except ProtectedError:
            return JsonResponse({"error": "Remove this from documents before deleting it"}, status=409)
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = body.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return JsonResponse({"error": "Name must be 1–100 characters"}, status=400)
    item.name = name.strip()
    try:
        with transaction.atomic():
            item.save(update_fields=["name"])
    except IntegrityError:
        return JsonResponse({"error": "This name already exists"}, status=409)
    return JsonResponse(_vocabulary_json(item))


@require_http_methods(["GET", "POST"])
def correspondents(request):
    return _vocabulary(request, Correspondent, "correspondents")


@require_http_methods(["PATCH", "DELETE"])
def correspondent_detail(request, correspondent_id):
    return _vocabulary_detail(request, Correspondent, correspondent_id)


@require_http_methods(["GET", "POST"])
def document_types(request):
    return _vocabulary(request, DocumentType, "document_types")


@require_http_methods(["PATCH", "DELETE"])
def document_type_detail(request, type_id):
    return _vocabulary_detail(request, DocumentType, type_id)


def _filing_rule_json(rule):
    target = rule.correspondent if rule.kind == FilingRule.Kind.CORRESPONDENT else rule.document_type
    return {
        "id": str(rule.id), "kind": rule.kind, "target_id": str(target.id), "target_name": target.name,
        "pattern": rule.pattern, "field": rule.field, "enabled": rule.enabled,
    }


@require_http_methods(["GET", "POST"])
def filing_rules(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        kind = request.GET.get("kind")
        if kind is not None and kind not in FilingRule.Kind.values:
            return JsonResponse({"error": "Invalid filing kind"}, status=400)
        queryset = FilingRule.objects.filter(owner=request.user).select_related("correspondent", "document_type")
        if kind:
            queryset = queryset.filter(kind=kind)
        return JsonResponse({"rules": [_filing_rule_json(rule) for rule in queryset]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    kind = body.get("kind")
    model = Correspondent if kind == FilingRule.Kind.CORRESPONDENT else DocumentType if kind == FilingRule.Kind.DOCUMENT_TYPE else None
    if model is None:
        return JsonResponse({"error": "Choose a correspondent or document type"}, status=400)
    try:
        target_id = UUID(body.get("target_id", ""))
    except (TypeError, ValueError, AttributeError):
        return JsonResponse({"error": "Invalid target ID"}, status=400)
    target = model.objects.filter(pk=target_id, owner=request.user).first()
    pattern = body.get("pattern")
    field = body.get("field", FilingRule.Field.EITHER)
    if target is None or not isinstance(pattern, str) or not pattern.strip() or len(pattern.strip()) > 200 or field not in FilingRule.Field.values:
        return JsonResponse({"error": "Choose an owned target, phrase, and field"}, status=400)
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            if FilingRule.objects.filter(owner=request.user, kind=kind, pattern__iexact=pattern.strip()).exists():
                return JsonResponse({"error": "This phrase already files another name"}, status=409)
            rule = FilingRule.objects.create(
                owner=request.user, kind=kind, pattern=pattern.strip(), field=field,
                correspondent=target if kind == FilingRule.Kind.CORRESPONDENT else None,
                document_type=target if kind == FilingRule.Kind.DOCUMENT_TYPE else None,
            )
    except IntegrityError:
        return JsonResponse({"error": "This matching phrase already exists"}, status=409)
    _queue_filing_candidates(request.user.id, kind, target.id, rule.pattern, rule.field)
    return JsonResponse(_filing_rule_json(rule), status=201)


@require_http_methods(["DELETE"])
def filing_rule_detail(request, rule_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    with transaction.atomic():
        get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
        rule = FilingRule.objects.filter(pk=rule_id, owner=request.user).first()
        if rule is None:
            return JsonResponse({"error": "Filing rule not found"}, status=404)
        kind = rule.kind
        target_id = rule.correspondent_id if kind == FilingRule.Kind.CORRESPONDENT else rule.document_type_id
        pattern = rule.pattern
        field = rule.field
        rule.delete()
    _queue_filing_candidates(request.user.id, kind, target_id, pattern, field, deleted=True)
    return JsonResponse({"deleted": True})


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
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            tag = Tag.objects.create(owner=request.user, name=name, color=color, description=description, parent=parent)
            for keyword in dict.fromkeys(value.strip() for value in keywords):
                ClassificationRule.objects.create(owner=request.user, tag=tag, pattern=keyword)
    except IntegrityError:
        return JsonResponse({"error": "A tag with that name already exists"}, status=409)
    if keywords:
        _queue_tag_candidates(request.user.id, tag.id, [{"pattern": keyword, "field": "either"} for keyword in keywords])
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
            with transaction.atomic():
                get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
                tag.delete()
        except ProtectedError:
            return JsonResponse({"error": "Move or delete child tags first"}, status=409)
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
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            rule = ClassificationRule.objects.create(owner=request.user, tag=tag, pattern=pattern.strip(), field=field)
    except IntegrityError:
        return JsonResponse({"error": "This rule already exists"}, status=409)
    _queue_tag_candidates(request.user.id, tag.id, [{"pattern": rule.pattern, "field": rule.field}])
    return JsonResponse({"id": str(rule.id), "tag_id": str(tag.id), "tag_name": tag.name, "pattern": rule.pattern, "field": rule.field, "enabled": True}, status=201)


@require_http_methods(["DELETE"])
def rule_detail(request, rule_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    with transaction.atomic():
        get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
        rule = ClassificationRule.objects.filter(pk=rule_id, owner=request.user).first()
        if rule is None:
            return JsonResponse({"error": "Rule not found"}, status=404)
        tag_id = rule.tag_id
        rule.delete()
    _queue_tag_candidates(request.user.id, tag_id, [], deleted=True)
    return JsonResponse({"deleted": True})
