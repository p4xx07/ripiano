"""Owner-scoped workflow management and run history."""

import json
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Correspondent, Document, DocumentType, Tag, Workflow, WorkflowRun
from .workflows import run_workflow


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
    }


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
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be text up to {limit} characters")
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
                              ("set_correspondent", Correspondent, "Sender"), ("set_document_type", DocumentType, "Document type")):
        if f"{key}_id" in body:
            setattr(item, key, _owned(model, owner, body[f"{key}_id"], label))
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
