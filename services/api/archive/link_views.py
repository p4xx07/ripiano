import json
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Document, DocumentLink


def _unauthorized(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _related(document):
    links = DocumentLink.objects.filter(Q(left=document) | Q(right=document)).select_related("left", "right").order_by("-created_at", "-id")
    return [
        {"id": str(other.id), "title": other.title, "created_at": link.created_at.isoformat()}
        for link in links
        if (other := link.right if link.left_id == document.id else link.left).trashed_at is None and other.owner_id == document.owner_id
    ]


@require_http_methods(["GET", "POST"])
def document_links(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        document = Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
        if document is None:
            return JsonResponse({"error": "Document not found"}, status=404)
        return JsonResponse({"links": _related(document)})
    try:
        body = json.loads(request.body)
        target_id = UUID(body["document_id"]) if isinstance(body, dict) and isinstance(body.get("document_id"), str) else None
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        target_id = None
    if target_id is None or target_id == document_id:
        return JsonResponse({"error": "Choose a different document"}, status=400)
    with transaction.atomic():
        documents = list(Document.objects.select_for_update().filter(pk__in=[document_id, target_id], owner=request.user, trashed_at__isnull=True).order_by("pk"))
        if len(documents) != 2:
            return JsonResponse({"error": "Document not found"}, status=404)
        left_id, right_id = sorted((document_id, target_id))
        if DocumentLink.objects.filter(left_id=left_id, right_id=right_id).exists():
            return JsonResponse({"error": "Documents are already linked"}, status=409)
        DocumentLink.objects.create(left_id=left_id, right_id=right_id)
        target = next(doc for doc in documents if doc.id == target_id)
    return JsonResponse({"id": str(target.id), "title": target.title}, status=201)


@transaction.atomic
@require_http_methods(["DELETE"])
def document_link_detail(request, document_id, target_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    documents = list(Document.objects.select_for_update().filter(pk__in=[document_id, target_id], owner=request.user, trashed_at__isnull=True).order_by("pk"))
    if len(documents) != 2:
        return JsonResponse({"error": "Link not found"}, status=404)
    left_id, right_id = sorted((document_id, target_id))
    deleted, _ = DocumentLink.objects.filter(left_id=left_id, right_id=right_id).delete()
    if not deleted:
        return JsonResponse({"error": "Link not found"}, status=404)
    return JsonResponse({"deleted": True})
