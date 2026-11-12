"""Document versions and PDF page tools. Every edit adds a version; no file is ever overwritten."""

import re
import shutil
import subprocess
import uuid
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import File
from django.db import transaction
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError

from .models import Document, DocumentVersion, ShareLink
from .storage import InvalidDocument, save_original

MAX_PAGES_EDITABLE = 500


class VersionError(ValueError):
    """A user-presentable reason a version or page edit cannot happen; `status` is the HTTP status."""

    def __init__(self, message, status=400, code=""):
        super().__init__(message)
        self.status = status
        self.code = code


def _media(path):
    return Path(settings.MEDIA_ROOT) / path


def _preview_dir(document):
    return _media(Path("previews") / str(document.id)[:2] / str(document.id))


def page_source(document):
    """The PDF page tools work on: the original when it is a PDF, otherwise the searchable PDF."""
    if document.original_mime == "application/pdf":
        return _media(document.original_path), "original"
    if document.archive_path and document.status == Document.Status.READY:
        return _media(document.archive_path), "searchable"
    raise VersionError("Page tools need a PDF. Wait until this document has finished processing.", 409)


def is_signed(path):
    """True when the PDF carries a digital signature: a byte range with signature contents, or a signature field."""
    with open(path, "rb") as source:
        data = source.read()
    if b"/ByteRange" in data and (re.search(rb"/Contents\s*<[0-9A-Fa-f]{64,}", data) or re.search(rb"/(?:Type|FT)\s*/Sig\b", data)):
        return True
    try:
        fields = PdfReader(BytesIO(data)).get_fields() or {}
    except (PyPdfError, ValueError, OSError):
        return False
    return any(field.get("/FT") == "/Sig" for field in fields.values())


def _open_reader(path):
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise VersionError("This PDF is password-protected, so its pages cannot be edited.")
        count = len(reader.pages)
    except VersionError:
        raise
    except (PyPdfError, OSError, ValueError) as exc:
        raise VersionError("This PDF could not be read.") from exc
    return reader, count


def page_info(document):
    path, source = page_source(document)
    _, count = _open_reader(path)
    return {"count": count, "source": source, "signed": is_signed(path), "version_number": document.version_number}


def render_page(document, number):
    """PNG preview of one page (1-based), cached per version."""
    cache = _preview_dir(document) / f"v{document.version_number}-{number}.png"
    if cache.exists():
        return cache
    path, _ = page_source(document)
    _, count = _open_reader(path)
    if not 1 <= number <= count:
        raise VersionError("Page not found", 404)
    cache.parent.mkdir(parents=True, exist_ok=True)
    partial = cache.with_name(f".{uuid.uuid4().hex}.part")
    try:
        subprocess.run(
            ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=png16m", "-r48", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
             f"-dFirstPage={number}", f"-dLastPage={number}", f"-sOutputFile={partial}", str(path)],
            check=True, capture_output=True, timeout=60,
        )
        with open(partial, "rb") as image:
            if image.read(8) != b"\x89PNG\r\n\x1a\n":
                raise subprocess.SubprocessError("no preview produced")
        partial.replace(cache)
    finally:
        partial.unlink(missing_ok=True)
    return cache


def _locked(document_id, owner, expected_version=None):
    document = Document.objects.select_for_update().filter(pk=document_id, owner=owner, trashed_at__isnull=True).first()
    if document is None:
        raise VersionError("Document not found", 404)
    if document.status in (Document.Status.PENDING, Document.Status.PROCESSING):
        raise VersionError("Wait until this document has finished processing.", 409)
    if document.is_split_source:
        raise VersionError("This full scan is kept unchanged. Edit its parts instead.", 409)
    if expected_version is not None and expected_version != document.version_number:
        raise VersionError("This document changed since you opened it. Reload the pages and try again.", 409, "stale")
    return document


def add_version(document_id, owner, upload, note, *, expected_version=None):
    """Store a new current file for a document and queue processing. The previous file becomes a version.

    Active share links are revoked: they must never start serving different content.
    """
    from .tasks import process_document

    try:
        path, mime, digest, size = save_original(upload)
    except InvalidDocument as exc:
        raise VersionError(str(exc), 400) from exc
    try:
        with transaction.atomic():
            document = _locked(document_id, owner, expected_version)
            DocumentVersion.objects.create(
                document=document, number=document.version_number, note=document.version_note,
                original_name=document.original_name, original_path=document.original_path, original_mime=document.original_mime,
                original_sha256=document.original_sha256, original_size=document.original_size,
                created_at=document.version_created_at or document.created_at,
            )
            document.original_name = Path(upload.name).name[:500]
            document.original_path, document.original_mime, document.original_sha256, document.original_size = path, mime, digest, size
            document.version_number += 1
            document.version_note = note[:200]
            document.version_created_at = timezone.now()
            document.status = Document.Status.PENDING
            document.error = ""
            document.save(update_fields=["original_name", "original_path", "original_mime", "original_sha256", "original_size",
                                         "version_number", "version_note", "version_created_at", "status", "error"])
            document.revoked_shares = ShareLink.objects.filter(document=document, revoked_at__isnull=True, expires_at__gt=timezone.now()).update(revoked_at=timezone.now())
            transaction.on_commit(lambda: process_document.delay(str(document.id)), robust=True)
    except Exception:
        _media(path).unlink(missing_ok=True)
        raise
    # Previews of the replaced file are no longer shown.
    shutil.rmtree(_preview_dir(document), ignore_errors=True)
    return document


def _pdf_bytes(writer):
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _reader(document):
    path, source = page_source(document)
    reader, count = _open_reader(path)
    if count > MAX_PAGES_EDITABLE:
        raise VersionError(f"Page tools handle up to {MAX_PAGES_EDITABLE} pages.")
    return reader, source, is_signed(path)


def _rotations(rotations, count):
    if not isinstance(rotations, dict) or not all(str(key).isdigit() and int(key) < count and value in (0, 90, 180, 270) for key, value in rotations.items()):
        raise VersionError("Pages can be rotated by 90, 180, or 270 degrees.")
    return {int(key): value for key, value in rotations.items() if value}


def _new_pdf(reader, indexes, rotations):
    writer = PdfWriter()
    for index in indexes:
        page = writer.add_page(reader.pages[index])
        if rotations.get(index):
            page.rotate(rotations[index])
    try:
        return _pdf_bytes(writer)
    except (PyPdfError, ValueError) as exc:
        raise VersionError("This PDF could not be rewritten.") from exc


def edit_pages(document, owner, order, rotations, *, accept_signature_loss, expected_version=None):
    """Keep `order` (0-based page indexes, which may drop pages) and rotate pages; saved as a new version."""
    reader, _, signed = _reader(document)
    count = len(reader.pages)
    if not isinstance(order, list) or not order or len(order) != len(set(order)) or not all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < count for i in order):
        raise VersionError("Choose at least one page, each once.")
    rotations = _rotations(rotations, count)
    if order == list(range(count)) and not rotations:
        raise VersionError("Nothing changed.")
    if signed and not accept_signature_loss:
        raise VersionError("This PDF is digitally signed. Editing pages creates an unsigned new version; the signed file stays as an older version.", 409, "signed")
    dropped, turned = count - len(order), len(rotations)
    reordered = order != sorted(order)
    parts = [f"removed {dropped} page{'s' if dropped != 1 else ''}" if dropped else "", f"rotated {turned} page{'s' if turned != 1 else ''}" if turned else "", "reordered pages" if reordered else ""]
    note = "Edited pages: " + ", ".join(part for part in parts if part)
    name = f"{Path(document.original_name).stem}.pdf"
    return add_version(document.id, owner, File(BytesIO(_new_pdf(reader, order, rotations)), name=name), note, expected_version=expected_version)


def split_pages(document, owner, groups, rotations=None):
    """Create new documents from groups of 0-based pages (with optional rotations). The source is unchanged."""
    from .ingestion import ingest_document
    from .tasks import process_document

    reader, _, _ = _reader(document)
    count = len(reader.pages)
    if (not isinstance(groups, list) or len(groups) < 2 or len(groups) > 100
            or not all(isinstance(group, list) and group and all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < count for i in group) for group in groups)):
        raise VersionError("Choose at least two groups of pages.")
    rotations = _rotations(rotations or {}, count)
    created = []
    try:
        with transaction.atomic():
            for number, group in enumerate(groups, start=1):
                part = ingest_document(owner, File(BytesIO(_new_pdf(reader, group, rotations)), name=f"{Path(document.original_name).stem}-{number}.pdf"),
                                       title=f"{document.title} ({number}/{len(groups)})", queue=False)
                created.append(part)
                transaction.on_commit(lambda part_id=str(part.id): process_document.delay(part_id), robust=True)
    except InvalidDocument as exc:
        for part in created:
            _media(part.original_path).unlink(missing_ok=True)
        raise VersionError(str(exc)) from exc
    except Exception:
        for part in created:
            _media(part.original_path).unlink(missing_ok=True)
        raise
    return created


def merge_documents(documents, owner):
    """One new PDF document from several documents, in the given order. Sources are unchanged."""
    from .ingestion import ingest_document

    if not 2 <= len(documents) <= 50:
        raise VersionError("Choose 2–50 documents to merge.")
    writer = PdfWriter()
    total = 0
    for document in documents:
        try:
            reader, _, _ = _reader(document)
        except VersionError as exc:
            raise VersionError(f"“{document.title}”: {exc}", exc.status) from exc
        total += len(reader.pages)
        if total > MAX_PAGES_EDITABLE:
            raise VersionError(f"A merged PDF can have up to {MAX_PAGES_EDITABLE} pages.")
        for item in reader.pages:
            writer.add_page(item)
    title = "Merged: " + " + ".join(document.title for document in documents)
    try:
        return ingest_document(owner, File(BytesIO(_pdf_bytes(writer)), name="merged.pdf"), title=title[:300])
    except InvalidDocument as exc:
        raise VersionError(f"The merged PDF is too large: {exc}") from exc


def restore_version(document, owner, version, *, expected_version=None):
    """Make an earlier version current again by adding it as a new version; nothing is lost."""
    try:
        source = open(_media(version.original_path), "rb")
    except OSError as exc:
        raise VersionError("This stored version is unavailable. Restore it from a backup.", 503) from exc
    with source:
        return add_version(document.id, owner, File(source, name=version.original_name), f"Restored version {version.number}",
                           expected_version=expected_version)
