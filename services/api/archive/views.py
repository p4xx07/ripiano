import json
import logging
import secrets
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core import signing
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import IntegrityError, connection, transaction
from django.db.models import BigIntegerField, Count, Exists, F, OuterRef, Q
from django.db.models.functions import Cast
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import BackupRun, Correspondent, Document, DocumentTag, DocumentType, PhysicalCopy, Tag, TagOverride
from .physical_views import copy_json
from .ingestion import ingest_document
from .storage import InvalidDocument
from .tasks import backup_archive

logger = logging.getLogger(__name__)
CURSOR_SALT = "ripiano-document-page-v1"


def _read_page_cursor(raw, owner, query, view):
    try:
        value = signing.loads(raw, salt=CURSOR_SALT, max_age=86400)
        if not isinstance(value, dict) or value.get("owner") != str(owner.pk) or value.get("query") != query or value.get("view") != view:
            raise ValueError
        created_at = datetime.fromisoformat(value["created_at"])
        if timezone.is_naive(created_at):
            raise ValueError
        document_id = UUID(value["id"])
        due_date = date.fromisoformat(value["due_date"]) if value.get("due_date") else None
        score = int(value["score"]) if view == "search" else None
        if score is not None and score < 0:
            raise ValueError
        counts = value["counts"]
        if not isinstance(counts, dict) or not all(isinstance(counts.get(key), int) and counts[key] >= 0 for key in ("total", "ready", "waiting")):
            raise ValueError
        return created_at, document_id, due_date, score, counts
    except (signing.BadSignature, KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid page cursor") from exc


def _next_page_cursor(document, owner, query, view, counts):
    return signing.dumps({
        "owner": str(owner.pk), "query": query, "view": view,
        "created_at": document.created_at.isoformat(), "id": str(document.id),
        "due_date": document.action_due_date.isoformat() if document.action_due_date else None,
        "score": int(getattr(document, "search_score", 0)) if view == "search" else None,
        "counts": counts,
    }, salt=CURSOR_SALT)


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
        "duplicate_reviewed_at": document.duplicate_reviewed_at.isoformat() if document.duplicate_reviewed_at else None,
        "source": document.source,
        "status": document.status,
        "archive_available": bool(document.archive_path) and document.status == Document.Status.READY,
        "error": document.error,
        "created_at": document.created_at.isoformat(),
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "correspondent": {"id": str(document.correspondent_id), "name": document.correspondent.name} if document.correspondent_id else None,
        "document_type": {"id": str(document.document_type_id), "name": document.document_type.name} if document.document_type_id else None,
        "correspondent_origin": document.correspondent_origin,
        "document_type_origin": document.document_type_origin,
        "action_status": document.action_status,
        "action_due_date": document.action_due_date.isoformat() if document.action_due_date else None,
        "action_note": document.action_note,
        "action_completed_at": document.action_completed_at.isoformat() if document.action_completed_at else None,
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
        if "offset" in request.GET:
            return JsonResponse({"error": "Use a page cursor"}, status=400)
        queryset = Document.objects.filter(owner=request.user).select_related("duplicate_of", "correspondent", "document_type").prefetch_related("tag_links__tag", "physical_copies__location")
        query = request.GET.get("q", "").strip()[:200]
        requested_view = request.GET.get("view")
        view = "actions" if requested_view == "actions" else "exceptions" if requested_view == "exceptions" else "search" if query else "documents"
        if view == "actions":
            queryset = queryset.filter(action_status=Document.ActionStatus.OPEN)
        elif view == "exceptions":
            queryset = queryset.filter(Q(status=Document.Status.FAILED) | Q(duplicate_of__isnull=False, duplicate_reviewed_at__isnull=True))
        if query:
            queryset = queryset.annotate(
                tag_match=Exists(Tag.objects.filter(document_links__document_id=OuterRef("pk"), name__icontains=query)),
                sticker_match=Exists(PhysicalCopy.objects.filter(document_id=OuterRef("pk"), sticker_code__icontains=query)),
            )
            if connection.vendor == "postgresql":
                vector = SearchVector("title", weight="A", config="simple") + SearchVector("extracted_text", weight="B", config="simple") + SearchVector("action_note", weight="C", config="simple")
                search_query = SearchQuery(query, search_type="plain", config="simple")
                queryset = queryset.annotate(search_score=Cast(SearchRank(vector, search_query) * 1000000, BigIntegerField())).filter(Q(search_score__gt=0) | Q(tag_match=True) | Q(sticker_match=True) | Q(correspondent__name__icontains=query) | Q(document_type__name__icontains=query)).order_by("-search_score", "-created_at", "-id")
            else:
                queryset = queryset.filter(Q(title__icontains=query) | Q(extracted_text__icontains=query) | Q(action_note__icontains=query) | Q(tag_match=True) | Q(sticker_match=True) | Q(correspondent__name__icontains=query) | Q(document_type__name__icontains=query))
        if view == "actions":
            queryset = queryset.order_by(F("action_due_date").asc(nulls_last=True), "-created_at", "-id")
        elif view != "search":
            queryset = queryset.order_by("-created_at", "-id")
        elif connection.vendor != "postgresql":
            queryset = queryset.order_by("-created_at", "-id")

        cursor_raw = request.GET.get("cursor")
        if cursor_raw:
            try:
                created_at, document_id, due_date, score, counts = _read_page_cursor(cursor_raw, request.user, query, view)
            except ValueError:
                return JsonResponse({"error": "Invalid page cursor"}, status=400)
            older = Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=document_id)
            if view == "actions":
                if due_date is None:
                    queryset = queryset.filter(Q(action_due_date__isnull=True) & older)
                else:
                    queryset = queryset.filter(Q(action_due_date__gt=due_date) | Q(action_due_date__isnull=True) | (Q(action_due_date=due_date) & older))
            elif view == "search" and connection.vendor == "postgresql":
                queryset = queryset.filter(Q(search_score__lt=score) | (Q(search_score=score) & older))
            else:
                queryset = queryset.filter(older)
        else:
            counts = queryset.aggregate(
                total=Count("id"),
                ready=Count("id", filter=Q(status=Document.Status.READY)),
                waiting=Count("id", filter=Q(status__in=[Document.Status.PENDING, Document.Status.PROCESSING])),
            )
        page = list(queryset[:51])
        visible = page[:50]
        return JsonResponse({
            "documents": [_document_json(doc) for doc in visible],
            "next_cursor": _next_page_cursor(visible[-1], request.user, query, view, counts) if len(page) > 50 else None,
            "counts": counts,
        })

    upload = request.FILES.get("document")
    if upload is None:
        return JsonResponse({"error": "Missing document file"}, status=400)
    scan_id = request.headers.get("X-Ripiano-Scan-ID", "")
    if scan_id:
        try:
            scan_id = str(UUID(scan_id))
        except ValueError:
            return JsonResponse({"error": "Invalid scan ID"}, status=400)
        existing = Document.objects.filter(owner=request.user, source=Document.Source.ANDROID, source_ref=scan_id).select_related("duplicate_of", "correspondent", "document_type").prefetch_related("tag_links__tag", "physical_copies__location").first()
        if existing:
            return JsonResponse(_document_json(existing), status=200)
    try:
        document = ingest_document(request.user, upload, source=Document.Source.ANDROID if scan_id else Document.Source.WEB, source_ref=scan_id)
    except IntegrityError:
        if scan_id:
            existing = Document.objects.filter(owner=request.user, source=Document.Source.ANDROID, source_ref=scan_id).select_related("duplicate_of", "correspondent", "document_type").prefetch_related("tag_links__tag", "physical_copies__location").first()
            if existing:
                return JsonResponse(_document_json(existing), status=200)
        raise
    except InvalidDocument as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_document_json(document), status=202)


@require_http_methods(["GET", "PATCH"])
def document_detail(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.filter(pk=document_id, owner=request.user).select_related("duplicate_of", "correspondent", "document_type").prefetch_related("tag_links__tag", "physical_copies__location").first()
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
        for field, model in (("correspondent", Correspondent), ("document_type", DocumentType)):
            key = f"{field}_id"
            if key not in body:
                continue
            raw = body[key]
            if raw is None or raw == "":
                item = None
            else:
                try:
                    item_id = UUID(raw) if isinstance(raw, str) else None
                except ValueError:
                    item_id = None
                item = model.objects.filter(pk=item_id, owner=request.user).first() if item_id else None
                if item is None:
                    return JsonResponse({"error": f"{field.replace('_', ' ').title()} not found"}, status=400)
            setattr(document, field, item)
            setattr(document, f"{field}_origin", Document.FilingOrigin.MANUAL)
            changes.extend([field, f"{field}_origin"])
        if "action_status" in body:
            status = body["action_status"]
            if status not in Document.ActionStatus.values:
                return JsonResponse({"error": "Invalid action status"}, status=400)
            if status != document.action_status:
                document.action_status = status
                document.action_completed_at = timezone.now() if status == Document.ActionStatus.DONE else None
                changes.extend(["action_status", "action_completed_at"])
        if "action_due_date" in body:
            try:
                document.action_due_date = date.fromisoformat(body["action_due_date"]) if body["action_due_date"] else None
            except (TypeError, ValueError):
                return JsonResponse({"error": "Use an ISO due date (YYYY-MM-DD)"}, status=400)
            changes.append("action_due_date")
        if "action_note" in body:
            if not isinstance(body["action_note"], str) or len(body["action_note"].strip()) > 500:
                return JsonResponse({"error": "Action note must be at most 500 characters"}, status=400)
            document.action_note = body["action_note"].strip()
            changes.append("action_note")
        if "duplicate_reviewed" in body:
            if not isinstance(body["duplicate_reviewed"], bool) or document.duplicate_of_id is None:
                return JsonResponse({"error": "Only exact copies can be reviewed"}, status=400)
            document.duplicate_reviewed_at = timezone.now() if body["duplicate_reviewed"] else None
            changes.append("duplicate_reviewed_at")
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
        document = Document.objects.filter(pk=document.id).select_related("duplicate_of", "correspondent", "document_type").prefetch_related("tag_links__tag", "physical_copies__location").get()
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
