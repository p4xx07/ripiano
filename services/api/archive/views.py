import json
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import Document
from .ingestion import ingest_document
from .storage import InvalidDocument


def _payload(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _document_json(document):
    return {
        "id": str(document.id),
        "title": document.title,
        "original_name": document.original_name,
        "source": document.source,
        "status": document.status,
        "error": document.error,
        "created_at": document.created_at.isoformat(),
        "snippet": document.extracted_text[:240],
    }


def _unauthorized(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"status": "ok"})


@csrf_protect
@require_http_methods(["POST"])
def setup_owner(request):
    if get_user_model().objects.exists():
        return JsonResponse({"error": "Setup is complete"}, status=409)
    expected = settings.RIPIANO_SETUP_KEY
    body = _payload(request)
    if not body or not expected or not secrets.compare_digest(str(body.get("setup_key", "")), expected):
        return JsonResponse({"error": "Invalid setup key"}, status=403)
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    if not username or len(password) < 12:
        return JsonResponse({"error": "Username and a password of at least 12 characters are required"}, status=400)
    user = get_user_model().objects.create_superuser(username=username, password=password)
    login(request, user)
    return JsonResponse({"username": user.get_username()}, status=201)


@ensure_csrf_cookie
@csrf_protect
@require_http_methods(["GET", "POST", "DELETE"])
def session(request):
    if request.method == "GET":
        return JsonResponse({
            "authenticated": request.user.is_authenticated,
            "username": request.user.get_username() if request.user.is_authenticated else None,
            "setup_required": not get_user_model().objects.exists(),
        })
    if request.method == "DELETE":
        logout(request)
        return JsonResponse({"authenticated": False})
    body = _payload(request)
    if not body:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    user = authenticate(request, username=body.get("username"), password=body.get("password"))
    if user is None:
        return JsonResponse({"error": "Invalid credentials"}, status=401)
    login(request, user)
    return JsonResponse({"authenticated": True, "username": user.get_username()})


@require_http_methods(["GET", "POST"])
def documents(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        queryset = Document.objects.filter(owner=request.user)
        query = request.GET.get("q", "").strip()[:200]
        if query:
            if connection.vendor == "postgresql":
                vector = SearchVector("title", weight="A", config="simple") + SearchVector("extracted_text", weight="B", config="simple")
                search_query = SearchQuery(query, search_type="websearch", config="simple")
                queryset = queryset.annotate(search_rank=SearchRank(vector, search_query)).filter(search_rank__gt=0).order_by("-search_rank", "-created_at")
            else:
                queryset = queryset.filter(Q(title__icontains=query) | Q(extracted_text__icontains=query))
        return JsonResponse({"documents": [_document_json(doc) for doc in queryset[:50]]})

    upload = request.FILES.get("document")
    if upload is None:
        return JsonResponse({"error": "Missing document file"}, status=400)
    try:
        document = ingest_document(request.user, upload)
    except InvalidDocument as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_document_json(document), status=202)


@require_http_methods(["GET"])
def document_detail(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.filter(pk=document_id, owner=request.user).first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    return JsonResponse(_document_json(document))


@require_http_methods(["GET"])
def download_original(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.filter(pk=document_id, owner=request.user).first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    return FileResponse(
        (Path(settings.MEDIA_ROOT) / document.original_path).open("rb"),
        content_type=document.original_mime,
        as_attachment=True,
        filename=Path(document.original_name).name,
    )
