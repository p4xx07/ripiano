from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from . import access, attention_suggestions
from .models import Document


@require_http_methods(["GET"])
def document_attention_suggestion(request, document_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    document, _ = access.readable(request.user, document_id, Document.objects.only(
        "id", "owner_id", "title", "status", "extracted_text", "trashed_at"))
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    suggestion = attention_suggestions.suggest_attention(document.title, document.extracted_text) if document.status == Document.Status.READY else None
    return JsonResponse({"suggestion": suggestion})
