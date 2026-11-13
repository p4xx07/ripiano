import json
import logging
import re
import secrets
import shlex
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import IntegrityError, connection, transaction
from django.db.models import BigIntegerField, Count, DecimalField, Exists, F, OuterRef, Prefetch, Q, prefetch_related_objects
from django.db.models.functions import Cast, Lower, Substr
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import BackupRun, Correspondent, CustomField, CustomFieldValue, Document, DocumentNote, DocumentTag, DocumentType, PhysicalCopy, ShareLink, Tag, TagOverride
from . import two_factor
from .throttle import record_sign_in_failure, sign_in_blocked, sign_in_throttle_key
from .classification import filing_suggestions
from .models import Workflow
from .workflows import run_for_document
from .custom_field_views import normalize_filter_range, normalize_filter_value
from .physical_views import copy_json
from .ingestion import ingest_document
from .storage import InvalidDocument
from .tasks import backup_archive

logger = logging.getLogger(__name__)
CURSOR_SALT = "ripiano-document-page-v2"
SEARCH_FIELDS = {"title", "text", "note", "tag", "sender", "type", "sticker", "date", "field", "asn"}
LIBRARY_SORTS = {"relevance", "newest", "oldest", "document_newest", "document_oldest", "title_asc", "title_desc"}


def _tag_subtree_ids(owner, root_id):
    children = {}
    for tag_id, parent_id in Tag.objects.filter(owner=owner).values_list("id", "parent_id"):
        children.setdefault(str(parent_id) if parent_id else None, []).append(str(tag_id))
    result = {str(root_id)}
    pending = [str(root_id)]
    while pending:
        for child in children.get(pending.pop(), []):
            if child not in result:
                result.add(child)
                pending.append(child)
    return result


def _parse_search(query):
    try:
        tokens = shlex.split(query)
    except ValueError:
        return query, []
    words = []
    clauses = []
    for token in tokens:
        field, separator, value = token.partition(":")
        if separator and field in SEARCH_FIELDS and value:
            if field == "date":
                try:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError
                    value = date.fromisoformat(value).isoformat()
                except ValueError as exc:
                    raise ValueError("Use YYYY-MM-DD after date:") from exc
            if field == "asn":
                if not re.fullmatch(r"\d{1,9}", value):
                    raise ValueError("Use a number after asn:")
                value = str(int(value))
            if field == "field" and ("=" not in value or not all(part.strip() for part in value.split("=", 1))):
                raise ValueError('Use field:"Name=value" to search a custom field')
            clauses.append((field, value))
        else:
            words.append(token)
    return " ".join(words), clauses


def _read_page_cursor(raw, owner, query, view, filters, sort):
    try:
        value = signing.loads(raw, salt=CURSOR_SALT, max_age=86400)
        if not isinstance(value, dict) or value.get("owner") != str(owner.pk) or value.get("query") != query or value.get("view") != view or value.get("filters", {}) != filters or value.get("sort") != sort:
            raise ValueError
        created_at = datetime.fromisoformat(value["created_at"])
        if timezone.is_naive(created_at):
            raise ValueError
        document_id = UUID(value["id"])
        due_date = date.fromisoformat(value["due_date"]) if value.get("due_date") else None
        score = int(value["score"]) if sort == "relevance" and view == "search" else None
        if score is not None and score < 0:
            raise ValueError
        sort_value = value.get("sort_value")
        if sort in {"title_asc", "title_desc"} and not isinstance(sort_value, str):
            raise ValueError
        if sort in {"document_newest", "document_oldest"} and sort_value is not None:
            sort_value = date.fromisoformat(sort_value)
        counts = value["counts"]
        if not isinstance(counts, dict) or not all(isinstance(counts.get(key), int) and counts[key] >= 0 for key in ("total", "ready", "waiting")):
            raise ValueError
        return created_at, document_id, due_date, score, sort_value, counts
    except (signing.BadSignature, KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid page cursor") from exc


def _next_page_cursor(document, owner, query, view, filters, sort, counts):
    sort_value = document.sort_title if sort in {"title_asc", "title_desc"} else document.document_date.isoformat() if sort in {"document_newest", "document_oldest"} and document.document_date else None
    return signing.dumps({
        "owner": str(owner.pk), "query": query, "view": view, "filters": filters, "sort": sort,
        "created_at": (document.trashed_at if view == "trash" else document.created_at).isoformat(), "id": str(document.id),
        "due_date": document.action_due_date.isoformat() if document.action_due_date else None,
        "score": int(getattr(document, "search_score", 0)) if sort == "relevance" and view == "search" else None,
        "sort_value": sort_value,
        "counts": counts,
    }, salt=CURSOR_SALT)


def _payload(request):
    try:
        value = json.loads(request.body)
        return value if isinstance(value, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _excerpt(text, query):
    if not text or not query:
        return ""
    match = re.search(re.escape(query), text, re.IGNORECASE)
    if match is None:
        terms = sorted(set(re.findall(r"\w+", query)), key=lambda value: (-len(value), value.casefold()))
        for term in terms:
            if len(term) < 2:
                continue
            match = re.search(re.escape(term), text, re.IGNORECASE)
            if match:
                break
    if match is None:
        return ""
    start = max(0, match.start() - 32)
    end = min(len(text), match.end() + 120, start + 240)
    excerpt = " ".join(text[start:end].split())
    return ("…" if start else "") + excerpt + ("…" if end < len(text) else "")


def _search_snippet(document, query):
    if not query:
        return "", None
    for text, source in ((document.extracted_text, "document"), (document.action_note, "note")):
        excerpt = _excerpt(text, query)
        if excerpt:
            return excerpt, source
    for note in getattr(document, "matching_notes", ()):
        excerpt = _excerpt(note.body, query)
        if excerpt:
            return excerpt, "note"
    for value in getattr(document, "matching_custom_fields", ()):
        return f"{value.field.name}: {value.value}", "field"
    for copy in document.physical_copies.all():
        if query.casefold() in copy.sticker_code.casefold():
            return copy.sticker_code, "sticker"
    return "", None


def _note_json(note):
    return {"id": str(note.id), "body": note.body, "author": note.author.get_username(), "created_at": note.created_at.isoformat()}


def _document_json(document, query=""):
    snippet, snippet_source = _search_snippet(document, query)
    return {
        "id": str(document.id),
        "title": document.title,
        "original_name": document.original_name,
        "duplicate_of": {"id": str(document.duplicate_of_id), "title": document.duplicate_of.title} if document.duplicate_of_id and not document.duplicate_of.trashed_at else None,
        "duplicate_reviewed_at": document.duplicate_reviewed_at.isoformat() if document.duplicate_reviewed_at else None,
        "source": document.source,
        "status": document.status,
        "archive_available": bool(document.archive_path) and document.status == Document.Status.READY,
        "error": document.error,
        "created_at": document.created_at.isoformat(),
        "trashed_at": document.trashed_at.isoformat() if document.trashed_at else None,
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
        "snippet": snippet,
        "snippet_source": snippet_source,
        "email": _email_json(document),
        "asn": document.asn,
        "split_parent": {"id": str(document.split_parent_id), "title": document.split_parent.title} if document.split_parent_id else None,
        "is_split_source": document.is_split_source,
    }


def _email_json(document):
    try:
        origin = document.email
    except ObjectDoesNotExist:
        return None
    return {
        "account": origin.account_name, "sender": origin.sender, "subject": origin.subject,
        "received_at": origin.received_at.isoformat() if origin.received_at else None,
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
    throttle_key = sign_in_throttle_key(request, body.get("username"))
    if sign_in_blocked(throttle_key):
        return JsonResponse({"error": "Too many sign-in attempts. Wait a few minutes and try again."}, status=429)
    user = authenticate(request, username=body.get("username"), password=body.get("password"))
    if user is None:
        record_sign_in_failure(throttle_key)
        return JsonResponse({"error": "Invalid credentials"}, status=401)
    if two_factor.is_enabled(user):
        code = str(body.get("code") or "").strip()
        if not code:
            return JsonResponse({"error": "Enter the 6-digit code from your authenticator app", "two_factor_required": True}, status=401)
        ok, message = two_factor.verify(user, code)
        if not ok:
            record_sign_in_failure(throttle_key)
            return JsonResponse({"error": message, "two_factor_required": True}, status=401)
    login(request, user)
    request.session[two_factor.SESSION_FLAG] = True
    return JsonResponse({"authenticated": True, "username": user.get_username()})


@require_http_methods(["GET", "POST"])
def documents(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        if "offset" in request.GET:
            return JsonResponse({"error": "Use a page cursor"}, status=400)
        requested_view = request.GET.get("view")
        if requested_view not in (None, "documents", "actions", "exceptions", "trash"):
            return JsonResponse({"error": "Invalid document view"}, status=400)
        queryset = Document.objects.filter(owner=request.user, trashed_at__isnull=requested_view != "trash").select_related(
            "duplicate_of", "correspondent", "document_type", "email", "split_parent").prefetch_related("tag_links__tag", "physical_copies__location")
        if requested_view not in ("trash", "exceptions"):
            # A scan split at separator sheets is reached from its parts; it still shows in Trash and Exceptions.
            queryset = queryset.filter(is_split_source=False)
        query = request.GET.get("q", "").strip()[:200]
        try:
            free_query, clauses = _parse_search(query)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        filters = {}
        for key in ("tag_id", "correspondent_id", "document_type_id", "custom_field_id"):
            raw = request.GET.get(key, "")
            if raw:
                try:
                    filters[key] = str(UUID(raw))
                except (TypeError, ValueError, AttributeError):
                    return JsonResponse({"error": f"Invalid {key.replace('_', ' ')}"}, status=400)
        for key in ("date_from", "date_to"):
            raw = request.GET.get(key, "")
            if raw:
                try:
                    filters[key] = date.fromisoformat(raw).isoformat()
                except (TypeError, ValueError):
                    return JsonResponse({"error": f"Invalid {key.replace('_', ' ')}"}, status=400)
        if filters.get("date_from") and filters.get("date_to") and filters["date_from"] > filters["date_to"]:
            return JsonResponse({"error": "Start date must be before end date"}, status=400)
        custom_value = request.GET.get("custom_value", "").strip()
        custom_min = request.GET.get("custom_min", "").strip()
        custom_max = request.GET.get("custom_max", "").strip()
        if any((custom_value, custom_min, custom_max)) and not filters.get("custom_field_id"):
            return JsonResponse({"error": "Choose a custom field before its value"}, status=400)
        if max(map(len, (custom_value, custom_min, custom_max))) > 500:
            return JsonResponse({"error": "Custom field value is too long"}, status=400)
        if custom_value and (custom_min or custom_max):
            return JsonResponse({"error": "Use an exact value or a range"}, status=400)
        if filters.get("custom_field_id"):
            definition = CustomField.objects.filter(pk=filters["custom_field_id"], owner=request.user).first()
            if definition is None:
                return JsonResponse({"error": "Custom field not found"}, status=400)
            filters.update(custom_value=custom_value, custom_min=custom_min, custom_max=custom_max)
            matches = CustomFieldValue.objects.filter(document_id=OuterRef("pk"), field=definition)
            if custom_value:
                try:
                    normalized = normalize_filter_value(definition, custom_value)
                except ValueError as exc:
                    return JsonResponse({"error": str(exc)}, status=400)
                matches = matches.filter(value__icontains=normalized) if definition.kind == CustomField.Kind.TEXT else matches.filter(value=normalized)
            try:
                custom_min, custom_max = normalize_filter_range(definition, custom_min, custom_max)
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            if custom_min or custom_max:
                if definition.kind == CustomField.Kind.NUMBER:
                    matches = matches.annotate(number_value=Cast("value", DecimalField(max_digits=24, decimal_places=6)))
                    if custom_min:
                        matches = matches.filter(number_value__gte=custom_min)
                    if custom_max:
                        matches = matches.filter(number_value__lte=custom_max)
                else:
                    if custom_min:
                        matches = matches.filter(value__gte=custom_min)
                    if custom_max:
                        matches = matches.filter(value__lte=custom_max)
            queryset = queryset.filter(Exists(matches))
        if "tag_id" in filters:
            tag_ids = _tag_subtree_ids(request.user, filters["tag_id"])
            queryset = queryset.filter(Exists(
                DocumentTag.objects.filter(document_id=OuterRef("pk"), tag_id__in=tag_ids)
            ))
        if "correspondent_id" in filters:
            queryset = queryset.filter(correspondent_id=filters["correspondent_id"])
        if "document_type_id" in filters:
            queryset = queryset.filter(document_type_id=filters["document_type_id"])
        if "date_from" in filters:
            queryset = queryset.filter(document_date__gte=filters["date_from"])
        if "date_to" in filters:
            queryset = queryset.filter(document_date__lte=filters["date_to"])
        for field, value in clauses:
            if field == "title":
                queryset = queryset.filter(title__icontains=value)
            elif field == "text":
                queryset = queryset.filter(extracted_text__icontains=value)
            elif field == "note":
                queryset = queryset.filter(Q(action_note__icontains=value) | Q(Exists(DocumentNote.objects.filter(document_id=OuterRef("pk"), body__icontains=value))))
            elif field == "tag":
                queryset = queryset.filter(Exists(Tag.objects.filter(document_links__document_id=OuterRef("pk"), name__icontains=value)))
            elif field == "sender":
                queryset = queryset.filter(correspondent__name__icontains=value)
            elif field == "type":
                queryset = queryset.filter(document_type__name__icontains=value)
            elif field == "asn":
                queryset = queryset.filter(asn=int(value))
            elif field == "sticker":
                queryset = queryset.filter(Exists(PhysicalCopy.objects.filter(document_id=OuterRef("pk"), sticker_code__icontains=value)))
            elif field == "field":
                name, raw_value = (part.strip() for part in value.split("=", 1))
                definition = CustomField.objects.filter(owner=request.user, name__iexact=name).first()
                if definition is None:
                    queryset = queryset.none()
                elif definition.kind == CustomField.Kind.TEXT:
                    queryset = queryset.filter(Exists(CustomFieldValue.objects.filter(document_id=OuterRef("pk"), field=definition, value__icontains=raw_value)))
                else:
                    try:
                        normalized = normalize_filter_value(definition, raw_value)
                    except ValueError as exc:
                        return JsonResponse({"error": str(exc)}, status=400)
                    queryset = queryset.filter(Exists(CustomFieldValue.objects.filter(document_id=OuterRef("pk"), field=definition, value=normalized)))
            else:
                queryset = queryset.filter(document_date=value)
        view = "trash" if requested_view == "trash" else "actions" if requested_view == "actions" else "exceptions" if requested_view == "exceptions" else "search" if free_query else "documents"
        requested_sort = request.GET.get("sort", "")
        if requested_sort and requested_sort not in LIBRARY_SORTS:
            return JsonResponse({"error": "Invalid sort order"}, status=400)
        if view in {"actions", "exceptions", "trash"}:
            if requested_sort:
                return JsonResponse({"error": "Sorting is available in the Library"}, status=400)
            sort = "actions" if view == "actions" else "newest"
        else:
            sort = requested_sort or ("relevance" if free_query else "newest")
            if sort == "relevance" and not free_query:
                return JsonResponse({"error": "Relevance needs search text"}, status=400)
        if view == "actions":
            queryset = queryset.filter(action_status=Document.ActionStatus.OPEN)
        elif view == "exceptions":
            queryset = queryset.filter(Q(status=Document.Status.FAILED) | Q(duplicate_of__isnull=False, duplicate_of__trashed_at__isnull=True, duplicate_reviewed_at__isnull=True))
        if free_query:
            queryset = queryset.annotate(
                tag_match=Exists(Tag.objects.filter(document_links__document_id=OuterRef("pk"), name__icontains=free_query)),
                sticker_match=Exists(PhysicalCopy.objects.filter(document_id=OuterRef("pk"), sticker_code__icontains=free_query)),
                note_match=Exists(DocumentNote.objects.filter(document_id=OuterRef("pk"), body__icontains=free_query)),
                field_match=Exists(CustomFieldValue.objects.filter(document_id=OuterRef("pk"), field__owner=request.user, value__icontains=free_query)),
            )
            if connection.vendor == "postgresql":
                vector = SearchVector("title", weight="A", config="simple") + SearchVector("extracted_text", weight="B", config="simple") + SearchVector("action_note", weight="C", config="simple")
                search_query = SearchQuery(free_query, search_type="plain", config="simple")
                queryset = queryset.annotate(
                    search_vector=vector,
                    search_score=Cast(SearchRank(vector, search_query) * 1000000, BigIntegerField()),
                ).filter(Q(search_vector=search_query) | Q(tag_match=True) | Q(sticker_match=True) | Q(note_match=True) | Q(field_match=True) | Q(correspondent__name__icontains=free_query) | Q(document_type__name__icontains=free_query))
            else:
                queryset = queryset.filter(Q(title__icontains=free_query) | Q(extracted_text__icontains=free_query) | Q(action_note__icontains=free_query) | Q(tag_match=True) | Q(sticker_match=True) | Q(note_match=True) | Q(field_match=True) | Q(correspondent__name__icontains=free_query) | Q(document_type__name__icontains=free_query))
        if view == "actions":
            queryset = queryset.order_by(F("action_due_date").asc(nulls_last=True), "-created_at", "-id")
        elif sort == "relevance" and connection.vendor == "postgresql":
            queryset = queryset.order_by("-search_score", "-created_at", "-id")
        elif sort == "oldest":
            queryset = queryset.order_by("created_at", "id")
        elif sort == "document_newest":
            queryset = queryset.order_by(F("document_date").desc(nulls_last=True), "-created_at", "-id")
        elif sort == "document_oldest":
            queryset = queryset.order_by(F("document_date").asc(nulls_last=True), "-created_at", "-id")
        elif sort == "title_asc":
            queryset = queryset.annotate(sort_title=Lower("title")).order_by("sort_title", "id")
        elif sort == "title_desc":
            queryset = queryset.annotate(sort_title=Lower("title")).order_by("-sort_title", "-id")
        elif view == "trash":
            queryset = queryset.order_by("-trashed_at", "-id")
        else:
            queryset = queryset.order_by("-created_at", "-id")

        cursor_raw = request.GET.get("cursor")
        if cursor_raw:
            try:
                created_at, document_id, due_date, score, sort_value, counts = _read_page_cursor(cursor_raw, request.user, query, view, filters, sort)
            except ValueError:
                return JsonResponse({"error": "Invalid page cursor"}, status=400)
            older = Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=document_id)
            newer = Q(created_at__gt=created_at) | Q(created_at=created_at, id__gt=document_id)
            if view == "actions":
                if due_date is None:
                    queryset = queryset.filter(Q(action_due_date__isnull=True) & older)
                else:
                    queryset = queryset.filter(Q(action_due_date__gt=due_date) | Q(action_due_date__isnull=True) | (Q(action_due_date=due_date) & older))
            elif sort == "relevance" and connection.vendor == "postgresql":
                queryset = queryset.filter(Q(search_score__lt=score) | (Q(search_score=score) & older))
            elif sort == "oldest":
                queryset = queryset.filter(newer)
            elif sort == "title_asc":
                queryset = queryset.filter(Q(sort_title__gt=sort_value) | Q(sort_title=sort_value, id__gt=document_id))
            elif sort == "title_desc":
                queryset = queryset.filter(Q(sort_title__lt=sort_value) | Q(sort_title=sort_value, id__lt=document_id))
            elif sort in {"document_newest", "document_oldest"}:
                if sort_value is None:
                    queryset = queryset.filter(Q(document_date__isnull=True) & older)
                elif sort == "document_newest":
                    queryset = queryset.filter(Q(document_date__lt=sort_value) | Q(document_date__isnull=True) | (Q(document_date=sort_value) & older))
                else:
                    queryset = queryset.filter(Q(document_date__gt=sort_value) | Q(document_date__isnull=True) | (Q(document_date=sort_value) & older))
            elif view == "trash":
                queryset = queryset.filter(Q(trashed_at__lt=created_at) | Q(trashed_at=created_at, id__lt=document_id))
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
        snippet_query = free_query or next((value.split("=", 1)[1] if field == "field" else value for field, value in clauses if field in {"text", "note", "sticker", "field"}), "")
        if snippet_query:
            prefetch_related_objects(visible, Prefetch("notes", queryset=DocumentNote.objects.filter(body__icontains=snippet_query), to_attr="matching_notes"))
            prefetch_related_objects(visible, Prefetch("custom_values", queryset=CustomFieldValue.objects.filter(field__owner=request.user, value__icontains=snippet_query).select_related("field"), to_attr="matching_custom_fields"))
        return JsonResponse({
            "documents": [_document_json(doc, query=snippet_query) for doc in visible],
            "next_cursor": _next_page_cursor(visible[-1], request.user, query, view, filters, sort, counts) if len(page) > 50 else None,
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
        existing = Document.objects.filter(owner=request.user, source=Document.Source.ANDROID, source_ref=scan_id).select_related("duplicate_of", "correspondent", "document_type", "email", "split_parent").prefetch_related("tag_links__tag", "physical_copies__location").first()
        if existing:
            if existing.trashed_at:
                return JsonResponse({"error": "This scan is in Trash. Restore it before retrying."}, status=409)
            return JsonResponse(_document_json(existing), status=200)
    try:
        document = ingest_document(request.user, upload, source=Document.Source.ANDROID if scan_id else Document.Source.WEB, source_ref=scan_id)
    except IntegrityError:
        if scan_id:
            existing = Document.objects.filter(owner=request.user, source=Document.Source.ANDROID, source_ref=scan_id).select_related("duplicate_of", "correspondent", "document_type", "email", "split_parent").prefetch_related("tag_links__tag", "physical_copies__location").first()
            if existing:
                if existing.trashed_at:
                    return JsonResponse({"error": "This scan is in Trash. Restore it before retrying."}, status=409)
                return JsonResponse(_document_json(existing), status=200)
        raise
    except InvalidDocument as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_document_json(document), status=202)


@require_http_methods(["POST"])
def bulk_document_tags(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    body = _payload(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    raw_ids = body.get("document_ids")
    if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= 100:
        return JsonResponse({"error": "Choose 1–100 documents"}, status=400)
    try:
        document_ids = {UUID(str(value)) for value in raw_ids}
        tag_id = UUID(str(body.get("tag_id")))
    except ValueError:
        return JsonResponse({"error": "Invalid document or tag ID"}, status=400)
    if len(document_ids) != len(raw_ids):
        return JsonResponse({"error": "Document IDs must be unique"}, status=400)
    action = body.get("action")
    if action not in {"add", "remove"}:
        return JsonResponse({"error": "Choose add or remove"}, status=400)
    with transaction.atomic():
        tag = Tag.objects.filter(pk=tag_id, owner=request.user).first()
        documents_to_change = list(Document.objects.select_for_update().filter(owner=request.user, trashed_at__isnull=True, pk__in=document_ids).order_by("pk"))
        if tag is None or len(documents_to_change) != len(document_ids):
            return JsonResponse({"error": "Document or tag not found"}, status=404)
        if action == "add":
            counts = dict(DocumentTag.objects.filter(document_id__in=document_ids).values("document_id").annotate(total=Count("id")).values_list("document_id", "total"))
            already_tagged = set(DocumentTag.objects.filter(document_id__in=document_ids, tag=tag).values_list("document_id", flat=True))
            if any(counts.get(document.id, 0) >= 100 and document.id not in already_tagged for document in documents_to_change):
                return JsonResponse({"error": "A document already has 100 tags"}, status=400)
        for document in documents_to_change:
            if action == "add":
                TagOverride.objects.filter(document=document, tag=tag).delete()
                DocumentTag.objects.update_or_create(document=document, tag=tag, defaults={"origin": DocumentTag.Origin.MANUAL})
            else:
                DocumentTag.objects.filter(document=document, tag=tag).delete()
                TagOverride.objects.get_or_create(document=document, tag=tag)
    return JsonResponse({"updated": len(documents_to_change), "action": action})


@require_http_methods(["POST"])
def bulk_document_filing(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    body = _payload(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    raw_ids = body.get("document_ids")
    if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= 100:
        return JsonResponse({"error": "Choose 1–100 documents"}, status=400)
    try:
        document_ids = {UUID(str(value)) for value in raw_ids}
    except ValueError:
        return JsonResponse({"error": "Invalid document ID"}, status=400)
    if len(document_ids) != len(raw_ids):
        return JsonResponse({"error": "Document IDs must be unique"}, status=400)
    field = body.get("field")
    if field not in {"correspondent", "document_type"}:
        return JsonResponse({"error": "Choose sender or document type"}, status=400)
    if "value_id" not in body:
        return JsonResponse({"error": "Choose a filing value or clear it"}, status=400)
    raw_value = body.get("value_id")
    try:
        value_id = UUID(str(raw_value)) if raw_value is not None else None
    except ValueError:
        return JsonResponse({"error": "Invalid filing ID"}, status=400)
    model = Correspondent if field == "correspondent" else DocumentType
    with transaction.atomic():
        item = model.objects.filter(pk=value_id, owner=request.user).first() if value_id else None
        documents_to_change = list(Document.objects.select_for_update().filter(owner=request.user, trashed_at__isnull=True, pk__in=document_ids).order_by("pk"))
        if len(documents_to_change) != len(document_ids) or (value_id and item is None):
            return JsonResponse({"error": "Document or filing choice not found"}, status=404)
        for document in documents_to_change:
            setattr(document, field, item)
            setattr(document, f"{field}_origin", Document.FilingOrigin.MANUAL)
            document.save(update_fields=[field, f"{field}_origin"])
    return JsonResponse({"updated": len(documents_to_change), "field": field, "value_id": str(value_id) if value_id else None})


@require_http_methods(["POST"])
def bulk_document_date(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    body = _payload(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    raw_ids = body.get("document_ids")
    if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= 100:
        return JsonResponse({"error": "Choose 1–100 documents"}, status=400)
    try:
        document_ids = {UUID(str(value)) for value in raw_ids}
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid document ID"}, status=400)
    if len(document_ids) != len(raw_ids):
        return JsonResponse({"error": "Document IDs must be unique"}, status=400)
    if "document_date" not in body:
        return JsonResponse({"error": "Choose a document date or clear it"}, status=400)
    raw_date = body["document_date"]
    if raw_date is None:
        document_date = None
    elif isinstance(raw_date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
        try:
            document_date = date.fromisoformat(raw_date)
        except ValueError:
            return JsonResponse({"error": "Use a valid date (YYYY-MM-DD)"}, status=400)
    else:
        return JsonResponse({"error": "Use a valid date (YYYY-MM-DD)"}, status=400)
    with transaction.atomic():
        documents_to_change = list(Document.objects.select_for_update().filter(
            owner=request.user, trashed_at__isnull=True, pk__in=document_ids,
        ).order_by("pk"))
        if len(documents_to_change) != len(document_ids):
            return JsonResponse({"error": "Document not found"}, status=404)
        Document.objects.filter(owner=request.user, trashed_at__isnull=True, pk__in=document_ids).update(document_date=document_date)
    return JsonResponse({"updated": len(document_ids), "document_date": document_date.isoformat() if document_date else None})


@require_http_methods(["POST"])
def bulk_document_trash(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    body = _payload(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    raw_ids = body.get("document_ids")
    if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= 100:
        return JsonResponse({"error": "Choose 1–100 documents"}, status=400)
    try:
        document_ids = {UUID(str(value)) for value in raw_ids}
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid document ID"}, status=400)
    if len(document_ids) != len(raw_ids):
        return JsonResponse({"error": "Document IDs must be unique"}, status=400)
    action = body.get("action")
    if action not in {"trash", "restore"}:
        return JsonResponse({"error": "Choose trash or restore"}, status=400)
    with transaction.atomic():
        documents_to_change = list(Document.objects.select_for_update().filter(
            owner=request.user, pk__in=document_ids,
        ).order_by("pk"))
        if len(documents_to_change) != len(document_ids):
            return JsonResponse({"error": "Document not found"}, status=404)
        if action == "trash":
            if any(document.trashed_at for document in documents_to_change):
                return JsonResponse({"error": "A selected document is already in Trash"}, status=409)
            if any(document.status in {Document.Status.PENDING, Document.Status.PROCESSING} for document in documents_to_change):
                return JsonResponse({"error": "Wait for processing to finish before moving these documents to Trash"}, status=409)
            trashed_at = timezone.now()
            Document.objects.filter(owner=request.user, pk__in=document_ids).update(trashed_at=trashed_at)
            ShareLink.objects.filter(document_id__in=document_ids, revoked_at__isnull=True).update(revoked_at=trashed_at)
        else:
            if any(not document.trashed_at for document in documents_to_change):
                return JsonResponse({"error": "A selected document is not in Trash"}, status=409)
            Document.objects.filter(owner=request.user, pk__in=document_ids).update(trashed_at=None)
    return JsonResponse({"updated": len(document_ids), "action": action})


@require_http_methods(["POST"])
def bulk_reprocess_documents(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    body = _payload(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    raw_ids = body.get("document_ids")
    if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= 100:
        return JsonResponse({"error": "Choose 1–100 documents"}, status=400)
    try:
        document_ids = {UUID(str(value)) for value in raw_ids}
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid document ID"}, status=400)
    if len(document_ids) != len(raw_ids):
        return JsonResponse({"error": "Document IDs must be unique"}, status=400)
    mode = body.get("mode")
    if mode not in {"retry", "rebuild"}:
        return JsonResponse({"error": "Choose retry or rebuild"}, status=400)
    allowed = {Document.Status.FAILED} if mode == "retry" else {Document.Status.READY, Document.Status.FAILED}
    with transaction.atomic():
        documents_to_check = list(Document.objects.select_for_update().filter(
            owner=request.user, trashed_at__isnull=True, pk__in=document_ids,
        ).order_by("pk"))
        if len(documents_to_check) != len(document_ids):
            return JsonResponse({"error": "Document not found"}, status=404)
        scheduled = []
        skipped = []
        for document in documents_to_check:
            if document.status in allowed:
                document.status = Document.Status.PENDING
                document.error = ""
                document.processing_started_at = None
                document.save(update_fields=["status", "error", "processing_started_at"])
                scheduled.append(str(document.id))
            else:
                skipped.append(str(document.id))
    if scheduled:
        from .tasks import process_document

        for document_id in scheduled:
            try:
                process_document.delay(document_id)
            except Exception:
                logger.exception("Document processing queue unavailable; pending document will be reconciled: %s", document_id)
    return JsonResponse({"scheduled": len(scheduled), "skipped": len(skipped), "skipped_ids": skipped, "mode": mode})


@transaction.atomic
@require_http_methods(["GET", "PATCH"])
def document_detail(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    queryset = Document.objects
    if request.method == "PATCH":
        queryset = queryset.select_for_update(of=("self",))
    document = queryset.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).select_related("duplicate_of", "correspondent", "document_type", "email", "split_parent").prefetch_related("tag_links__tag", "physical_copies__location").first()
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
        if "asn" in body:
            asn = body["asn"]
            if asn is not None and (not isinstance(asn, int) or isinstance(asn, bool) or not 1 <= asn <= 999_999_999):
                return JsonResponse({"error": "ASN must be a whole number from 1 to 999999999"}, status=400)
            taken = Document.objects.filter(owner=request.user, asn=asn).exclude(pk=document.pk).first() if asn else None
            if taken:
                return JsonResponse({"error": f"ASN {asn} is already used by “{taken.title}”"}, status=409)
            document.asn = asn
            changes.append("asn")
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
        if "asn" in changes:
            try:
                with transaction.atomic():
                    Document.objects.filter(pk=document.pk).update(asn=document.asn)
            except IntegrityError:
                return JsonResponse({"error": f"ASN {document.asn} is already used by another document"}, status=409)
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
        # Filing changes trigger "updated" workflows; follow-up, ASN, and review clicks do not.
        if set(changes) & {"title", "document_date", "correspondent", "document_type"} or chosen is not None:
            # Workflow actions run after the owner's own change and never re-trigger themselves.
            run_for_document(document, Workflow.Trigger.UPDATED)
        document = Document.objects.filter(pk=document.id).select_related("duplicate_of", "correspondent", "document_type", "email", "split_parent").prefetch_related("tag_links__tag", "physical_copies__location").get()
    return JsonResponse(_document_json(document))


@require_http_methods(["GET"])
def document_filing_suggestions(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).only("id", "owner", "status", "trashed_at", "title", "correspondent_origin", "document_type_origin").annotate(text_start=Substr("extracted_text", 1, 1800)).first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    return JsonResponse(filing_suggestions(document))


@transaction.atomic
@require_http_methods(["GET", "POST"])
def document_notes(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    queryset = Document.objects.select_for_update() if request.method == "POST" else Document.objects
    document = queryset.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    if request.method == "GET":
        try:
            offset = int(request.GET.get("offset", "0"))
        except ValueError:
            return JsonResponse({"error": "Invalid note offset"}, status=400)
        if offset < 0:
            return JsonResponse({"error": "Invalid note offset"}, status=400)
        page = list(DocumentNote.objects.filter(document=document).select_related("author")[offset:offset + 51])
        return JsonResponse({"notes": [_note_json(note) for note in page[:50]], "next_offset": offset + 50 if len(page) > 50 else None})
    body = _payload(request)
    if body is None or not isinstance(body.get("body"), str) or not 1 <= len(body["body"].strip()) <= 2000:
        return JsonResponse({"error": "Note must be 1–2000 characters"}, status=400)
    note = DocumentNote.objects.create(document=document, author=request.user, body=body["body"].strip())
    return JsonResponse(_note_json(note), status=201)


@transaction.atomic
@require_http_methods(["DELETE"])
def document_note_detail(request, document_id, note_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if not Document.objects.select_for_update().filter(pk=document_id, owner=request.user, trashed_at__isnull=True).exists():
        return JsonResponse({"error": "Note not found"}, status=404)
    note = DocumentNote.objects.filter(pk=note_id, document_id=document_id).first()
    if note is None:
        return JsonResponse({"error": "Note not found"}, status=404)
    note.delete()
    return JsonResponse({"deleted": True})


@require_http_methods(["GET"])
def download_original(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    document = Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
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
    document = Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
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
    return _restart_document_processing(request, document_id, {Document.Status.FAILED}, "Only failed documents can be retried")


@require_http_methods(["POST"])
def reprocess_document(request, document_id):
    return _restart_document_processing(request, document_id, {Document.Status.READY, Document.Status.FAILED}, "Document is already being processed")


@require_http_methods(["POST"])
def trash_document(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id, owner=request.user).first()
        if document is None:
            return JsonResponse({"error": "Document not found"}, status=404)
        if document.trashed_at:
            return JsonResponse({"error": "Document is already in Trash"}, status=409)
        if document.status in {Document.Status.PENDING, Document.Status.PROCESSING}:
            return JsonResponse({"error": "Wait for processing to finish before moving this document to Trash"}, status=409)
        document.trashed_at = timezone.now()
        document.save(update_fields=["trashed_at"])
        ShareLink.objects.filter(document=document, revoked_at__isnull=True).update(revoked_at=document.trashed_at)
    return JsonResponse({"id": str(document.id), "trashed_at": document.trashed_at.isoformat()})


@require_http_methods(["POST"])
def restore_document(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id, owner=request.user, trashed_at__isnull=False).first()
        if document is None:
            return JsonResponse({"error": "Document not found in Trash"}, status=404)
        document.trashed_at = None
        document.save(update_fields=["trashed_at"])
    return JsonResponse({"id": str(document.id), "restored": True})


def _restart_document_processing(request, document_id, allowed_statuses, conflict):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
        if document is None:
            return JsonResponse({"error": "Document not found"}, status=404)
        if document.status not in allowed_statuses:
            return JsonResponse({"error": conflict}, status=409)
        document.status = Document.Status.PENDING
        document.error = ""
        document.processing_started_at = None
        document.save(update_fields=["status", "error", "processing_started_at"])
    try:
        from .tasks import process_document

        process_document.delay(str(document.id))
    except Exception:
        logger.exception("Document processing queue unavailable; pending document will be reconciled")
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
