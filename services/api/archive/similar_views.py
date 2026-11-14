from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Document
from .similar import similar_documents


@require_http_methods(["GET"])
def document_similar(request, document_id):
    """Documents with the most distinctive words in common (local word overlap)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    document = Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).only("id", "owner", "status", "original_sha256").first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    return JsonResponse({"similar": similar_documents(document)})
