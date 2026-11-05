"""Read-only NAS folder intake using the same durable pipeline as other inputs."""

import hashlib
import logging
import os
import time
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from archive.ingestion import ingest_document
from archive.models import Document
from archive.storage import InvalidDocument

logger = logging.getLogger(__name__)
EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


class FolderWatcher:
    def __init__(self, root: Path, owner):
        self.root = root.resolve(strict=True)
        self.owner = owner
        self.observed = {}
        self.rejected = {}

    def scan(self):
        """Only import files whose size and timestamp match the previous pass."""
        current = {}
        added = 0
        for path in self.root.rglob("*"):
            if path.suffix.lower() not in EXTENSIONS or path.is_symlink() or not path.is_file():
                continue
            try:
                if not path.resolve().is_relative_to(self.root):
                    continue
                stat = path.stat()
            except OSError:
                continue
            fingerprint = (stat.st_size, stat.st_mtime_ns)
            current[path] = fingerprint
            if stat.st_size > settings.RIPIANO_MAX_UPLOAD_BYTES:
                if self.rejected.get(path) != fingerprint:
                    logger.warning("Watched file exceeds the upload limit: %s", path)
                    self.rejected[path] = fingerprint
                continue
            if self.observed.get(path) != fingerprint or self.rejected.get(path) == fingerprint:
                continue
            try:
                added += self.import_file(path, fingerprint)
            except InvalidDocument as error:
                logger.warning("Watched file skipped: %s (%s)", path, error)
                self.rejected[path] = fingerprint
            except OSError as error:
                logger.warning("Watched file could not be read: %s (%s)", path, error)
        self.observed = current
        self.rejected = {path: fingerprint for path, fingerprint in self.rejected.items() if current.get(path) == fingerprint}
        return added

    def import_file(self, path: Path, fingerprint):
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
            stat = os.fstat(handle.fileno())
            if (stat.st_size, stat.st_mtime_ns) != fingerprint:
                return 0
            source_ref = hashlib.sha256(path.relative_to(self.root).as_posix().encode() + b"\0" + digest.digest()).hexdigest()
            if Document.objects.filter(owner=self.owner, source=Document.Source.FOLDER, source_ref=source_ref).exists():
                return 0
            handle.seek(0)
            try:
                ingest_document(self.owner, File(handle, name=path.name), source=Document.Source.FOLDER, source_ref=source_ref)
            except IntegrityError:
                # Another poller won the same source key after the existence check.
                if Document.objects.filter(owner=self.owner, source=Document.Source.FOLDER, source_ref=source_ref).exists():
                    return 0
                raise
            logger.info("Imported watched file %s", path)
            return 1


class Command(BaseCommand):
    help = "Import stable PDF/PNG/JPEG files from a read-only mounted folder"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Scan twice with a short delay, then exit")

    def handle(self, *args, **options):
        path = os.environ.get("RIPIANO_WATCH_PATH", "/watch")
        username = os.environ.get("RIPIANO_WATCH_OWNER_USERNAME", "")
        owner = get_user_model().objects.filter(username=username).first()
        if owner is None:
            raise CommandError("RIPIANO_WATCH_OWNER_USERNAME must name an existing account")
        root = Path(path)
        if not root.is_dir():
            raise CommandError(f"Watched directory is missing: {root}")
        try:
            interval = max(2, int(os.environ.get("RIPIANO_WATCH_POLL_SECONDS", "5")))
        except ValueError as error:
            raise CommandError("RIPIANO_WATCH_POLL_SECONDS must be an integer") from error
        watcher = FolderWatcher(root, owner)
        passes = 0
        while True:
            added = watcher.scan()
            passes += 1
            if added:
                self.stdout.write(f"Imported {added} document(s)")
            if options["once"] and passes >= 2:
                return
            time.sleep(interval)
