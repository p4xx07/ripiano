from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from pypdf import PdfWriter

from archive.email_render import msg_to_message, render_html
from archive.ingestion import ingest_document
from archive.models import Document
from archive.msg_fixture import build_msg
from archive.storage import InvalidDocument, save_original
from archive.tasks import process_document

MSG = build_msg("Avviso TARI <urgente>", "Comune", "tributi@comune.test", "Importo dovuto: 120 euro.\n<script>alert(1)</script>",
                [("avviso.pdf", b"%PDF-1.4 avviso" + b"0" * 6000)], "Date: Tue, 10 Nov 2026 09:30:00 +0100\r\n")


def test_outlook_messages_become_standard_emails_without_active_content(tmp_path):
    path = tmp_path / "notice.msg"
    path.write_bytes(MSG)
    message = msg_to_message(path)
    assert (message["Subject"], message["From"]) == ("Avviso TARI <urgente>", "Comune <tributi@comune.test>")
    assert [part.get_filename() for part in message.iter_attachments()] == ["avviso.pdf"]
    page = render_html(path, "application/vnd.ms-outlook")
    assert "Avviso TARI &lt;urgente&gt;" in page and "Importo dovuto: 120 euro." in page and "avviso.pdf" in page
    assert "<script" not in page


@pytest.mark.django_db
def test_msg_uploads_are_detected_titled_and_rendered(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    with override_settings(MEDIA_ROOT=tmp_path), pytest.raises(InvalidDocument):
        save_original(SimpleUploadedFile("fake.msg", b"not an outlook file"))
    with override_settings(MEDIA_ROOT=tmp_path), pytest.raises(InvalidDocument):
        save_original(SimpleUploadedFile("broken.msg", MSG[:700]))  # truncated compound file
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        document = ingest_document(owner, SimpleUploadedFile("notice.msg", MSG))
    assert (document.title, document.original_mime) == ("Avviso TARI <urgente>", "application/vnd.ms-outlook")

    def fake_convert(source, name, mime, destination):
        assert "Importo dovuto" in Path(source).read_text(encoding="utf-8")
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with Path(destination).open("wb") as output:
            writer.write(output)

    def fake_ocr(args, **kwargs):
        Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())

    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.tasks.convert_office", side_effect=fake_convert), patch("archive.tasks.subprocess.run", side_effect=fake_ocr):
        process_document(str(document.id))
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert (tmp_path / document.original_path).read_bytes() == MSG
