import json
import logging
import secrets
from datetime import date
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection, transaction
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import BackupRun, Document, DocumentTag, Tag, TagOverride
from .physical_views import copy_json
from .ingestion import ingest_document
from .storage import InvalidDocument
from .tasks import backup_archive

logger = logging.getLogger(__name__)


def _payload(request):
    try:
        value = json.loads(request.body)
        return value if isinstance(value, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _document_json(document):
    return {
        "id": str(document.id),
        "title": document.title,
        "original_name": document.original_name,
        "duplicate_of": {"id": str(document.duplicate_of_id), "title": document.duplicate_of.title} if document.duplicate_of_id else None,
        "source": document.source,
        "status": document.status,
        "archive_available": bool(document.archive_path) and document.status == Document.Status.READY,
        "error": document.error,
        "created_at": document.created_at.isoformat(),
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "tags": [{"id": str(link.tag_id), "name": link.tag.name, "color": link.tag.color, "origin": link.origin} for link in document.tag_links.all()],
        "physical_copies": [copy_json(copy) for copy in document.physical_copies.all()],
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
            "owner": request.user.is_superuser if request.user.is_authenticated else False,
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
        queryset = Document.objects.filter(owner=request.user).select_related("duplicate_of").prefetch_related("tag_links__tag", "physical_copies__location")
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


@require_http_methods(["GET", "PATCH"])
def document_detail(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.filter(pk=document_id, owner=request.user).select_related("duplicate_of").prefetch_related("tag_links__tag", "physical_copies__location").first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    if request.method == "PATCH":
        body = _payload(request)
        if body is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        changes = []
        if "title" in body:
            if not isinstance(body["title"], str) or not body["title"].strip() or len(body["title"].strip()) > 300:
                return JsonResponse({"error": "Title must be 1–300 characters"}, status=400)
            document.title = body["title"].strip()
            changes.append("title")
        if "document_date" in body:
            try:
                document.document_date = date.fromisoformat(body["document_date"]) if body["document_date"] else None
            except (TypeError, ValueError):
                return JsonResponse({"error": "Use an ISO date (YYYY-MM-DD)"}, status=400)
            changes.append("document_date")
        chosen = None
        if "tags" in body:
            if not isinstance(body["tags"], list) or len(body["tags"]) > 100:
                return JsonResponse({"error": "Tags must be a list of up to 100 IDs"}, status=400)
            try:
                chosen_ids = {UUID(str(value)) for value in body["tags"]}
            except ValueError:
                return JsonResponse({"error": "Invalid tag ID"}, status=400)
            chosen = list(Tag.objects.filter(owner=request.user, pk__in=chosen_ids))
            if len(chosen) != len(chosen_ids):
                return JsonResponse({"error": "Tag not found"}, status=400)
        with transaction.atomic():
            if changes:
                document.save(update_fields=changes)
            if chosen is not None:
                selected = {tag.id for tag in chosen}
                existing = set(DocumentTag.objects.filter(document=document).values_list("tag_id", flat=True))
                for tag_id in existing - selected:
                    DocumentTag.objects.filter(document=document, tag_id=tag_id).delete()
                    TagOverride.objects.get_or_create(document=document, tag_id=tag_id)
                for tag in chosen:
                    TagOverride.objects.filter(document=document, tag=tag).delete()
                    DocumentTag.objects.update_or_create(document=document, tag=tag, defaults={"origin": DocumentTag.Origin.MANUAL})
        document = Document.objects.filter(pk=document.id).select_related("duplicate_of").prefetch_related("tag_links__tag", "physical_copies__location").get()
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


@require_http_methods(["GET"])
def download_archive(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.filter(pk=document_id, owner=request.user).first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    if document.status != Document.Status.READY or not document.archive_path:
        return JsonResponse({"error": "Archive PDF is not ready"}, status=409)
    try:
        source = (Path(settings.MEDIA_ROOT) / document.archive_path).open("rb")
    except FileNotFoundError:
        return JsonResponse({"error": "Archive PDF is missing"}, status=503)
    return FileResponse(source, content_type="application/pdf", filename=f"{document.title}.pdf")


@require_http_methods(["POST"])
def retry_document(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.filter(pk=document_id, owner=request.user).first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    if document.status != Document.Status.FAILED:
        return JsonResponse({"error": "Only failed documents can be retried"}, status=409)
    document.status = Document.Status.PENDING
    document.error = ""
    document.processing_started_at = None
    document.save(update_fields=["status", "error", "processing_started_at"])
    try:
        from .tasks import process_document

        process_document.delay(str(document.id))
    except Exception:
        logger.exception("Retry queue unavailable; pending document will be reconciled")
    return JsonResponse(_document_json(document), status=202)


@require_http_methods(["GET", "POST"])
def backups(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"error": "Owner access required"}, status=403)
    if request.method == "GET":
        return JsonResponse({
            "schedule": f"{settings.RIPIANO_BACKUP_HOUR:02d}:{settings.RIPIANO_BACKUP_MINUTE:02d} Europe/Rome",
            "runs": [{
                "id": str(run.id), "status": run.status, "trigger": run.trigger,
                "snapshot_name": run.snapshot_name, "error": run.error,
                "created_at": run.created_at.isoformat(),
            } for run in BackupRun.objects.all()[:20]],
        })
    run = BackupRun.objects.create(trigger="manual")
    try:
        backup_archive.delay(str(run.id))
    except Exception:
        run.status = BackupRun.Status.FAILED
        run.error = "Backup queue unavailable"
        run.save(update_fields=["status", "error"])
        return JsonResponse({"error": run.error}, status=503)
    return JsonResponse({"id": str(run.id), "status": run.status}, status=202)
