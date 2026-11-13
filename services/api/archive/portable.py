"""Portable whole-archive export and import (for moving to a new server or a later Ripiano version).

The export is a plain folder: `manifest.json` (every record, with stable IDs) and `media/` (every
original, older version, and searchable PDF, each listed with its SHA-256). Import loads it into an
empty instance and refuses to finish unless every file checksum matches.
"""

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import serializers
from django.db import connection, transaction

FORMAT = "ripiano-export"
FORMAT_VERSION = 1
# Runtime bookkeeping (jobs, cursors, audit noise) is not part of the archive.
SKIPPED = {"InputCursor", "BackupRun", "BrowseExportRun", "PurgeJob", "FilingModel"}


class PortableError(Exception):
    pass


def _models():
    user = get_user_model()
    archive = [model for model in apps.get_app_config("archive").get_models() if model.__name__ not in SKIPPED]
    # Groups first: people refer to them, and documents can be shared with them.
    return [Group, user, *archive]


def _hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _media_files():
    """Every stored file the database refers to, with the checksum the database expects (None if unknown)."""
    Document = apps.get_model("archive", "Document")
    DocumentVersion = apps.get_model("archive", "DocumentVersion")
    files = {}
    for path, digest, archive_path in Document.objects.values_list("original_path", "original_sha256", "archive_path"):
        files[path] = digest
        if archive_path:
            files.setdefault(archive_path, None)
    for path, digest in DocumentVersion.objects.values_list("original_path", "original_sha256"):
        files[path] = digest
    return files


def export_archive(destination):
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise PortableError("Choose an empty or new folder for the export")
    media_root = Path(settings.MEDIA_ROOT)
    (destination / "media").mkdir(parents=True, exist_ok=True)
    records = []
    for model in _models():
        batch = json.loads(serializers.serialize("json", model.objects.all().order_by("pk")))
        for record in batch:
            # Django permission IDs differ between databases, and Ripiano does not use them.
            record["fields"].pop("permissions", None)
            record["fields"].pop("user_permissions", None)
        records.extend(batch)
    listed = []
    for relative, expected in sorted(_media_files().items()):
        source = media_root / relative
        if not source.is_file():
            raise PortableError(f"Stored file is missing: {relative}")
        digest = _hash(source)
        if expected and digest != expected:
            raise PortableError(f"Stored file does not match its checksum: {relative}")
        target = destination / "media" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if _hash(target) != digest:
            raise PortableError(f"Copy changed while exporting: {relative}")
        listed.append({"path": relative, "sha256": digest, "size": target.stat().st_size})
    manifest = {
        "format": FORMAT, "format_version": FORMAT_VERSION, "exported_at": datetime.now(timezone.utc).isoformat(),
        "counts": {model._meta.label: model.objects.count() for model in _models()}, "files": listed, "records": records,
    }
    with open(destination / "manifest.json", "w", encoding="utf-8") as output:
        json.dump(manifest, output, ensure_ascii=False, indent=1)
        output.flush()
        os.fsync(output.fileno())
    return manifest["counts"], len(listed)


def import_archive(source):
    source = Path(source)
    try:
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PortableError("This folder has no readable manifest.json") from exc
    if manifest.get("format") != FORMAT or manifest.get("format_version") != FORMAT_VERSION:
        raise PortableError("This is not a Ripiano export this version can read")
    Document = apps.get_model("archive", "Document")
    if get_user_model().objects.exists() or Document.objects.exists():
        raise PortableError("Import only into a new, empty Ripiano (no accounts or documents yet)")
    media_root = Path(settings.MEDIA_ROOT)
    for item in manifest["files"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in {"originals", "archive"}:
            raise PortableError(f"Unexpected file path in export: {item['path']}")
        if _hash(source / "media" / relative) != item["sha256"]:
            raise PortableError(f"File does not match the export checksum: {item['path']}")
    copied = []
    try:
        with transaction.atomic():
            with connection.constraint_checks_disabled():
                for record in serializers.deserialize("json", json.dumps(manifest["records"])):
                    record.save()
            connection.check_constraints()
            for item in manifest["files"]:
                target = media_root / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / "media" / item["path"], target)
                copied.append(target)
                if _hash(target) != item["sha256"]:
                    raise PortableError(f"Copy changed while importing: {item['path']}")
            if connection.vendor == "postgresql":
                _reset_sequences()
    except Exception:
        for target in copied:
            target.unlink(missing_ok=True)
        raise
    return manifest["counts"], len(copied)


def _reset_sequences():
    from django.core.management.color import no_style

    statements = connection.ops.sequence_reset_sql(no_style(), _models())
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
