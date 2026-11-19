import hashlib
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from pypdf import PdfWriter

from archive.email_render import inspect_eml, render_html
from archive.ingestion import ingest_document
from archive.models import Document
from archive.office import OLE_MAGIC, inspect_office
from archive.storage import InvalidDocument, save_original
from archive.tasks import process_document


def odf(kind, *, macro=False, mimetype=None, script=False, encrypted=False):
    data = BytesIO()
    with ZipFile(data, "w") as package:
        package.writestr("mimetype", mimetype or f"application/vnd.oasis.opendocument.{kind}", compress_type=ZIP_STORED)
        package.writestr("content.xml", "<office:document-content/>", compress_type=ZIP_DEFLATED)
        if macro:
            package.writestr("Basic/Standard/Module1.xml", "macro")
        if script:
            package.writestr("Scripts/python/run.py", "import os")
        if encrypted:
            package.writestr("META-INF/manifest.xml", "<manifest:encryption-data/>")
    return data.getvalue()


EMAIL = (
    b"From: Comune di Milano <tributi@comune.test>\r\nTo: me@example.test\r\nSubject: =?utf-8?q?Avviso_TARI_2026_=E2=82=AC?=\r\n"
    b"Date: Tue, 10 Nov 2026 09:30:00 +0100\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=b\r\n\r\n"
    b"--b\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
    b"<html><head><style>p{color:red}</style><script>alert(1)</script></head><body><p>Importo dovuto: <b>120 &euro;</b></p>"
    b"<img src=\"https://tracker.example/pixel.png\"><a href=\"https://phish.example\">Paga ora</a></body></html>\r\n"
    b"--b\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=\"avviso.pdf\"\r\n\r\n%PDF-1.4\r\n--b--\r\n"
)


@pytest.mark.parametrize(("name", "content", "mime"), [
    ("letter.odt", odf("text"), "application/vnd.oasis.opendocument.text"),
    ("budget.ods", odf("spreadsheet"), "application/vnd.oasis.opendocument.spreadsheet"),
    ("slides.odp", odf("presentation"), "application/vnd.oasis.opendocument.presentation"),
    ("old.doc", OLE_MAGIC + b"\0" * 504, "application/msword"),
    ("old.xls", OLE_MAGIC + b"\0" * 504, "application/vnd.ms-excel"),
    ("old.ppt", OLE_MAGIC + b"\0" * 504, "application/vnd.ms-powerpoint"),
    ("note.rtf", b"{\\rtf1\\ansi Hello}", "application/rtf"),
    ("bill.eml", EMAIL, "message/rfc822"),
])
def test_more_document_formats_are_accepted_by_content_not_just_name(tmp_path, name, content, mime):
    with override_settings(MEDIA_ROOT=tmp_path):
        path, detected, _, size = save_original(SimpleUploadedFile(name, content))
    assert detected == mime and size == len(content)
    assert (tmp_path / path).read_bytes() == content


@pytest.mark.parametrize(("name", "content"), [
    ("fake.doc", b"plain text pretending"),
    ("fake.rtf", b"not rtf"),
    ("macro.odt", odf("text", macro=True)),
    ("script.odt", odf("text", script=True)),
    ("locked.odt", odf("text", encrypted=True)),
    ("wrong.odt", odf("spreadsheet")),
    ("notmail.eml", b"just some words\nwithout headers\n"),
])
def test_disguised_or_risky_files_are_rejected(tmp_path, name, content):
    with override_settings(MEDIA_ROOT=tmp_path), pytest.raises(InvalidDocument):
        save_original(SimpleUploadedFile(name, content))
    assert inspect_office(Path(__file__), "report.pdf") is None
    assert inspect_eml(Path(__file__), "report.pdf") is None


def test_email_page_keeps_text_and_drops_anything_that_could_load_or_run(tmp_path):
    source = tmp_path / "bill.eml"
    source.write_bytes(EMAIL)
    page = render_html(source)
    assert "Avviso TARI 2026 €" in page and "Comune di Milano &lt;tributi@comune.test&gt;" in page
    assert "Importo dovuto: 120 €" in page and "avviso.pdf" in page
    for unsafe in ("<script", "alert(1)", "<img", "tracker.example", "href=", "color:red"):
        assert unsafe not in page
    headless = tmp_path / "headless.eml"
    headless.write_bytes(b"From: a@example.test\r\nSubject: Note\r\nContent-Type: text/html\r\n\r\n<html><head><meta charset=utf-8><body><p>Visible words</p></body></html>")
    assert "Visible words" in render_html(headless)


@pytest.mark.django_db
def test_uploaded_email_is_titled_by_subject_and_rendered_through_the_private_converter(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        document = ingest_document(owner, SimpleUploadedFile("message.eml", EMAIL))
    assert document.title == "Avviso TARI 2026 €" and document.original_mime == "message/rfc822"

    def fake_convert(source, name, mime, destination):
        assert name == "message.html" and mime == "text/html"
        assert "Importo dovuto" in Path(source).read_text(encoding="utf-8")
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with Path(destination).open("wb") as output:
            writer.write(output)

    def fake_ocr(args, **kwargs):
        Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())

    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.tasks.convert_office", side_effect=fake_convert), patch("archive.tasks.subprocess.run", side_effect=fake_ocr):
        process_document(str(document.id))
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert hashlib.sha256((tmp_path / document.original_path).read_bytes()).hexdigest() == hashlib.sha256(EMAIL).hexdigest()
