import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import CustomField, CustomFieldValue, Document, SavedView


def normalize_value(kind, value):
    if kind == CustomField.Kind.TEXT:
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
            raise ValueError("Text must be 1–500 characters")
        return value.strip()
    if kind == CustomField.Kind.NUMBER:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError("Enter a number")
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("Enter a number") from exc
        if not number.is_finite():
            raise ValueError("Enter a finite number")
        number = number.normalize()
        if number.adjusted() > 17 or number.as_tuple().exponent < -6:
            raise ValueError("Number must have at most 18 whole digits and 6 decimal places")
        normalized = format(number, "f")
        if len(normalized) > 500:
            raise ValueError("Number is too long")
        return normalized
    if kind == CustomField.Kind.DATE:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use YYYY-MM-DD")
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise ValueError("Use a valid date") from exc
    if kind == CustomField.Kind.BOOLEAN:
        if not isinstance(value, bool):
            raise ValueError("Choose yes or no")
        return "true" if value else "false"
    raise ValueError("Unknown custom field type")


def normalize_filter_value(field, value):
    if field.kind == CustomField.Kind.BOOLEAN:
        if value.casefold() not in {"true", "false", "yes", "no"}:
            raise ValueError("Use yes or no for this field")
        value = value.casefold() in {"true", "yes"}
    return normalize_value(field.kind, value)


def field_json(field, value=None, in_use=None):
    result = {"id": str(field.id), "name": field.name, "kind": field.kind,
              "value": (value == "true" if field.kind == CustomField.Kind.BOOLEAN else value) if value is not None else None}
    if in_use is not None:
        result["in_use"] = in_use
    return result


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


@require_http_methods(["GET", "POST"])
def custom_fields(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        return JsonResponse({"fields": [field_json(field) for field in CustomField.objects.filter(owner=request.user)]})
    body = _body(request)
    name = body.get("name") if body else None
    kind = body.get("kind") if body else None
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100 or kind not in CustomField.Kind.values:
        return JsonResponse({"error": "Use a name (1–100 characters) and a supported field type"}, status=400)
    try:
        with transaction.atomic():
            if CustomField.objects.filter(owner=request.user).count() >= 100:
                return JsonResponse({"error": "Limit of 100 custom fields reached"}, status=409)
            field = CustomField.objects.create(owner=request.user, name=name.strip(), kind=kind)
    except IntegrityError:
        return JsonResponse({"error": "A field with that name already exists"}, status=409)
    return JsonResponse(field_json(field), status=201)


@transaction.atomic
@require_http_methods(["PATCH", "DELETE"])
def custom_field_detail(request, field_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    field = CustomField.objects.select_for_update().filter(pk=field_id, owner=request.user).first()
    if field is None:
        return JsonResponse({"error": "Custom field not found"}, status=404)
    if request.method == "DELETE":
        if field.values.exists() or SavedView.objects.filter(custom_field=field).exists():
            return JsonResponse({"error": "Remove this field from documents and saved searches before deleting it"}, status=409)
        try:
            field.delete()
        except ProtectedError:
            return JsonResponse({"error": "Remove this field from documents and saved searches before deleting it"}, status=409)
        return JsonResponse({"deleted": True})
    body = _body(request)
    name = body.get("name") if body else None
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        return JsonResponse({"error": "Name must be 1–100 characters"}, status=400)
    field.name = name.strip()
    try:
        with transaction.atomic():
            field.save(update_fields=["name"])
    except IntegrityError:
        return JsonResponse({"error": "A field with that name already exists"}, status=409)
    return JsonResponse(field_json(field))


@require_http_methods(["GET"])
def document_custom_fields(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if not Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).exists():
        return JsonResponse({"error": "Document not found"}, status=404)
    values = dict(CustomFieldValue.objects.filter(document_id=document_id, field__owner=request.user).values_list("field_id", "value"))
    used_ids = set(CustomFieldValue.objects.filter(field__owner=request.user).values_list("field_id", flat=True).distinct())
    used_ids.update(SavedView.objects.filter(owner=request.user, custom_field__isnull=False).values_list("custom_field_id", flat=True).distinct())
    return JsonResponse({"fields": [field_json(field, values.get(field.id), field.id in used_ids) for field in CustomField.objects.filter(owner=request.user)]})


@transaction.atomic
@require_http_methods(["PUT", "DELETE"])
def document_custom_field_detail(request, document_id, field_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.select_for_update().filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
    field = CustomField.objects.select_for_update().filter(pk=field_id, owner=request.user).first()
    if document is None or field is None:
        return JsonResponse({"error": "Custom field not found"}, status=404)
    if request.method == "DELETE":
        CustomFieldValue.objects.filter(document=document, field=field).delete()
        return JsonResponse(field_json(field))
    body = _body(request)
    if body is None or "value" not in body:
        return JsonResponse({"error": "Provide a value"}, status=400)
    if body["value"] is None:
        CustomFieldValue.objects.filter(document=document, field=field).delete()
        return JsonResponse(field_json(field))
    try:
        value = normalize_value(field.kind, body["value"])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    CustomFieldValue.objects.update_or_create(document=document, field=field, defaults={"value": value})
    return JsonResponse(field_json(field, value))
