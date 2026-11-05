"""Consistent PostgreSQL snapshots plus checksum-verified immutable media."""

import fcntl
import hashlib
import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone as django_timezone

from .models import BackupRun, Document

FORMAT_VERSION = 1
logger = logging.getLogger(__name__)


class BackupError(RuntimeError):
    pass


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sync_file(path):
    with path.open("rb") as source:
        os.fsync(source.fileno())


def _postgres_environment():
    database = settings.DATABASES["default"]
    if connection.vendor != "postgresql":
        raise BackupError("Backup and restore require PostgreSQL")
    environment = os.environ.copy()
    environment["PGPASSWORD"] = database.get("PASSWORD", "")
    return database, environment


def _database_command(command, dump, *, restore=False):
    database, environment = _postgres_environment()
    args = [
        command, "--host", database["HOST"], "--port", str(database["PORT"]),
        "--username", database["USER"], "--dbname", database["NAME"],
        "--no-owner", "--no-acl",
    ]
    if restore:
        args += ["--clean", "--if-exists", "--single-transaction", "--exit-on-error", str(dump)]
    else:
        args += ["--format=custom", "--file", str(dump)]
    try:
        subprocess.run(args, check=True, capture_output=True, text=True, env=environment, timeout=6 * 3600)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise BackupError(f"{command} failed; see container logs") from exc


def _applied_migrations():
    return sorted(f"{app}:{name}" for app, name in MigrationRecorder(connection).applied_migrations())


def _snapshots():
    complete = settings.RIPIANO_BACKUP_ROOT / "complete"
    if not complete.exists():
        return []
    return sorted(path for path in complete.iterdir() if path.is_dir() and (path / "manifest.json").is_file())


def _previous_files():
    snapshots = _snapshots()
    if not snapshots:
        return None, {}
    previous = snapshots[-1]
    try:
        manifest = json.loads((previous / "manifest.json").read_text())
        return previous, {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    except (KeyError, ValueError, OSError):
        return None, {}


def _valid_relative(path):
    relative = PurePosixPath(path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise BackupError("Snapshot contains an invalid media path")
    if relative.parts[0] not in {"originals", "archive"}:
        raise BackupError("Snapshot contains an unexpected media path")
    return Path(*relative.parts)


def _copy_media(stage):
    media_root = Path(settings.MEDIA_ROOT)
    previous, previous_hashes = _previous_files()
    files = []
    for source in sorted(media_root.rglob("*")):
        if source.is_symlink():
            raise BackupError("Media contains a symlink")
        if not source.is_file():
            continue
        relative = source.relative_to(media_root)
        if ".pending" in relative.parts:
            continue
        _valid_relative(relative.as_posix())
        digest = _hash_file(source)
        destination = stage / "media" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        previous_file = previous / "media" / relative if previous else None
        if previous_file and previous_hashes.get(relative.as_posix()) == digest and previous_file.is_file():
            try:
                os.link(previous_file, destination)
            except OSError:
                shutil.copy2(source, destination)
        else:
            shutil.copy2(source, destination)
        if _hash_file(destination) != digest:
            raise BackupError("Media changed during backup")
        _sync_file(destination)
        files.append({"path": relative.as_posix(), "size": destination.stat().st_size, "sha256": digest})
    return files


def create_snapshot():
    root = Path(settings.RIPIANO_BACKUP_ROOT)
    staging = root / "staging"
    complete = root / "complete"
    staging.mkdir(parents=True, exist_ok=True)
    complete.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    stage = staging / name
    destination = complete / name
    with (root / ".lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BackupError("Another backup is already running") from exc
        stage.mkdir()
        try:
            dump = stage / "database.dump"
            _database_command("pg_dump", dump)
            _sync_file(dump)
            files = _copy_media(stage)
            manifest = {
                "format_version": FORMAT_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "migrations": _applied_migrations(),
                "database": {"size": dump.stat().st_size, "sha256": _hash_file(dump)},
                "files": files,
            }
            with (stage / "manifest.json").open("w") as output:
                json.dump(manifest, output, indent=2, sort_keys=True)
                output.flush()
                os.fsync(output.fileno())
            verify_snapshot(stage, check_schema=False)
            for directory in sorted((stage / "media").rglob("*"), reverse=True) if (stage / "media").exists() else []:
                if directory.is_dir():
                    _sync_directory(directory)
            _sync_directory(stage)
            os.replace(stage, destination)
            _sync_directory(complete)
            snapshots = _snapshots()
            for old in snapshots[:-settings.RIPIANO_BACKUP_RETENTION]:
                shutil.rmtree(old)
            return destination
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def verify_snapshot(snapshot, *, check_schema=True):
    snapshot = Path(snapshot)
    try:
        manifest = json.loads((snapshot / "manifest.json").read_text())
    except (ValueError, OSError) as exc:
        raise BackupError("Snapshot manifest is missing or invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("format_version") != FORMAT_VERSION:
        raise BackupError("Unsupported snapshot format")
    if not isinstance(manifest.get("database"), dict) or not isinstance(manifest.get("files"), list):
        raise BackupError("Snapshot manifest is incomplete")
    if check_schema and manifest.get("migrations") != _applied_migrations():
        raise BackupError("Snapshot schema differs from this Ripiano release")
    dump = snapshot / "database.dump"
    if not dump.is_file() or dump.stat().st_size != manifest["database"]["size"] or _hash_file(dump) != manifest["database"]["sha256"]:
        raise BackupError("Database dump checksum failed")
    seen = set()
    for entry in manifest["files"]:
        relative = _valid_relative(entry["path"])
        if relative in seen:
            raise BackupError("Duplicate media path in snapshot")
        seen.add(relative)
        path = snapshot / "media" / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["size"] or _hash_file(path) != entry["sha256"]:
            raise BackupError("Media checksum failed")
    return manifest


def restore_snapshot(name):
    root = Path(settings.RIPIANO_BACKUP_ROOT)
    if Path(name).name != name:
        raise BackupError("Use a snapshot name from the complete directory")
    snapshot = root / "complete" / name
    if not snapshot.is_dir():
        raise BackupError("Snapshot does not exist")
    manifest = verify_snapshot(snapshot)
    if get_user_model().objects.exists() or Document.objects.exists():
        raise BackupError("Restore requires an empty Ripiano database")
    media_root = Path(settings.MEDIA_ROOT)
    if media_root.exists() and any(path.is_file() for path in media_root.rglob("*")):
        raise BackupError("Restore requires an empty media volume")
    copied = []
    try:
        for entry in manifest["files"]:
            relative = _valid_relative(entry["path"])
            destination = media_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(snapshot / "media" / relative, destination)
            copied.append(destination)
        _database_command("pg_restore", snapshot / "database.dump", restore=True)
    except Exception:
        for path in copied:
            path.unlink(missing_ok=True)
        raise
    if connection.vendor == "postgresql":
        connection.close()
    try:
        BackupRun.objects.filter(status=BackupRun.Status.RUNNING).update(
            status=BackupRun.Status.COMPLETE,
            snapshot_name=name,
            completed_at=django_timezone.now(),
            error="",
        )
    except Exception:
        logger.exception("Snapshot restored, but backup history could not be refreshed")
