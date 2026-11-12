"""Recoverable removal of live media after a document leaves the database."""

import os
from pathlib import Path

from django.conf import settings

from .backup import _hash_file, _valid_relative
from .models import Document


class PurgeError(RuntimeError):
    pass


def remove_job_media(job):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    to_remove = []
    for raw, expected_root, lookup in (
        (job.original_path, "originals", "original_path"),
        (job.archive_path, "archive", "archive_path"),
    ):
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
        if Document.objects.filter(**{lookup: raw}).exists():
            continue
        if not path.exists():
            continue
        if not path.is_file():
            raise PurgeError("Stored media path is not a file")
        if expected_root == "originals" and _hash_file(path) != job.original_sha256:
            raise PurgeError("Original checksum changed; file was left in place")
        to_remove.append(path)

    for path in to_remove:
        path.unlink(missing_ok=True)
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
