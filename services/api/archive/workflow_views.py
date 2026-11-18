"""Owner-scoped workflow management and run history."""

import json
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import CustomField, Correspondent, Document, DocumentAccess, DocumentType, StoragePath, Tag, Workflow, WorkflowRun
from .storage_paths import validate_title_template
from .workflows import MAX_FIELD_VALUES, MAX_PDF_PASSWORDS, MAX_SHARES, pdf_passwords, run_workflow, set_pdf_passwords
from .field_labels import label


def _signed_in(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _workflow_json(item):
    return {
        "id": str(item.id), "name": item.name, "enabled": item.enabled, "order": item.order, "trigger": item.trigger,
        "schedule_field": item.schedule_field, "schedule_days": item.schedule_days,
        "filter_sources": item.filter_sources, "filter_filename": item.filter_filename, "filter_text": item.filter_text,
        "filter_tag_id": str(item.filter_tag_id) if item.filter_tag_id else None,
        "filter_correspondent_id": str(item.filter_correspondent_id) if item.filter_correspondent_id else None,
        "filter_document_type_id": str(item.filter_document_type_id) if item.filter_document_type_id else None,
        "add_tag_ids": [str(tag.id) for tag in item.add_tags.all()], "remove_tag_ids": [str(tag.id) for tag in item.remove_tags.all()],
        "set_correspondent_id": str(item.set_correspondent_id) if item.set_correspondent_id else None,
        "set_document_type_id": str(item.set_document_type_id) if item.set_document_type_id else None,
        "set_needs_action": item.set_needs_action, "action_note": item.action_note, "add_note": item.add_note,
        "webhook_url": item.webhook_url, "email_to": item.email_to, "email_attach": item.email_attach,
        "title_template": item.title_template,
        "set_storage_path_id": str(item.set_storage_path_id) if item.set_storage_path_id else None,
        "set_custom_fields": [_field_value_json(entry) for entry in item.set_custom_fields or []],
        "share_with": [{"kind": entry["kind"], "id": entry["id"], "level": entry["level"]} for entry in item.share_with or []],
        # Passwords are write-only; only how many are saved is ever shown.
        "pdf_password_count": len(pdf_passwords(item)),
    }


def _field_value_json(entry):
    # Booleans are stored as "true"/"false" like document values and returned as true/false.
    value = entry.get("value")
    if entry.get("kind") == CustomField.Kind.BOOLEAN:
        value = value == "true"
    return {"field_id": entry.get("field_id"), "value": value}


def _custom_field_values(owner, values):
    from .custom_field_views import normalize_value

    if not isinstance(values, list) or len(values) > MAX_FIELD_VALUES or not all(isinstance(entry, dict) for entry in values):
        raise ValueError(f"Custom field values must be a list of up to {MAX_FIELD_VALUES} fields")
    result, seen = [], set()
    for entry in values:
        field = _owned(CustomField, owner, entry.get("field_id"), "Custom field")
        if field is None:
            raise ValueError("Choose a custom field for each value")
        if field.pk in seen:
            raise ValueError("Choose each custom field only once")
        seen.add(field.pk)
        if "value" not in entry or entry["value"] is None:
            raise ValueError("Give each custom field a value")
        result.append({"field_id": str(field.pk), "kind": field.kind, "value": normalize_value(field.kind, entry["value"])})
    return result


def _share_with(owner, values):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    if not isinstance(values, list) or len(values) > MAX_SHARES or not all(isinstance(entry, dict) for entry in values):
        raise ValueError(f"Share with up to {MAX_SHARES} people or groups")
    result, seen = [], set()
    for entry in values:
        kind, target_id, level = entry.get("kind"), entry.get("id"), entry.get("level", DocumentAccess.Level.VIEW)
        if kind not in ("person", "group") or not isinstance(target_id, int) or isinstance(target_id, bool) or level not in DocumentAccess.Level.values:
            raise ValueError("Choose a person or a group, and view or edit, for each share")
        if kind == "person":
            if target_id == owner.pk:
                raise ValueError("You already own your documents; choose someone else to share with")
            if not get_user_model().objects.filter(pk=target_id, is_active=True).exists():
                raise ValueError("Person not found")
        elif not Group.objects.filter(pk=target_id).exists():
            raise ValueError("Group not found")
        if (kind, target_id) in seen:
            raise ValueError("Choose each person or group only once")
        seen.add((kind, target_id))
        result.append({"kind": kind, "id": target_id, "level": level})
    return result


def _run_json(run):
    return {"id": str(run.id), "workflow": run.workflow.name, "document": {"id": str(run.document_id), "title": run.document.title},
            "trigger": run.trigger, "status": run.status, "detail": run.detail, "created_at": run.created_at.isoformat()}


def _owned(model, owner, value, label):
    if value in (None, ""):
        return None
    try:
        item = model.objects.filter(pk=value, owner=owner).first() if isinstance(value, str) else None
    except ValidationError:
        item = None
    if item is None:
        raise ValueError(f"{label} not found")
    return item


def _tags(owner, values):
    if not isinstance(values, list) or len(values) > 50 or not all(isinstance(item, str) for item in values):
        raise ValueError("Tags must be a list")
    try:
        tags = list(Tag.objects.filter(owner=owner, pk__in=values))
    except ValidationError:
        tags = []
    if len(tags) != len(set(values)):
        raise ValueError("Tag not found")
    return tags


def _text(body, key, limit, current):
    value = body.get(key, current)
    if not isinstance(value, str) or len(value.strip()) > limit:
        raise ValueError(f"{label(key)} must be text up to {limit} characters")
    return value.strip()


def _apply(item, body, owner):
    item.name = _text(body, "name", 100, item.name)
    if not item.name:
        raise ValueError("Give the workflow a name")
    trigger = body.get("trigger", item.trigger)
    if trigger not in Workflow.Trigger.values:
        raise ValueError("Choose when the workflow runs")
    item.trigger = trigger
    field = body.get("schedule_field", item.schedule_field)
    if field not in Workflow.DateField.values:
        raise ValueError("Choose which date the schedule counts from")
    item.schedule_field = field
    days = body.get("schedule_days", item.schedule_days)
    if not isinstance(days, int) or isinstance(days, bool) or not -3650 <= days <= 3650:
        raise ValueError("Days must be between -3650 and 3650")
    item.schedule_days = days
    for key in ("enabled", "set_needs_action", "email_attach"):
        value = body.get(key, getattr(item, key))
        if not isinstance(value, bool):
            raise ValueError(f"{key.replace('_', ' ').capitalize()} must be true or false")
        setattr(item, key, value)
    order = body.get("order", item.order)
    if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= 10000:
        raise ValueError("Order must be 0–10000")
    item.order = order
    sources = body.get("filter_sources", item.filter_sources)
    if not isinstance(sources, list) or not all(isinstance(value, str) for value in sources) or not set(sources) <= set(Document.Source.values):
        raise ValueError("Unknown document source")
    item.filter_sources = sorted(set(sources))
    item.filter_filename = _text(body, "filter_filename", 200, item.filter_filename)
    item.filter_text = _text(body, "filter_text", 200, item.filter_text)
    item.action_note = _text(body, "action_note", 500, item.action_note)
    item.add_note = _text(body, "add_note", 2000, item.add_note)
    for key, model, label in (("filter_tag", Tag, "Tag"), ("filter_correspondent", Correspondent, "Sender"), ("filter_document_type", DocumentType, "Document type"),
                              ("set_correspondent", Correspondent, "Sender"), ("set_document_type", DocumentType, "Document type"),
                              ("set_storage_path", StoragePath, "Storage path")):
        if f"{key}_id" in body:
            setattr(item, key, _owned(model, owner, body[f"{key}_id"], label))
    if "title_template" in body:
        template = body["title_template"]
        if not isinstance(template, str):
            raise ValueError("Write a title template of up to 200 characters on one line")
        template = template.strip()
        problem = validate_title_template(template) if template else ""
        if problem:
            raise ValueError(problem)
        item.title_template = template
    if "set_custom_fields" in body:
        item.set_custom_fields = _custom_field_values(owner, body["set_custom_fields"])
    if "share_with" in body:
        item.share_with = _share_with(owner, body["share_with"])
    url = _text(body, "webhook_url", 500, item.webhook_url)
    if url:
        parts = urlsplit(url)
        try:
            valid_host = bool(parts.hostname) and bool(parts.hostname.encode("idna"))
        except UnicodeError:
            valid_host = False
        if parts.scheme not in ("http", "https") or not valid_host or parts.username or parts.password:
            raise ValueError("Use a web address starting with https:// or http:// for the webhook")
    item.webhook_url = url
    recipients = _text(body, "email_to", 500, item.email_to)
    for address in filter(None, (part.strip() for part in recipients.split(","))):
        try:
            validate_email(address)
        except ValidationError as exc:
            raise ValueError(f"“{address}” is not an email address") from exc
    item.email_to = recipients
    if "pdf_passwords" in body:
        values = body["pdf_passwords"]
        if (not isinstance(values, list) or len(values) > MAX_PDF_PASSWORDS
                or not all(isinstance(value, str) and 0 < len(value) <= 200 for value in values)):
            raise ValueError(f"PDF passwords must be a list of up to {MAX_PDF_PASSWORDS} passwords, each up to 200 characters")
        set_pdf_passwords(item, list(dict.fromkeys(values)))
    if item.pdf_passwords and item.trigger != Workflow.Trigger.ADDED:
        raise ValueError("PDF passwords only work in workflows that run when a document is added")
    add = _tags(owner, body["add_tag_ids"]) if "add_tag_ids" in body else None
    remove = _tags(owner, body["remove_tag_ids"]) if "remove_tag_ids" in body else None
    return add, remove


def _save(item, body, owner):
    with transaction.atomic():
        add, remove = _apply(item, body, owner)
        item.save()
        if add is not None:
            item.add_tags.set(add)
        if remove is not None:
            item.remove_tags.set(remove)


@require_http_methods(["GET", "POST"])
def workflows(request):
    denied = _signed_in(request)
    if denied:
        return denied
    if request.method == "GET":
        items = Workflow.objects.filter(owner=request.user).prefetch_related("add_tags", "remove_tags")
        runs = WorkflowRun.objects.filter(workflow__owner=request.user).select_related("workflow", "document")[:50]
        return JsonResponse({"workflows": [_workflow_json(item) for item in items], "runs": [_run_json(run) for run in runs]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    item = Workflow(owner=request.user, trigger=Workflow.Trigger.ADDED)
    try:
        _save(item, body, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_workflow_json(item), status=201)


@require_http_methods(["PATCH", "DELETE"])
def workflow_detail(request, workflow_id):
    denied = _signed_in(request)
    if denied:
        return denied
    item = Workflow.objects.filter(pk=workflow_id, owner=request.user).first()
    if item is None:
        return JsonResponse({"error": "Workflow not found"}, status=404)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    try:
        _save(item, body, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_workflow_json(item))


@require_http_methods(["POST"])
def workflow_run_now(request, workflow_id):
    """Apply a workflow to one chosen document now (recorded like any other run)."""
    denied = _signed_in(request)
    if denied:
        return denied
    item = Workflow.objects.filter(pk=workflow_id, owner=request.user).first()
    body = _body(request) or {}
    try:
        document = Document.objects.filter(pk=body.get("document_id"), owner=request.user, trashed_at__isnull=True).first() if item else None
    except ValidationError:
        document = None
    if item is None or document is None:
        return JsonResponse({"error": "Workflow or document not found"}, status=404)
    run = run_workflow(item, document, Workflow.Trigger.UPDATED)
    if run is None:
        return JsonResponse({"matched": False, "detail": "This document does not match the workflow’s conditions."})
    return JsonResponse({"matched": True, "run": _run_json(run)})
