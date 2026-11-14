import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from archive.browse_export import build_browse_tree
from archive.models import BrowseExportRun, Document, DocumentTag, Tag
from archive.tasks import build_browse_export


def make_document(owner, media, *, title="../Tax: 2026", name="statement.pdf"):
    original = b"%PDF-1.4\nOriginal statement"
    derived = b"%PDF-1.4\nSearchable statement"
    (media / "originals" / "ab").mkdir(parents=True, exist_ok=True)
    (media / "archive" / "ab").mkdir(parents=True, exist_ok=True)
    original_path = media / "originals" / "ab" / name
    archive_path = media / "archive" / "ab" / name
    original_path.write_bytes(original)
    archive_path.write_bytes(derived)
    document = Document.objects.create(
        owner=owner, title=title, original_name=name,
        original_path=f"originals/ab/{name}", original_mime="application/pdf",
        original_sha256=hashlib.sha256(original).hexdigest(), original_size=len(original),
        archive_path=f"archive/ab/{name}", extracted_text="Searchable statement",
        status=Document.Status.READY,
    )
    return document, original, derived


@pytest.mark.django_db
def test_browse_export_is_owner_scoped_readable_and_checksum_verified(tmp_path):
    owner = get_user_model().objects.create_superuser("browse-owner", password="secure-password-1")
    other = get_user_model().objects.create_user("browse-other", password="secure-password-2")
    media, backup = tmp_path / "media", tmp_path / "backup"
    document, original, derived = make_document(owner, media)
    make_document(other, media, name="private.pdf")
    tag = Tag.objects.create(owner=owner, name="Bills/Tax")
    DocumentTag.objects.create(document=document, tag=tag)
    client = Client()
    client.force_login(other)
    assert client.get("/api/browse-exports").status_code == 403
    assert client.post("/api/browse-exports").status_code == 403
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backup, RIPIANO_BROWSE_RETENTION=1):
        with patch("archive.browse_views.build_browse_export.delay"):
            started = client.post("/api/browse-exports")
        assert started.status_code == 202
        assert client.post("/api/browse-exports").status_code == 409
        run_id = started.json()["id"]
        build_browse_export(run_id)
        run = BrowseExportRun.objects.get(pk=run_id)
        assert run.status == BrowseExportRun.Status.COMPLETE and run.document_count == 1
        folder = backup / "browse" / "owners" / str(owner.pk) / "complete" / run.folder_name
        manifest = json.loads((folder / "manifest.json").read_text())
        assert manifest["kind"] == "nas_browse_copy" and len(manifest["documents"]) == 1
        entry = manifest["documents"][0]
        assert entry["id"] == str(document.id)
        assert ".." not in Path(entry["path"]).parts
        doc_folder = folder / entry["path"]
        assert (doc_folder / "original.pdf").read_bytes() == original
        assert (doc_folder / "searchable.pdf").read_bytes() == derived
        assert (doc_folder / "ocr.txt").read_text() == "Searchable statement"
        assert json.loads((doc_folder / "metadata.json").read_text())["tags"][0]["name"] == "Bills/Tax"
        assert (folder / entry["tag_paths"][0] / "original.pdf").read_bytes() == original
        assert manifest["documents"][0]["files"]["original.pdf"]["sha256"] == document.original_sha256
        assert build_browse_tree(run) == (run.folder_name, 1)
        listing = client.get("/api/browse-exports").json()["runs"]
        assert len(listing) == 1 and listing[0]["folder"].endswith(run.folder_name)

        second = BrowseExportRun.objects.create(owner=owner)
        build_browse_export(str(second.id))
        second.refresh_from_db()
        assert second.status == BrowseExportRun.Status.COMPLETE
        assert not folder.exists()
        assert client.get("/api/browse-exports").json()["runs"][1]["folder"] is None


@pytest.mark.django_db
def test_browse_export_does_not_publish_a_changed_original(tmp_path):
    owner = get_user_model().objects.create_superuser("browse-owner", password="secure-password-1")
    media, backup = tmp_path / "media", tmp_path / "backup"
    document, _, _ = make_document(owner, media)
    (media / document.original_path).write_bytes(b"changed")
    run = BrowseExportRun.objects.create(owner=owner)
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backup):
        build_browse_export(str(run.id))
        run.refresh_from_db()
        assert run.status == BrowseExportRun.Status.FAILED
        assert "original changed" in run.error
        complete = backup / "browse" / "owners" / str(owner.pk) / "complete"
        assert not list(complete.iterdir())
        staging = backup / "browse" / "owners" / str(owner.pk) / "staging"
        assert not list(staging.iterdir())
