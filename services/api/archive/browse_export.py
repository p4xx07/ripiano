"""Build a disposable, human-readable NAS copy without changing managed originals."""

import hashlib
import json
import logging
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from django.conf import settings

from .backup import backup_media_lock
from .export_views import _media_path, _metadata
from .models import BrowseExportRun, Document
from .office import OFFICE_EXTENSIONS
from .storage_paths import fit_bytes, render

logger = logging.getLogger(__name__)
ORIGINAL_EXTENSIONS = {
    "application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "message/rfc822": ".eml", "application/vnd.ms-outlook": ".msg", **OFFICE_EXTENSIONS,
}


class BrowseExportError(RuntimeError):
    pass


def _component(value):
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "-", value)
    value = fit_bytes(re.sub(r"\s+", " ", value).strip(" .")[:80]).rstrip(" .")
    return value or "Untitled"


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes(path, data):
    with path.open("xb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _copy_file(source, destination, *, expected_size=None, expected_hash=None):
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as input_file, destination.open("xb") as output:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        output.flush()
        os.fsync(output.fileno())
    checksum = digest.hexdigest()
    if (expected_size is not None and size != expected_size) or (expected_hash is not None and checksum != expected_hash):
        raise BrowseExportError("A managed original changed during the NAS browse copy")
    return {"size": size, "sha256": checksum}


def _document_folder(stage, document):
    leaf = f"{_component(document.title)}--{document.id}"
    if document.storage_path_id:
        return stage.joinpath("documents", *render(document.storage_path.template, document), leaf)
    year = document.document_date.year if document.document_date else document.created_at.year
    return stage / "documents" / f"{year:04d}" / leaf


def _write_document(stage, document):
    folder = _document_folder(stage, document)
    folder.mkdir(parents=True)
    files = {}
    extension = ORIGINAL_EXTENSIONS.get(document.original_mime, ".bin")
    name = f"original{extension}"
    files[name] = _copy_file(
        _media_path(document.original_path, "originals"), folder / name,
        expected_size=document.original_size, expected_hash=document.original_sha256,
    )
    if document.status == Document.Status.READY and document.archive_path:
        files["searchable.pdf"] = _copy_file(_media_path(document.archive_path, "archive"), folder / "searchable.pdf")
    if document.extracted_text:
        files["ocr.txt"] = _write_bytes(folder / "ocr.txt", document.extracted_text.encode("utf-8"))
    metadata = _metadata(document)
    files["metadata.json"] = _write_bytes(
        folder / "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
    )
    tag_paths = []
    for link in document.tag_links.select_related("tag").order_by("tag__name", "tag_id"):
        tag = link.tag
        tag_folder = stage / "tags" / f"{_component(tag.name)}--{tag.id}" / folder.name
        tag_folder.mkdir(parents=True)
        for source in folder.iterdir():
            destination = tag_folder / source.name
            try:
                os.link(source, destination)
            except OSError:
                _copy_file(source, destination, expected_size=files[source.name]["size"], expected_hash=files[source.name]["sha256"])
        tag_paths.append(tag_folder.relative_to(stage).as_posix())
    return {
        "id": str(document.id), "path": folder.relative_to(stage).as_posix(),
        "tag_paths": tag_paths, "files": files,
    }


def _safe_path(root, value, prefix):
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != prefix:
        raise BrowseExportError("NAS browse manifest contains an unsafe path")
    path = root.joinpath(*relative.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise BrowseExportError("NAS browse copy contains an unsafe path")
    return path


def _verify_published(root, owner_id):
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink():
        raise BrowseExportError("NAS browse manifest is a link")
    try:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("format_version") != 1 or manifest.get("kind") != "nas_browse_copy" or manifest.get("owner_id") != str(owner_id):
            raise ValueError
        entries = manifest["documents"]
        if not isinstance(entries, list):
            raise ValueError
        for entry in entries:
            folder = _safe_path(root, entry["path"], "documents")
            files = entry["files"]
            tag_folders = [_safe_path(root, value, "tags") for value in entry["tag_paths"]]
            if not isinstance(files, dict) or not all(path.is_dir() for path in [folder, *tag_folders]):
                raise ValueError
            for name, expected in files.items():
                if Path(name).name != name or name in {"", ".", ".."}:
                    raise ValueError
                for parent in [folder, *tag_folders]:
                    file_path = parent / name
                    if file_path.is_symlink() or not file_path.resolve().is_relative_to(root.resolve()) or not file_path.is_file():
                        raise ValueError
                    if file_path.stat().st_size != expected["size"]:
                        raise ValueError
                    digest = hashlib.sha256()
                    with file_path.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != expected["sha256"]:
                        raise ValueError
        return len(entries)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise BrowseExportError("NAS browse copy checksum or manifest verification failed") from exc


def build_browse_tree(run):
    """Publish one all-or-nothing browse copy and return its folder/count."""
    root = Path(settings.RIPIANO_BACKUP_ROOT) / "browse" / "owners" / str(run.owner_id)
    staging = root / "staging"
    complete = root / "complete"
    folder_name = run.created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + run.id.hex[:8]
    stage = staging / folder_name
    destination = complete / folder_name
    with backup_media_lock():
        staging.mkdir(parents=True, exist_ok=True)
        complete.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink() or stage.is_symlink():
            raise BrowseExportError("The NAS browse output folder is an unsafe link")
        if destination.exists():
            return folder_name, _verify_published(destination, run.owner_id)
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir()
        try:
            documents = Document.objects.filter(owner_id=run.owner_id, trashed_at__isnull=True, is_split_source=False).select_related("correspondent", "document_type", "storage_path")
            entries = [_write_document(stage, document) for document in documents.order_by("id").iterator(chunk_size=100)]
            manifest = {
                "format_version": 1, "kind": "nas_browse_copy", "created_at": datetime.now(timezone.utc).isoformat(),
                "owner_id": str(run.owner_id), "documents": entries,
            }
            _write_bytes(stage / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
            _verify_published(stage, run.owner_id)
            for directory in sorted((path for path in stage.rglob("*") if path.is_dir()), key=lambda item: len(item.parts), reverse=True):
                _sync_directory(directory)
            _sync_directory(stage)
            os.replace(stage, destination)
            _sync_directory(complete)
            return folder_name, len(entries)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise


def prune_old_browse_trees(run):
    """Remove only previously tracked successful copies beyond retention."""
    complete = Path(settings.RIPIANO_BACKUP_ROOT) / "browse" / "owners" / str(run.owner_id) / "complete"
    old_runs = BrowseExportRun.objects.filter(owner_id=run.owner_id, status=BrowseExportRun.Status.COMPLETE).order_by("-created_at", "-id")
    for old in old_runs[settings.RIPIANO_BROWSE_RETENTION:]:
        if old.folder_name and Path(old.folder_name).name == old.folder_name:
            try:
                shutil.rmtree(complete / old.folder_name)
            except FileNotFoundError:
                pass
            except OSError:
                logger.exception("Could not prune browse copy %s", old.id)
