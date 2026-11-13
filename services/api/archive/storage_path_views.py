"""Owner-scoped storage paths (folder templates for the NAS browse copy)."""

import json

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Document, StoragePath
from .storage_paths import PLACEHOLDERS, render, validate_template


def _json(item):
    return {"id": str(item.id), "name": item.name, "template": item.template, "documents": getattr(item, "document_count", None)}


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


@require_http_methods(["GET", "POST"])
def storage_paths(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    if request.method == "GET":
        from django.db.models import Count

        from django.db.models import Q

        items = StoragePath.objects.filter(owner=request.user).annotate(document_count=Count("documents", filter=Q(documents__trashed_at__isnull=True)))
        return JsonResponse({"storage_paths": [_json(item) for item in items], "placeholders": sorted(PLACEHOLDERS)})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name, template = body.get("name", ""), body.get("template", "")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return JsonResponse({"error": "Give the storage path a name"}, status=400)
    problem = validate_template(template)
    if problem:
        return JsonResponse({"error": problem}, status=400)
    try:
        with transaction.atomic():
            item = StoragePath.objects.create(owner=request.user, name=name.strip(), template=template.strip().strip("/"))
    except IntegrityError:
        return JsonResponse({"error": "You already have a storage path with this name"}, status=409)
    sample = Document.objects.filter(owner=request.user, trashed_at__isnull=True).select_related("correspondent", "document_type").first()
    return JsonResponse({**_json(item), "example": "/".join(render(item.template, sample)) if sample else None}, status=201)


@require_http_methods(["DELETE"])
def storage_path_detail(request, path_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    deleted, _ = StoragePath.objects.filter(pk=path_id, owner=request.user).delete()
    if not deleted:
        return JsonResponse({"error": "Storage path not found"}, status=404)
    return JsonResponse({"deleted": True})
