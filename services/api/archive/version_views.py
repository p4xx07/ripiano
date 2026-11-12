"""Owner-scoped endpoints for document versions and PDF page tools."""

import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Document, DocumentVersion
from .versions import VersionError, add_version, edit_pages, merge_documents, page_info, render_page, restore_version, split_pages


def _signed_in(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _document(request, document_id):
    return Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _error(exc):
    payload = {"error": str(exc)}
    if exc.code:
        payload["code"] = exc.code
    if exc.code == "signed":
        payload["signed"] = True
    return JsonResponse(payload, status=exc.status)


def _expected(body):
    value = (body or {}).get("version_number")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _summary(document):
    return {"id": str(document.id), "title": document.title, "status": document.status, "version_number": document.version_number,
            "revoked_shares": getattr(document, "revoked_shares", 0)}


def _version_json(version):
    return {"id": str(version.id), "number": version.number, "note": version.note, "original_name": version.original_name,
            "size": version.original_size, "created_at": version.created_at.isoformat(), "replaced_at": version.replaced_at.isoformat()}


@require_http_methods(["GET", "POST"])
def document_versions(request, document_id):
    denied = _signed_in(request)
    if denied:
        return denied
    document = _document(request, document_id)
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    if request.method == "POST":
        upload = request.FILES.get("file")
        if upload is None:
            return JsonResponse({"error": "Choose a file"}, status=400)
        raw = request.POST.get("version_number", "")
        try:
            document = add_version(document.id, request.user, upload, "Uploaded new version", expected_version=int(raw) if raw.isdigit() else None)
        except VersionError as exc:
            return _error(exc)
        return JsonResponse(_summary(document), status=202)
    return JsonResponse({
        "current": {"number": document.version_number, "note": document.version_note, "original_name": document.original_name,
                    "size": document.original_size, "created_at": (document.version_created_at or document.created_at).isoformat()},
        "versions": [_version_json(item) for item in document.versions.all()[:200]],
    })


@require_http_methods(["GET"])
def document_version_download(request, document_id, version_id):
    denied = _signed_in(request)
    if denied:
        return denied
    version = DocumentVersion.objects.filter(pk=version_id, document_id=document_id, document__owner=request.user, document__trashed_at__isnull=True).first()
    if version is None:
        return JsonResponse({"error": "Version not found"}, status=404)
    return FileResponse((Path(settings.MEDIA_ROOT) / version.original_path).open("rb"), content_type=version.original_mime,
                        as_attachment=True, filename=f"v{version.number}-{Path(version.original_name).name}")


@require_http_methods(["POST"])
def document_version_restore(request, document_id, version_id):
    denied = _signed_in(request)
    if denied:
        return denied
    document = _document(request, document_id)
    version = DocumentVersion.objects.filter(pk=version_id, document=document).first() if document else None
    if version is None:
        return JsonResponse({"error": "Version not found"}, status=404)
    try:
        document = restore_version(document, request.user, version, expected_version=_expected(_body(request)))
    except VersionError as exc:
        return _error(exc)
    return JsonResponse(_summary(document), status=202)


@require_http_methods(["GET", "POST"])
def document_pages(request, document_id):
    denied = _signed_in(request)
    if denied:
        return denied
    document = _document(request, document_id)
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    try:
        if request.method == "GET":
            return JsonResponse(page_info(document))
        body = _body(request)
        if body is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        document = edit_pages(document, request.user, body.get("order"), body.get("rotate", {}),
                              accept_signature_loss=body.get("accept_signature_loss") is True, expected_version=_expected(body))
    except VersionError as exc:
        return _error(exc)
    return JsonResponse(_summary(document), status=202)


@require_http_methods(["GET"])
def document_page_preview(request, document_id, number):
    denied = _signed_in(request)
    if denied:
        return denied
    document = _document(request, document_id)
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    try:
        path = render_page(document, number)
    except VersionError as exc:
        return _error(exc)
    except (subprocess.SubprocessError, OSError):
        return JsonResponse({"error": "Preview unavailable"}, status=503)
    response = FileResponse(path.open("rb"), content_type="image/png")
    response["Cache-Control"] = "private, max-age=3600"
    return response


@require_http_methods(["POST"])
def document_split(request, document_id):
    denied = _signed_in(request)
    if denied:
        return denied
    document = _document(request, document_id)
    body = _body(request)
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    try:
        created = split_pages(document, request.user, body.get("groups"), body.get("rotate"))
    except VersionError as exc:
        return _error(exc)
    return JsonResponse({"documents": [_summary(item) for item in created]}, status=201)


@require_http_methods(["POST"])
def documents_merge(request):
    denied = _signed_in(request)
    if denied:
        return denied
    body = _body(request)
    ids = body.get("document_ids") if body else None
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids) or len(ids) != len(set(ids)):
        return JsonResponse({"error": "Choose documents to merge"}, status=400)
    try:
        found = {str(item.id): item for item in Document.objects.filter(owner=request.user, trashed_at__isnull=True, pk__in=ids)}
    except Exception:  # noqa: BLE001 - malformed UUIDs
        found = {}
    if len(found) != len(ids):
        return JsonResponse({"error": "Document not found"}, status=404)
    try:
        merged = merge_documents([found[item] for item in ids], request.user)
    except VersionError as exc:
        return _error(exc)
    return JsonResponse(_summary(merged), status=201)
