import os
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from archive.backup import BackupError, create_snapshot, restore_snapshot, verify_snapshot
from archive.models import BackupRun


def fake_database_command(command, dump, *, restore=False):
    if not restore:
        dump.write_bytes(b"test-database-dump")


@pytest.mark.django_db
def test_snapshot_checksums_hardlinks_retention_and_restore(tmp_path):
    media = tmp_path / "media"
    original = media / "originals" / "ab" / "example.pdf"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"original-v1")
    backup_root = tmp_path / "backups"
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backup_root, RIPIANO_BACKUP_RETENTION=2):
        with patch("archive.backup._database_command", side_effect=fake_database_command):
            first = create_snapshot()
            second = create_snapshot()
            assert verify_snapshot(second)["files"][0]["sha256"]
            assert os.stat(first / "media/originals/ab/example.pdf").st_ino == os.stat(second / "media/originals/ab/example.pdf").st_ino

            original.write_bytes(b"original-v2")
            third = create_snapshot()
            assert not first.exists()
            assert second.exists() and third.exists()
            assert (third / "media/originals/ab/example.pdf").read_bytes() == b"original-v2"

            empty_media = tmp_path / "restored-media"
            with override_settings(MEDIA_ROOT=empty_media):
                restore_snapshot(third.name)
                assert (empty_media / "originals/ab/example.pdf").read_bytes() == b"original-v2"


@pytest.mark.django_db
def test_tampered_snapshot_is_rejected(tmp_path):
    media = tmp_path / "media"
    original = media / "originals" / "ab" / "example.pdf"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"original")
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=tmp_path / "backups"):
        with patch("archive.backup._database_command", side_effect=fake_database_command):
            snapshot = create_snapshot()
        (snapshot / "media/originals/ab/example.pdf").write_bytes(b"tampered")
        with pytest.raises(BackupError, match="checksum"):
            verify_snapshot(snapshot)


@pytest.mark.django_db
def test_only_owner_can_trigger_backup():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    user = get_user_model().objects.create_user("user", password="secure-password-2")
    client = Client()
    client.force_login(user)
    assert client.get("/api/backups").status_code == 403
    assert client.post("/api/backups").status_code == 403
    client.force_login(owner)
    with patch("archive.views.backup_archive.delay"):
        response = client.post("/api/backups")
    assert response.status_code == 202
    assert BackupRun.objects.get(pk=response.json()["id"]).trigger == "manual"
