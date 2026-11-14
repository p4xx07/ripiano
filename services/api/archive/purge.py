"""Recoverable removal of live media after a document leaves the database."""

import os
import shutil
from pathlib import Path

from django.conf import settings

from .backup import _hash_file, _valid_relative
from .models import Document, DocumentVersion, PhysicalCopy, PurgeJob


class PurgeError(RuntimeError):
    pass


def remove_job_media(job):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    to_remove = []
    targets = [(job.original_path, "originals", "original_path", job.original_sha256), (job.archive_path, "archive", "archive_path", None)]
    targets += [(item.get("path", ""), "originals", "original_path", item.get("sha256", "")) for item in job.version_files or []]
    for raw, expected_root, lookup, expected_sha in targets:
        if not raw:
            continue
        try:
            relative = _valid_relative(raw)
        except Exception as exc:
            raise PurgeError("Stored media path is invalid") from exc
        if relative.parts[0] != expected_root:
            raise PurgeError("Stored media path has the wrong directory")
        path = media_root / relative
        if not path.resolve().is_relative_to(media_root) or any(
            (media_root / Path(*relative.parts[:index])).is_symlink()
            for index in range(1, len(relative.parts) + 1)
        ):
            raise PurgeError("Stored media path leaves the media volume")
        if Document.objects.filter(**{lookup: raw}).exists() or DocumentVersion.objects.filter(original_path=raw).exists():
            continue
        if not path.exists():
            continue
        if not path.is_file():
            raise PurgeError("Stored media path is not a file")
        if expected_root == "originals" and _hash_file(path) != expected_sha:
            raise PurgeError("Original checksum changed; file was left in place")
        to_remove.append(path)

    # Page previews are derived images; they must not outlive the document.
    previews = media_root / "previews" / str(job.document_id)[:2] / str(job.document_id)
    if previews.is_dir() and not previews.is_symlink():
        shutil.rmtree(previews, ignore_errors=True)
    for path in to_remove:
        path.unlink(missing_ok=True)
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)


def record_purge(document):
    """Remove a locked trashed document and leave a durable media cleanup job."""
    job = PurgeJob.objects.create(
        owner=document.owner, document_id=document.id, title=document.title,
        original_path=document.original_path, archive_path=document.archive_path,
        version_files=[{"path": item.original_path, "sha256": item.original_sha256} for item in document.versions.all()],
        original_sha256=document.original_sha256,
    )
    PhysicalCopy.objects.filter(document=document).delete()
    document.delete()
    return job
