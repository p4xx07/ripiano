"""Portable single-document exports. The ZIP layout is intentionally simple and versioned."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from tempfile import TemporaryFile
from uuid import UUID
from zipfile import ZIP_STORED, ZipFile

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from .models import CustomFieldValue, Document, DocumentLink, DocumentNote, Movement
from .physical_views import location_path


def _media_path(value, folder):
    relative = PurePosixPath(value)
    root = Path(settings.MEDIA_ROOT).resolve()
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2 or relative.parts[0] != folder:
        raise ValueError("Invalid media path")
    path = (root / Path(*relative.parts)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Media file is missing")
    return path


def _add_file(bundle, source, name, mime):
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as input_file, bundle.open(name, "w") as output_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            output_file.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return {"path": name, "mime": mime, "size": size, "sha256": digest.hexdigest()}


def _write_files(bundle, document, prefix=""):
    extension = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}.get(document.original_mime, ".bin")
    original = _add_file(bundle, _media_path(document.original_path, "originals"), f"{prefix}original{extension}", document.original_mime)
    if original["sha256"] != document.original_sha256 or original["size"] != document.original_size:
        raise ValueError("Original checksum does not match the archive record")
    files = {"original": original}
    if document.status == Document.Status.READY and document.archive_path:
        files["searchable_pdf"] = _add_file(bundle, _media_path(document.archive_path, "archive"), f"{prefix}searchable.pdf", "application/pdf")
    if document.extracted_text:
        text = document.extracted_text.encode("utf-8")
        name = f"{prefix}ocr.txt"
        bundle.writestr(name, text)
        files["ocr_text"] = {"path": name, "mime": "text/plain; charset=utf-8", "size": len(text), "sha256": hashlib.sha256(text).hexdigest()}
    return files


def _metadata(document):
    copies = []
    for copy in document.physical_copies.select_related("location__parent__parent"):
        movements = Movement.objects.filter(physical_copy=copy).select_related("from_location__parent__parent", "to_location__parent__parent").order_by("created_at", "id")
        copies.append({
            "sticker_code": copy.sticker_code,
            "location": location_path(copy.location),
            "missing_at": copy.missing_at.isoformat() if copy.missing_at else None,
            "movements": [{
                "kind": move.kind, "from": location_path(move.from_location),
                "to": location_path(move.to_location), "note": move.note,
                "at": move.created_at.isoformat(),
            } for move in movements],
        })
    links = DocumentLink.objects.filter(left=document).select_related("right") | DocumentLink.objects.filter(right=document).select_related("left")
    related = []
    for link in links:
        other = link.right if link.left_id == document.id else link.left
        if other.owner_id == document.owner_id and other.trashed_at is None:
            related.append({"id": str(other.id), "title": other.title})
    return {
        "id": str(document.id), "title": document.title,
        "original_name": document.original_name, "source": document.source,
        "created_at": document.created_at.isoformat(),
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "correspondent": document.correspondent.name if document.correspondent_id else None,
        "document_type": document.document_type.name if document.document_type_id else None,
        "tags": [{"name": link.tag.name, "color": link.tag.color, "origin": link.origin} for link in document.tag_links.select_related("tag").order_by("tag__name")],
        "notes": [{"body": note.body, "created_at": note.created_at.isoformat()} for note in DocumentNote.objects.filter(document=document).order_by("created_at", "id")],
        "action": {"status": document.action_status, "due_date": document.action_due_date.isoformat() if document.action_due_date else None, "note": document.action_note},
        "duplicate_of": str(document.duplicate_of_id) if document.duplicate_of_id else None,
        "physical_copies": copies, "related_documents": sorted(related, key=lambda item: item["id"]),
        "custom_fields": [
            {"name": item.field.name, "kind": item.field.kind,
             "value": item.value == "true" if item.field.kind == "boolean" else item.value}
            for item in CustomFieldValue.objects.filter(document=document, field__owner=document.owner).select_related("field").order_by("field__name")
        ],
    }


@require_http_methods(["GET"])
def export_document(request, document_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    document = Document.objects.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).select_related("correspondent", "document_type").first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    output = TemporaryFile(mode="w+b")
    try:
        with ZipFile(output, "w", compression=ZIP_STORED) as bundle:
            files = _write_files(bundle, document)
            manifest = {"format_version": 1, "exported_at": datetime.now(timezone.utc).isoformat(), "document": _metadata(document), "files": files}
            bundle.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
        output.seek(0)
        return FileResponse(output, content_type="application/zip", as_attachment=True, filename=f"ripiano-{document.id}.zip")
    except (OSError, ValueError):
        output.close()
        return JsonResponse({"error": "Export could not verify the document files"}, status=503)


@require_http_methods(["GET"])
def export_documents(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    try:
        raw_ids = request.GET.getlist("document_ids")
        if not 1 <= len(raw_ids) <= 20:
            raise ValueError
        ids = [UUID(value) for value in raw_ids]
        if len(set(ids)) != len(ids):
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"error": "Select 1–20 distinct documents"}, status=400)
    found = Document.objects.filter(pk__in=ids, owner=request.user, trashed_at__isnull=True).select_related("correspondent", "document_type")
    by_id = {item.id: item for item in found}
    if len(by_id) != len(ids):
        return JsonResponse({"error": "A selected document was not found"}, status=404)
    output = TemporaryFile(mode="w+b")
    try:
        entries = []
        with ZipFile(output, "w", compression=ZIP_STORED) as bundle:
            for document_id in ids:
                document = by_id[document_id]
                prefix = f"documents/{document_id}/"
                entries.append({"id": str(document_id), "metadata": _metadata(document), "files": _write_files(bundle, document, prefix)})
            manifest = {"format_version": 1, "kind": "document_collection", "exported_at": datetime.now(timezone.utc).isoformat(), "documents": entries}
            bundle.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
        output.seek(0)
        return FileResponse(output, content_type="application/zip", as_attachment=True, filename="ripiano-documents.zip")
    except (OSError, ValueError):
        output.close()
        return JsonResponse({"error": "Export could not verify the selected document files"}, status=503)
