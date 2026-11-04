from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from PIL import Image

from archive.management.commands.watch_folder import FolderWatcher
from archive.models import Document


def png(color):
    output = BytesIO()
    Image.new("RGB", (8, 8), color).save(output, format="PNG")
    return output.getvalue()


@pytest.mark.django_db
def test_watched_folder_waits_for_stability_and_imports_each_revision_once(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    original = incoming / "document.png"
    original.write_bytes(png("white"))
    outside = tmp_path / "outside.png"
    outside.write_bytes(png("green"))
    (incoming / "link.png").symlink_to(outside)
    watcher = FolderWatcher(incoming, owner)

    with override_settings(MEDIA_ROOT=tmp_path / "media"):
        with patch("archive.ingestion.process_document.delay"):
            assert watcher.scan() == 0
            assert watcher.scan() == 1
            assert watcher.scan() == 0
            original.write_bytes(png("black"))
            assert watcher.scan() == 0
            assert watcher.scan() == 1
    assert Document.objects.filter(owner=owner, source=Document.Source.FOLDER).count() == 2
    assert original.read_bytes() == png("black")
    assert outside.read_bytes() == png("green")
