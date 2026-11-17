"""External storage sources: connected storages that Ripiano polls as document inputs.

Each source has a connection (credentials encrypted at rest), a folder or prefix, filters, a recursive
option, and an after-import action (leave and remember, move to a processed folder, or delete). Every
file version is handled once: a "seen" record survives even if its document is later deleted.

New storage kinds implement the small Backend interface below.
"""

import fnmatch
import hashlib
import ipaddress
import logging
import socket
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files import File
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .ingestion import ingest_document
from .models import Document, DocumentTag, StorageSource, StorageSourceSeen
from .storage import SUPPORTED_EXTENSIONS, InvalidDocument

logger = logging.getLogger(__name__)
PREVIEW_LIMIT = 50
RUN_LIMIT = 200  # files imported per pass; the next pass continues
STALE_RUN = timedelta(minutes=30)

FILE_TYPES = {
    "pdf": {".pdf"},
    "image": {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".gif", ".bmp"},
    "office": {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf"},
    "email": {".eml", ".msg"},
}


class SourceError(Exception):
    """A user-presentable problem. Never contains credentials."""


@dataclass
class Entry:
    key: str  # full key/path in the storage
    relative: str  # path below the source folder
    size: int
    modified: datetime
    version: str  # ETag or similar; a changed file is a new version

    @property
    def name(self):
        return PurePosixPath(self.relative).name


# --- network policy -----------------------------------------------------------------

def _private(host):
    from .workflows import _blocked

    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)}
    except (OSError, UnicodeError) as exc:
        raise SourceError(f"The address {host} could not be found") from exc
    return any(_blocked(ipaddress.ip_address(address.split("%")[0])) for address in addresses)


def check_endpoint(source):
    """Only the archive owner may connect sources on the home network (for example MinIO on the NAS)."""
    if source.kind == StorageSource.Kind.FOLDER:
        if not source.owner.is_superuser:
            raise SourceError("Only the archive owner can import from folders on the NAS")
        return
    parts = urlsplit(source.endpoint)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise SourceError("The address must start with https:// or http://")
    if source.owner.is_superuser:
        return
    if _private(parts.hostname):
        raise SourceError("Only the archive owner can connect storage on the home network")
    if parts.scheme != "https":
        raise SourceError("Use https:// for storage on the internet")


# --- backends -----------------------------------------------------------------------------

def _prefix(value):
    value = (value or "").strip().lstrip("/")
    return value if not value or value.endswith("/") else value + "/"


class S3Backend:
    def __init__(self, source, transport=None):
        from .mail import MailError, decrypt_secret
        from .s3_input import S3Client, S3Error

        self.error = S3Error
        try:
            secret = decrypt_secret(source.secret)
        except MailError as exc:
            raise SourceError("The saved secret can no longer be read. Edit the source and enter it again.") from exc
        try:
            self.client = S3Client(endpoint=source.endpoint, bucket=source.bucket, access_key=source.username, secret_key=secret,
                                   region=source.region or "us-east-1", addressing=source.addressing, transport=transport)
        except S3Error as exc:
            raise SourceError(str(exc)) from exc
        self.root = _prefix(source.path)

    def _wrap(self, call, *args):
        try:
            return call(*args)
        except self.error as exc:
            raise SourceError(str(exc)) from exc

    def entries(self, recursive):
        def listing():
            for item in self.client.list(self.root, recursive=recursive):
                if not item.key.endswith("/"):
                    yield Entry(key=item.key, relative=item.key[len(self.root):], size=item.size, modified=item.last_modified, version=item.etag)
        try:
            yield from listing()
        except self.error as exc:
            raise SourceError(str(exc)) from exc

    def processed_entries(self, folder):
        try:
            for item in self.client.list(folder, recursive=True):
                if not item.key.endswith("/"):
                    yield Entry(key=item.key, relative=item.key[len(folder):], size=item.size, modified=item.last_modified, version=item.etag)
        except self.error as exc:
            raise SourceError(str(exc)) from exc

    def download(self, entry, handle, limit):
        self._wrap(self.client.download, entry.key, handle, limit)

    def move(self, entry, destination):
        self._wrap(self.client.copy, entry.key, destination)
        self._wrap(self.client.delete, entry.key)

    def delete(self, entry):
        self._wrap(self.client.delete, entry.key)

    def close(self):
        self.client.close()


def backend_for(source, transport=None):
    check_endpoint(source)
    if source.kind == StorageSource.Kind.S3:
        return S3Backend(source, transport=transport)
    if source.kind == StorageSource.Kind.WEBDAV:
        from .webdav import WebDAVBackend

        return WebDAVBackend(source, transport=transport)
    if source.kind == StorageSource.Kind.FOLDER:
        from .folder_source import FolderBackend

        return FolderBackend(source)
    raise SourceError("Unknown storage kind")


def document_source(source):
    """Which Document.Source label imported documents carry."""
    return {StorageSource.Kind.S3: Document.Source.S3, StorageSource.Kind.WEBDAV: Document.Source.WEBDAV,
            StorageSource.Kind.FOLDER: Document.Source.FOLDER}.get(source.kind, Document.Source.S3)


# --- filters -------------------------------------------------------------------------------

def _patterns(value):
    return [item.strip().casefold() for item in (value or "").split(",") if item.strip()]


def skip_reason(source, entry, processed_folder):
    """Why a file is not imported, or None when it matches every filter."""
    if processed_folder and entry.key.startswith(processed_folder):
        return "in the processed folder"
    suffix = PurePosixPath(entry.name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return "unsupported file type"
    if source.file_types and not any(suffix in FILE_TYPES.get(kind, set()) for kind in source.file_types):
        return "file type not selected"
    include = _patterns(source.include_patterns)
    if include and not any(fnmatch.fnmatch(entry.name.casefold(), pattern) for pattern in include):
        return "name does not match"
    exclude = _patterns(source.exclude_patterns)
    if any(fnmatch.fnmatch(entry.name.casefold(), pattern) or fnmatch.fnmatch(entry.relative.casefold(), pattern) for pattern in exclude):
        return "excluded by a pattern"
    if entry.size > min(source.max_size_mb * 1024 * 1024, settings.RIPIANO_MAX_UPLOAD_BYTES):
        return "too large"
    if source.modified_after and entry.modified.date() < source.modified_after:
        return "older than the date filter"
    return None


def reference(source, entry):
    return hashlib.sha256(f"{source.id}\0{entry.key}\0{entry.version}".encode()).hexdigest()


def processed_folder(source):
    if source.after != StorageSource.After.MOVE:
        return ""
    return _prefix(source.processed_path)


# --- running ---------------------------------------------------------------------------------

def _file(document, source):
    updates = []
    if source.correspondent_id and document.correspondent_origin == Document.FilingOrigin.NONE:
        document.correspondent_id, document.correspondent_origin = source.correspondent_id, Document.FilingOrigin.SOURCE
        updates += ["correspondent", "correspondent_origin"]
    if source.document_type_id and document.document_type_origin == Document.FilingOrigin.NONE:
        document.document_type_id, document.document_type_origin = source.document_type_id, Document.FilingOrigin.SOURCE
        updates += ["document_type", "document_type_origin"]
    if updates:
        document.save(update_fields=updates)
    for tag in source.tags.all():
        DocumentTag.objects.get_or_create(document=document, tag=tag, defaults={"origin": DocumentTag.Origin.SOURCE})


def preview(source, backend=None):
    """Dry run: what the next pass would import, without downloading or changing anything."""
    if source.kind == StorageSource.Kind.TELEGRAM:
        from .telegram import TelegramError, bot_name

        try:
            name = bot_name(source, backend)
        except TelegramError as exc:
            raise SourceError(str(exc)) from exc
        return {"matching": [], "skipped": {}, "already_imported": 0, "bot": name}
    backend = backend or backend_for(source)
    folder = processed_folder(source)
    seen = set(StorageSourceSeen.objects.filter(source=source).values_list("ref", flat=True))
    matching, skipped, already = [], {}, 0
    try:
        for entry in backend.entries(source.recursive):
            reason = skip_reason(source, entry, folder)
            if reason:
                skipped[reason] = skipped.get(reason, 0) + 1
            elif reference(source, entry) in seen:
                already += 1
            elif len(matching) < PREVIEW_LIMIT:
                matching.append({"path": entry.relative, "size": entry.size, "modified": entry.modified.isoformat()})
            else:
                skipped["more than shown"] = skipped.get("more than shown", 0) + 1
    finally:
        backend.close()
    return {"matching": matching, "skipped": skipped, "already_imported": already}


def run(source, backend=None, now=None):
    """Import new matching files, apply the after-import action, and expire old processed files. Returns how many were imported."""
    if source.kind == StorageSource.Kind.TELEGRAM:
        from .telegram import TelegramError, run_telegram

        try:
            return run_telegram(source, backend)
        except TelegramError as exc:
            raise SourceError(str(exc)) from exc
    now = now or datetime.now(dt_timezone.utc)
    backend = backend or backend_for(source)
    folder = processed_folder(source)
    imported = 0
    try:
        for entry in list(backend.entries(source.recursive)):
            if imported >= RUN_LIMIT:
                break
            if skip_reason(source, entry, folder):
                continue
            ref = reference(source, entry)
            if StorageSourceSeen.objects.filter(source=source, ref=ref).exists():
                continue
            document_ref = ref
            if not Document.objects.filter(owner=source.owner, source=document_source(source), source_ref=document_ref).exists():
                try:
                    with tempfile.TemporaryFile() as handle:
                        backend.download(entry, handle, settings.RIPIANO_MAX_UPLOAD_BYTES)
                        handle.seek(0)
                        with transaction.atomic():
                            document = ingest_document(source.owner, File(handle, name=entry.name), source=document_source(source),
                                                       source_ref=document_ref, queue=False)
                            _file(document, source)
                        from .tasks import process_document

                        try:
                            process_document.delay(str(document.id))
                        except Exception:  # noqa: BLE001 - the pending document is reconciled later
                            logger.warning("Queue unavailable; document %s will be reconciled", document.id)
                except InvalidDocument as error:
                    logger.info("Source %s skipped %s: %s", source.id, entry.key, error)
                    StorageSourceSeen.objects.get_or_create(source=source, ref=ref)
                    continue
                except IntegrityError:
                    if not Document.objects.filter(owner=source.owner, source=document_source(source), source_ref=document_ref).exists():
                        raise
                else:
                    imported += 1
            # The original is durable in Ripiano before anything happens to the file in the storage.
            if source.after == StorageSource.After.MOVE:
                backend.move(entry, f"{folder}{now:%Y-%m-%d}/{entry.relative}")
            elif source.after == StorageSource.After.DELETE:
                backend.delete(entry)
            StorageSourceSeen.objects.get_or_create(source=source, ref=ref)
        if folder and source.retention_days:
            cutoff = now - timedelta(days=source.retention_days)
            for entry in list(backend.processed_entries(folder)):
                if entry.modified < cutoff:
                    backend.delete(entry)
    finally:
        backend.close()
    return imported


def claim(source_id):
    """Mark a source as running unless another pass holds it; returns the source or None."""
    with transaction.atomic():
        source = StorageSource.objects.select_for_update().select_related("owner").filter(pk=source_id, enabled=True).first()
        if source is None or (source.running_since and timezone.now() - source.running_since < STALE_RUN):
            return None
        source.running_since = timezone.now()
        source.save(update_fields=["running_since"])
    return source


def run_claimed(source):
    """Run a claimed source and record the outcome on it."""
    error, imported = "", 0
    try:
        imported = run(source)
    except SourceError as exc:
        error = str(exc)
    except Exception:  # noqa: BLE001 - one broken source must not stop the others
        logger.exception("Storage source %s failed", source.id)
        error = "Something went wrong while checking this source. See the server log."
    StorageSource.objects.filter(pk=source.pk).update(
        running_since=None, last_checked_at=timezone.now(), last_error=error[:300], last_imported=imported,
        total_imported=F("total_imported") + imported,
    )
    return imported


def due_sources(now=None):
    now = now or timezone.now()
    for source in StorageSource.objects.filter(enabled=True).only("id", "kind", "last_checked_at", "poll_minutes"):
        # Telegram is checked every minute: a quick request, and senders expect a prompt answer.
        minutes = 1 if source.kind == StorageSource.Kind.TELEGRAM else max(1 if source.kind == StorageSource.Kind.FOLDER else 5, source.poll_minutes)
        if source.last_checked_at is None or now - source.last_checked_at >= timedelta(minutes=minutes) - timedelta(seconds=5):
            yield source.id
