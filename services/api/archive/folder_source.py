"""Folder backend for storage sources: subfolders of one NAS folder mounted at RIPIANO_SOURCES_ROOT.

Paths always stay inside the mounted root; symbolic links are never followed. Files changed within the
last minute are left for the next check, so a scanner that is still writing is not imported half-done.
"""

import os
import shutil
import time
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.conf import settings

from .storage_sources import Entry, SourceError

SETTLE_SECONDS = 60
MAX_ENTRIES = 20000
MAX_DEPTH = 25


def sources_root():
    return Path(settings.RIPIANO_SOURCES_ROOT)


def _clean(value):
    parts = [part for part in (value or "").replace("\\", "/").split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise SourceError("Folder names cannot contain “..”")
    return "/".join(parts)


class FolderBackend:
    def __init__(self, source, root=None, now=None):
        self.root = Path(root or (settings.RIPIANO_CONSUME_ROOT if source.builtin else sources_root()))
        if not self.root.is_dir():
            if source.builtin:
                raise SourceError("The consume folder is not mounted. Set RIPIANO_CONSUME_PATH in the stack (see the README).")
            raise SourceError("No NAS folder is mounted for sources. Set RIPIANO_SOURCES_PATH in the stack (see the README).")
        self.real_root = self.root.resolve()
        self.base = _clean(source.path)
        self.now = now or time.time()

    def close(self):
        pass

    def _path(self, key):
        path = self.root / _clean(key)
        # The parent must resolve inside the root; the final component is checked with lstat (no symlinks).
        if not path.parent.resolve().is_relative_to(self.real_root):
            raise SourceError("That folder is outside the mounted NAS folder")
        return path

    def _walk(self, start, recursive):
        top = self._path(start) if start else self.root
        if not top.is_dir() or top.is_symlink():
            raise SourceError(f"The folder “{start or '/'}” does not exist in the mounted NAS folder")
        pending, seen = [(top, 0)], 0
        while pending:
            folder, depth = pending.pop(0)
            try:
                items = sorted(os.scandir(folder), key=lambda item: item.name)
            except OSError as exc:
                raise SourceError(f"Ripiano cannot read the folder “{folder.relative_to(self.root)}” (check NAS permissions)") from exc
            for item in items:
                if item.is_symlink() or item.name.startswith("."):
                    continue  # hidden files and links are never imported
                if item.is_dir(follow_symlinks=False):
                    if recursive and depth < MAX_DEPTH:
                        pending.append((Path(item.path), depth + 1))
                    continue
                if not item.is_file(follow_symlinks=False):
                    continue
                stat = item.stat(follow_symlinks=False)
                seen += 1
                if seen > MAX_ENTRIES:
                    raise SourceError(f"The folder has more than {MAX_ENTRIES} files; choose a smaller folder")
                yield Path(item.path).relative_to(self.root).as_posix(), stat

    def entries(self, recursive):
        prefix = f"{self.base}/" if self.base else ""
        for key, stat in self._walk(self.base, recursive):
            if self.now - stat.st_mtime < SETTLE_SECONDS:
                continue  # still being written; the next check takes it
            yield Entry(key=key, relative=key[len(prefix):], size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime, dt_timezone.utc), version=f"{stat.st_size}-{stat.st_mtime_ns}")

    def processed_entries(self, folder):
        folder = _clean(folder)
        if not (self.root / folder).is_dir():
            return
        for key, stat in self._walk(folder, True):
            yield Entry(key=key, relative=key[len(folder) + 1:], size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime, dt_timezone.utc), version="")

    def download(self, entry, handle, limit):
        path = self._path(entry.key)
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except OSError as exc:
            raise SourceError(f"Ripiano cannot read “{entry.relative}” (check NAS permissions)") from exc
        with os.fdopen(descriptor, "rb") as source:
            copied = 0
            for chunk in iter(lambda: source.read(64 * 1024), b""):
                copied += len(chunk)
                if copied > limit:
                    raise SourceError("The file is larger than the upload limit")
                handle.write(chunk)

    def move(self, entry, destination):
        source, target = self._path(entry.key), self._path(destination)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{target.stem}-{int(time.time())}{target.suffix}")
            shutil.move(str(source), str(target))
        except OSError as exc:
            raise SourceError(f"Ripiano cannot move “{entry.relative}” (it needs write access to the mounted NAS folder)") from exc

    def delete(self, entry):
        try:
            self._path(entry.key).unlink(missing_ok=True)
        except OSError as exc:
            raise SourceError(f"Ripiano cannot delete “{entry.relative}” (it needs write access to the mounted NAS folder)") from exc
