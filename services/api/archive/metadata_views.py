import io
import json
import logging
import re
from datetime import date
from uuid import UUID

import segno
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from django.views.decorators.http import require_http_methods

from .models import ClassificationRule, Correspondent, CustomField, DocumentType, FilingRule, SavedView, Tag
from .custom_field_views import normalize_filter_range, normalize_filter_value
from .classification import validate_pattern
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


def _queue_filing_candidates(owner_id, kind, target_id, pattern, field, deleted=False, match="phrase"):
    try:
        reclassify_filing_candidates.delay(owner_id, kind, str(target_id), pattern, field, deleted, match=match)
    except Exception:
        logger.exception("Could not queue filing recheck for owner %s", owner_id)


def _tag_json(tag):
    return {
        "id": str(tag.id), "name": tag.name, "color": tag.color,
        "description": tag.description,
        "barcode_value": tag.barcode_value,
        "parent_id": str(tag.parent_id) if tag.parent_id else None,
    }


def _tag_barcode_value(raw):
    if not isinstance(raw, str):
        raise ValueError("Barcode value must be text")
    value = raw.strip()
    if len(value) > 100 or not value.isascii() or not value.isprintable():
        raise ValueError("Barcode value must be printable ASCII text up to 100 characters")
    if (value and (value.casefold() == settings.RIPIANO_BARCODE_SEPARATOR.casefold()
                   or re.fullmatch(rf"{re.escape(settings.RIPIANO_BARCODE_ASN_PREFIX)}\s*0*\d{{1,9}}", value, re.IGNORECASE)
                   or value.casefold().startswith(settings.RIPIANO_BARCODE_TAG_PREFIX.casefold()))):
        raise ValueError("This barcode is reserved for a separator, archive number, or tag name")
    return value


def _tag_parent(owner, raw, tag_id=None):
    if raw in (None, ""):
        return None
    try:
        parent = Tag.objects.filter(pk=UUID(str(raw)), owner=owner).first()
    except (TypeError, ValueError):
        parent = None
    if parent is None:
        raise ValueError("Parent tag not found")
    seen = set()
    ancestor = parent
    while ancestor is not None:
        if ancestor.pk == tag_id or ancestor.pk in seen:
            raise ValueError("A tag cannot be inside itself or one of its children")
        seen.add(ancestor.pk)
        ancestor = ancestor.parent
    return parent


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


def _saved_view_json(view):
    return {
        "id": str(view.id), "name": view.name, "query": view.query,
        "tag_id": str(view.tag_id) if view.tag_id else None,
        "correspondent_id": str(view.correspondent_id) if view.correspondent_id else None,
        "document_type_id": str(view.document_type_id) if view.document_type_id else None,
        "copy_status": view.copy_status,
        "custom_field_id": str(view.custom_field_id) if view.custom_field_id else None,
        "custom_value": view.custom_value,
        "custom_min": view.custom_min,
        "custom_max": view.custom_max,
        "date_from": view.date_from.isoformat() if view.date_from else None,
        "date_to": view.date_to.isoformat() if view.date_to else None,
    }


def _saved_view_values(body, owner, current=None):
    name = body.get("name", current.name if current else None)
    query = body.get("query", current.query if current else "")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise ValueError("Name must be 1–100 characters")
    if not isinstance(query, str) or len(query.strip()) > 200:
        raise ValueError("Search text must be at most 200 characters")
    values = {"name": name.strip(), "query": query.strip()}
    copy_status = body.get("copy_status", current.copy_status if current else "")
    if copy_status not in ("", "paper", "virtual", "missing"):
        raise ValueError("Choose a valid paper-copy filter")
    values["copy_status"] = copy_status
    for key, model in (("tag", Tag), ("correspondent", Correspondent), ("document_type", DocumentType), ("custom_field", CustomField)):
        raw = body.get(f"{key}_id", getattr(current, f"{key}_id") if current else None)
        if raw in (None, ""):
            values[key] = None
            continue
        try:
            item = model.objects.filter(pk=UUID(str(raw)), owner=owner).first()
        except (TypeError, ValueError, AttributeError):
            item = None
        if item is None:
            raise ValueError(f"{key.replace('_', ' ').title()} not found")
        values[key] = item
    for key in ("date_from", "date_to"):
        raw = body.get(key, getattr(current, key) if current else None)
        if raw in (None, ""):
            values[key] = None
        else:
            try:
                if isinstance(raw, str):
                    values[key] = date.fromisoformat(raw)
                elif isinstance(raw, date):
                    values[key] = raw
                else:
                    raise ValueError
            except ValueError as exc:
                raise ValueError("Invalid document date") from exc
    if values["date_from"] and values["date_to"] and values["date_from"] > values["date_to"]:
        raise ValueError("Start date must be before end date")
    custom_value = body.get("custom_value", current.custom_value if current else "")
    if not isinstance(custom_value, str) or len(custom_value.strip()) > 500:
        raise ValueError("Custom field value must be at most 500 characters")
    values["custom_value"] = custom_value.strip()
    if values["custom_value"]:
        if values["custom_field"] is None:
            raise ValueError("Choose a custom field before its value")
        normalize_filter_value(values["custom_field"], values["custom_value"])
    bounds = []
    for key in ("custom_min", "custom_max"):
        raw = body.get(key, getattr(current, key) if current else "")
        if not isinstance(raw, str) or len(raw.strip()) > 500:
            raise ValueError("Custom field range value must be at most 500 characters")
        bounds.append(raw.strip())
    if values["custom_value"] and any(bounds):
        raise ValueError("Use an exact value or a range")
    values["custom_min"], values["custom_max"] = normalize_filter_range(values["custom_field"], *bounds)
    return values


@require_http_methods(["GET", "POST"])
def saved_views(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        return JsonResponse({"views": [_saved_view_json(view) for view in SavedView.objects.filter(owner=request.user)]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            values = _saved_view_values(body, request.user)
            view = SavedView.objects.create(owner=request.user, **values)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "A saved search with this name already exists"}, status=409)
    return JsonResponse(_saved_view_json(view), status=201)


@require_http_methods(["PATCH", "DELETE"])
def saved_view_detail(request, view_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    view = SavedView.objects.filter(pk=view_id, owner=request.user).first()
    if view is None:
        return JsonResponse({"error": "Saved search not found"}, status=404)
    if request.method == "DELETE":
        view.delete()
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            view = SavedView.objects.select_for_update().filter(pk=view_id, owner=request.user).first()
            if view is None:
                return JsonResponse({"error": "Saved search not found"}, status=404)
            values = _saved_view_values(body, request.user, view)
            for key, value in values.items():
                setattr(view, key, value)
            view.save(update_fields=list(values))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "A saved search with this name already exists"}, status=409)
    return JsonResponse(_saved_view_json(view))


def _filing_rule_json(rule):
    target = rule.correspondent if rule.kind == FilingRule.Kind.CORRESPONDENT else rule.document_type
    return {
        "id": str(rule.id), "kind": rule.kind, "target_id": str(target.id), "target_name": target.name,
        "pattern": rule.pattern, "field": rule.field, "match": rule.match, "enabled": rule.enabled,
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
    match = body.get("match", "phrase")
    if target is None or not isinstance(pattern, str) or not pattern.strip() or len(pattern.strip()) > 200 or field not in FilingRule.Field.values:
        return JsonResponse({"error": "Choose an owned target, phrase, and field"}, status=400)
    problem = validate_pattern(pattern.strip(), match) if isinstance(match, str) else "Choose how the rule matches"
    if problem:
        return JsonResponse({"error": problem}, status=400)
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            same = FilingRule.objects.filter(owner=request.user, kind=kind, match=match)
            same = same.filter(pattern=pattern.strip()) if match == "regex" else same.filter(pattern__iexact=pattern.strip())
            if same.exists():
                return JsonResponse({"error": "A rule with this text and matching already exists"}, status=409)
            rule = FilingRule.objects.create(
                owner=request.user, kind=kind, pattern=pattern.strip(), field=field, match=match,
                correspondent=target if kind == FilingRule.Kind.CORRESPONDENT else None,
                document_type=target if kind == FilingRule.Kind.DOCUMENT_TYPE else None,
            )
    except IntegrityError:
        return JsonResponse({"error": "This matching phrase already exists"}, status=409)
    _queue_filing_candidates(request.user.id, kind, target.id, rule.pattern, rule.field, match=rule.match)
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
    try:
        barcode_value = _tag_barcode_value(body.get("barcode_value", ""))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    keywords = body.get("keywords", [])
    if not name or len(name) > 100 or not COLOR.fullmatch(color) or len(description) > 500:
        return JsonResponse({"error": "Invalid tag name, color, or description"}, status=400)
    if not isinstance(keywords, list) or len(keywords) > 20 or any(not isinstance(value, str) or not value.strip() or len(value.strip()) > 200 for value in keywords):
        return JsonResponse({"error": "Keywords must be a list of up to 20 short phrases"}, status=400)
    try:
        parent = _tag_parent(request.user, body.get("parent_id"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    if Tag.objects.filter(owner=request.user, name__iexact=name).exists():
        return JsonResponse({"error": "A tag with that name already exists"}, status=409)
    if barcode_value and Tag.objects.filter(owner=request.user, barcode_value__iexact=barcode_value).exists():
        return JsonResponse({"error": "Another tag already uses that barcode"}, status=409)
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            tag = Tag.objects.create(owner=request.user, name=name, color=color, description=description, barcode_value=barcode_value, parent=parent)
            for keyword in dict.fromkeys(value.strip() for value in keywords):
                ClassificationRule.objects.create(owner=request.user, tag=tag, pattern=keyword)
    except IntegrityError:
        return JsonResponse({"error": "A tag name or barcode is already in use"}, status=409)
    if keywords:
        _queue_tag_candidates(request.user.id, tag.id, [{"pattern": keyword, "field": "either"} for keyword in keywords])
    return JsonResponse(_tag_json(tag), status=201)


@require_http_methods(["PATCH", "DELETE"])
def tag_detail(request, tag_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "DELETE":
        tag = Tag.objects.filter(pk=tag_id, owner=request.user).first()
        if tag is None:
            return JsonResponse({"error": "Tag not found"}, status=404)
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
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            tag = Tag.objects.select_for_update().filter(pk=tag_id, owner=request.user).first()
            if tag is None:
                return JsonResponse({"error": "Tag not found"}, status=404)
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
            if "barcode_value" in body:
                try:
                    value = _tag_barcode_value(body["barcode_value"])
                except ValueError as exc:
                    return JsonResponse({"error": str(exc)}, status=400)
                if value and Tag.objects.filter(owner=request.user, barcode_value__iexact=value).exclude(pk=tag.pk).exists():
                    return JsonResponse({"error": "Another tag already uses that barcode"}, status=409)
                tag.barcode_value = value
                changes.append("barcode_value")
            if "parent_id" in body:
                try:
                    tag.parent = _tag_parent(request.user, body["parent_id"], tag.id)
                except ValueError as exc:
                    return JsonResponse({"error": str(exc)}, status=400)
                changes.append("parent")
            if changes:
                tag.save(update_fields=changes)
    except IntegrityError:
        return JsonResponse({"error": "A tag name or barcode is already in use"}, status=409)
    return JsonResponse(_tag_json(tag))


@require_http_methods(["GET"])
def tag_barcode_label(request, tag_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    tag = Tag.objects.filter(pk=tag_id, owner=request.user).first()
    if tag is None:
        return JsonResponse({"error": "Tag not found"}, status=404)
    if not tag.barcode_value:
        return JsonResponse({"error": "Set a barcode for this tag first"}, status=409)
    qr = segno.make_qr(tag.barcode_value, error="m")
    output = io.BytesIO()
    qr.save(output, kind="svg", scale=3, border=2, dark="#183e32")
    name = escape(tag.name[:70])
    code = escape(tag.barcode_value)
    html = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Ripiano tag {name}</title>
<style>@page{{size:70mm 40mm;margin:0}}body{{margin:0;font-family:Arial,sans-serif;color:#183e32}}.label{{box-sizing:border-box;width:70mm;height:40mm;padding:3mm;display:flex;gap:3mm;border:1px solid #bbb}}svg{{width:30mm;height:30mm;flex:none}}.text{{overflow:hidden}}.brand{{font-size:8pt;font-weight:bold}}h1{{font-size:11pt;margin:2mm 0 1mm;overflow:hidden}}.code{{font-size:8pt;overflow-wrap:anywhere}}</style>
<div class="label">{output.getvalue().decode("utf-8")}<div class="text"><div class="brand">ripiano · tag</div><h1>{name}</h1><div class="code">{code}</div></div></div></html>"""
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return response


@require_http_methods(["GET", "POST"])
def rules(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        return JsonResponse({"rules": [{
            "id": str(rule.id), "tag_id": str(rule.tag_id), "tag_name": rule.tag.name,
            "pattern": rule.pattern, "field": rule.field, "match": rule.match, "enabled": rule.enabled,
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
    match = body.get("match", "phrase")
    if tag is None or not isinstance(pattern, str) or not pattern.strip() or len(pattern.strip()) > 200 or field not in ClassificationRule.Field.values:
        return JsonResponse({"error": "Choose a tag, phrase, and valid field"}, status=400)
    problem = validate_pattern(pattern.strip(), match) if isinstance(match, str) else "Choose how the rule matches"
    if problem:
        return JsonResponse({"error": problem}, status=400)
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
            rule = ClassificationRule.objects.create(owner=request.user, tag=tag, pattern=pattern.strip(), field=field, match=match)
    except IntegrityError:
        return JsonResponse({"error": "This rule already exists"}, status=409)
    _queue_tag_candidates(request.user.id, tag.id, [{"pattern": rule.pattern, "field": rule.field, "match": rule.match}])
    return JsonResponse({"id": str(rule.id), "tag_id": str(tag.id), "tag_name": tag.name, "pattern": rule.pattern, "field": rule.field, "match": rule.match, "enabled": True}, status=201)


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
