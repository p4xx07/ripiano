import hashlib
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
import segno
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from PIL import Image, ImageDraw

from archive.barcodes import BarcodeScan, split_ranges

try:
    from pyzbar import pyzbar  # noqa: F401
    HAS_ZBAR = True
except ImportError:
    HAS_ZBAR = False
needs_zbar = pytest.mark.skipif(not HAS_ZBAR, reason="install the zbar library to read barcodes (Debian: libzbar0t64)")
from archive.ingestion import ingest_document
from archive.models import Document, DocumentNote, DocumentTag, Tag
from archive.tasks import process_document


def page(text=None, code=None):
    image = Image.new("RGB", (850, 1100), "white")
    if text:
        ImageDraw.Draw(image).text((80, 80), text, fill="black")
    if code:
        qr = BytesIO()
        segno.make(code, micro=False).save(qr, kind="png", scale=10, border=4)
        with Image.open(BytesIO(qr.getvalue())) as symbol:
            image.paste(symbol.convert("RGB"), (450, 700))
    return image


def pdf(*pages):
    output = BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=list(pages[1:]), resolution=100)
    return output.getvalue()


def fake_ocr(args, **kwargs):
    if args[0] == "gs" or str(args[0]).endswith("/gs"):
        raise AssertionError("Ghostscript must run for real")
    Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())


def process(document_id):
    real_run = __import__("subprocess").run

    def run(args, **kwargs):
        if args[0] == "gs":
            return real_run(args, **kwargs)
        return fake_ocr(args, **kwargs)

    with patch("archive.tasks.subprocess.run", side_effect=run), patch("archive.barcodes.subprocess.run", side_effect=run):
        process_document(document_id)


def test_separator_pages_are_dropped_and_empty_parts_ignored():
    scan = BarcodeScan(pages=7, separators=[0, 2, 3, 6])
    assert split_ranges(scan) == [(1, 2), (4, 6)]
    assert split_ranges(BarcodeScan(pages=3)) == [(0, 3)]


@needs_zbar
@pytest.mark.django_db
def test_separator_sheets_split_a_scan_and_parts_take_their_own_asn_and_tags(tmp_path, django_capture_on_commit_callbacks):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    bills = Tag.objects.create(owner=owner, name="Bills")
    scan = pdf(page("Letter one"), page(code="PATCHT"), page("Bill page 1", "ASN00042"), page("Bill page 2", "TAG:bills"))
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay") as queued:
        source = ingest_document(owner, SimpleUploadedFile("batch.pdf", scan))
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            process(str(source.id))
        source.refresh_from_db()
        assert source.is_split_source and source.status == Document.Status.READY and source.asn is None
        assert (tmp_path / source.original_path).read_bytes() == scan  # the full scan is preserved
        parts = list(Document.objects.filter(split_parent=source).order_by("title"))
        assert [part.title for part in parts] == ["batch (1/2)", "batch (2/2)"]
        assert len(callbacks) == 2 and queued.call_count == 3  # the upload, then each part after commit
        for part in parts:
            process(str(part.id))
    first, second = (Document.objects.get(pk=part.pk) for part in parts)
    assert first.asn is None and second.asn == 42
    assert DocumentTag.objects.get(document=second, tag=bills).origin == DocumentTag.Origin.SOURCE
    assert not Document.objects.filter(split_parent=first).exists()  # parts are never split again

    client = Client()
    client.force_login(owner)
    listed = {item["id"] for item in client.get("/api/documents").json()["documents"]}
    assert str(source.id) not in listed and {str(first.id), str(second.id)} <= listed
    assert [item["id"] for item in client.get("/api/documents", {"q": "asn:42"}).json()["documents"]] == [str(second.id)]
    detail = client.get(f"/api/documents/{second.id}").json()
    assert detail["asn"] == 42 and detail["split_parent"] == {"id": str(source.id), "title": "batch"}
    assert client.get(f"/api/documents/{source.id}").json()["is_split_source"] is True


@needs_zbar
@pytest.mark.django_db
def test_asn_is_unique_per_owner_and_editable(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        labelled = ingest_document(owner, SimpleUploadedFile("a.pdf", pdf(page("A", "ASN7"))))
        clash = ingest_document(owner, SimpleUploadedFile("b.pdf", pdf(page("B", "ASN 7"))))
        foreign = ingest_document(other, SimpleUploadedFile("c.pdf", pdf(page("C", "ASN7"))))
        for document in (labelled, clash, foreign):
            process(str(document.id))
    labelled.refresh_from_db(); clash.refresh_from_db(); foreign.refresh_from_db()
    assert (labelled.asn, clash.asn, foreign.asn) == (7, None, 7)
    assert "ASN 7 is already used" in DocumentNote.objects.get(document=clash).body

    client = Client()
    client.force_login(owner)
    response = client.patch(f"/api/documents/{clash.id}", {"asn": 7}, content_type="application/json")
    assert response.status_code == 409 and "already used" in response.json()["error"]
    assert client.patch(f"/api/documents/{clash.id}", {"asn": "8"}, content_type="application/json").status_code == 400
    assert client.patch(f"/api/documents/{clash.id}", {"asn": 8}, content_type="application/json").json()["asn"] == 8
    assert client.patch(f"/api/documents/{clash.id}", {"asn": None}, content_type="application/json").json()["asn"] is None
    assert client.get("/api/documents", {"q": "asn:seven"}).status_code == 400


@pytest.mark.django_db
@override_settings(RIPIANO_BARCODES=False)
def test_barcodes_can_be_turned_off(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        document = ingest_document(owner, SimpleUploadedFile("x.pdf", pdf(page("A"), page(code="PATCHT"), page("B", "ASN9"))))
        process(str(document.id))
    document.refresh_from_db()
    assert not document.is_split_source and document.asn is None
    assert hashlib.sha256((tmp_path / document.original_path).read_bytes()).hexdigest() == document.original_sha256


@needs_zbar
@pytest.mark.django_db
def test_reprocessing_never_splits_and_parts_keep_input_rule_filing(tmp_path, django_capture_on_commit_callbacks):
    from django.utils import timezone

    from archive.models import Correspondent, DocumentEmail

    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    sender = Correspondent.objects.create(owner=owner, name="Bank")
    mail_tag = Tag.objects.create(owner=owner, name="From mail")
    scan = pdf(page("Statement"), page(code="PATCHT"), page("Letter"))
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        curated = ingest_document(owner, SimpleUploadedFile("old.pdf", scan))
        Document.objects.filter(pk=curated.pk).update(processed_at=timezone.now())  # processed before barcodes existed
        process(str(curated.id))
        curated.refresh_from_db()
        assert not curated.is_split_source and not Document.objects.filter(split_parent=curated).exists()

        mailed = ingest_document(owner, SimpleUploadedFile("mailed.pdf", scan + b"\n"))
        Document.objects.filter(pk=mailed.pk).update(correspondent=sender, correspondent_origin=Document.FilingOrigin.SOURCE)
        DocumentTag.objects.create(document=mailed, tag=mail_tag, origin=DocumentTag.Origin.SOURCE)
        DocumentEmail.objects.create(document=mailed, account_name="Home", sender="bank@example.test", subject="Statement")
        with django_capture_on_commit_callbacks(execute=False):
            process(str(mailed.id))
    parts = Document.objects.filter(split_parent=mailed)
    assert parts.count() == 2
    for part in parts:
        assert part.correspondent == sender and part.correspondent_origin == Document.FilingOrigin.SOURCE
        assert DocumentTag.objects.get(document=part).tag == mail_tag
        assert DocumentEmail.objects.get(document=part).subject == "Statement"


@needs_zbar
@pytest.mark.django_db
def test_a_failed_split_keeps_the_scan_whole_and_leaves_no_orphan_files(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        document = ingest_document(owner, SimpleUploadedFile("batch.pdf", pdf(page("A"), page(code="PATCHT"), page("B"), page(code="PATCHT"), page("C"))))
        before = {path for path in (tmp_path / "originals").rglob("*") if path.is_file()}
        real_ingest = __import__("archive.ingestion", fromlist=["ingest_document"]).ingest_document
        calls = []

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 3:
                raise OSError("disk full")
            return real_ingest(*args, **kwargs)

        with patch("archive.ingestion.ingest_document", side_effect=flaky):
            process(str(document.id))
        after = {path for path in (tmp_path / "originals").rglob("*") if path.is_file()}
    document.refresh_from_db()
    assert document.status == Document.Status.READY and not document.is_split_source
    assert not Document.objects.filter(split_parent=document).exists()
    assert after == before
    assert "could not split" in DocumentNote.objects.get(document=document).body


@needs_zbar
@pytest.mark.django_db
def test_a_trashed_full_scan_appears_in_trash(tmp_path, django_capture_on_commit_callbacks):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        source = ingest_document(owner, SimpleUploadedFile("batch.pdf", pdf(page("A"), page(code="PATCHT"), page("B"))))
        with django_capture_on_commit_callbacks(execute=False):
            process(str(source.id))
    client = Client()
    client.force_login(owner)
    assert client.post(f"/api/documents/{source.id}/trash").status_code in (200, 204)
    trashed = {item["id"] for item in client.get("/api/documents", {"view": "trash"}).json()["documents"]}
    assert str(source.id) in trashed
