import hashlib
import json
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone
from pypdf import PdfWriter

from archive.ingestion import ingest_document
from archive.models import (Correspondent, Document, DocumentNote, DocumentTag, DocumentVersion, Location, PhysicalCopy, Tag,
                            Workflow)
from archive.portable import PortableError, export_archive, import_archive


def pdf(width):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=500)
    data = BytesIO()
    writer.write(data)
    return data.getvalue()


def build_archive(media):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    parent = Tag.objects.create(owner=owner, name="Home")
    child = Tag.objects.create(owner=owner, name="Bills", parent=parent)
    sender = Correspondent.objects.create(owner=owner, name="Acme")
    with override_settings(MEDIA_ROOT=media), patch("archive.ingestion.process_document.delay"):
        first = ingest_document(owner, SimpleUploadedFile("bill.pdf", pdf(300)))
        copy = ingest_document(owner, SimpleUploadedFile("again.pdf", pdf(300)))
    archive = media / "archive" / "aa" / f"{first.id}.pdf"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(pdf(310))
    Document.objects.filter(pk=first.pk).update(status=Document.Status.READY, archive_path=f"archive/aa/{first.id}.pdf",
                                                  correspondent=sender, extracted_text="Acme bill", asn=7, version_number=2)
    old = media / "originals" / "zz" / "old.pdf"
    old.parent.mkdir(parents=True)
    old.write_bytes(pdf(200))
    DocumentVersion.objects.create(document=first, number=1, note="Original upload", original_name="old.pdf", original_path="originals/zz/old.pdf",
                                   original_mime="application/pdf", original_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),
                                   original_size=old.stat().st_size, created_at=timezone.now() - timedelta(days=1))
    DocumentTag.objects.create(document=first, tag=child, origin=DocumentTag.Origin.MANUAL)
    DocumentNote.objects.create(document=first, author=owner, body="Paid")
    shelf = Location.objects.create(owner=owner, name="Shelf")
    box = Location.objects.create(owner=owner, name="Box", parent=shelf)
    PhysicalCopy.objects.create(document=first, sticker_code="R-TESTCOPY", location=box)
    flow = Workflow.objects.create(owner=owner, name="Tag", trigger=Workflow.Trigger.ADDED)
    flow.add_tags.add(child)
    return owner, first, copy


@pytest.mark.django_db(transaction=True)
def test_export_then_import_restores_records_and_byte_identical_files(tmp_path):
    media = tmp_path / "media"
    owner, first, copy = build_archive(media)
    export = tmp_path / "export"
    with override_settings(MEDIA_ROOT=media):
        counts, files = export_archive(export)
    assert counts["archive.Document"] == 2 and files == 4
    manifest = json.loads((export / "manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} >= {"originals/zz/old.pdf", f"archive/aa/{first.id}.pdf"}
    with pytest.raises(PortableError, match="empty"):
        export_archive(export)

    # Simulate a brand-new server: empty database and empty media folder.
    call_command("flush", interactive=False, verbosity=0)
    fresh = tmp_path / "fresh-media"
    with override_settings(MEDIA_ROOT=fresh):
        with pytest.raises(CommandError, match="--yes"):
            call_command("import_archive", str(export))
        call_command("import_archive", str(export), "--yes")
        with pytest.raises(PortableError, match="empty"):
            import_archive(export)

    restored = Document.objects.get(pk=first.pk)
    assert (restored.asn, restored.correspondent.name, restored.extracted_text, restored.version_number) == (7, "Acme", "Acme bill", 2)
    assert Document.objects.get(pk=copy.pk).duplicate_of_id == first.pk
    assert list(restored.tag_links.values_list("tag__name", "tag__parent__name", "origin")) == [("Bills", "Home", "manual")]
    assert DocumentNote.objects.get(document=restored).body == "Paid"
    assert PhysicalCopy.objects.get(document=restored).location.parent.name == "Shelf"
    assert list(Workflow.objects.get(name="Tag").add_tags.values_list("name", flat=True)) == ["Bills"]
    assert get_user_model().objects.get(username="owner").check_password("secure-password-1")
    for relative in (restored.original_path, restored.archive_path, "originals/zz/old.pdf"):
        assert (fresh / relative).read_bytes() == (media / relative).read_bytes()


@pytest.mark.django_db
def test_import_refuses_tampered_or_unsafe_exports(tmp_path):
    media = tmp_path / "media"
    build_archive(media)
    export = tmp_path / "export"
    with override_settings(MEDIA_ROOT=media):
        export_archive(export)
    get_user_model().objects.all().update(username="still-here")
    with override_settings(MEDIA_ROOT=tmp_path / "fresh"), pytest.raises(PortableError, match="empty"):
        import_archive(export)
    manifest = json.loads((export / "manifest.json").read_text())
    tampered = manifest["files"][0]
    (export / "media" / tampered["path"]).write_bytes(b"changed")
    with patch("archive.portable.get_user_model") as users, patch("archive.portable.apps.get_model") as models:
        users.return_value.objects.exists.return_value = False
        models.return_value.objects.exists.return_value = False
        with override_settings(MEDIA_ROOT=tmp_path / "fresh"), pytest.raises(PortableError, match="checksum"):
            import_archive(export)
        manifest["files"][0]["path"] = "../../etc/passwd"
        (export / "manifest.json").write_text(json.dumps(manifest))
        with override_settings(MEDIA_ROOT=tmp_path / "fresh"), pytest.raises(PortableError, match="Unexpected file path"):
            import_archive(export)
