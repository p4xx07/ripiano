from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from pypdf import PdfWriter

from archive.date_detection import detect_date, matching_correspondent
from archive.ingestion import ingest_document
from archive.models import Correspondent, Document, DocumentEmail, DocumentEvent, MailAccount
from archive.tasks import process_document

FIXTURES = Path(__file__).resolve().parents[3] / "apps" / "web" / "e2e" / "fixtures"
TODAY = date(2026, 11, 18)


@pytest.mark.parametrize("text, expected", [
    ("Milano, 10/11/2025\nFattura n. 7", date(2025, 11, 10)),
    ("Data: 10.11.2025", date(2025, 11, 10)),
    ("Data 10-11-2025", date(2025, 11, 10)),
    ("Issued 2025-11-10 by Acme", date(2025, 11, 10)),
    ("emessa il 3/4/2025", date(2025, 4, 3)),
    ("Roma, 10 novembre 2025", date(2025, 11, 10)),
    ("Roma, 1° marzo 2026", date(2026, 3, 1)),
    ("Torino, 1 º Marzo 2026", date(2026, 3, 1)),
    ("Scadenza 5 dic. 2025", date(2025, 12, 5)),
    ("Dated 10 Nov 2025", date(2025, 11, 10)),
    ("Dated 3rd of March, 2025", date(2025, 3, 3)),
    ("Statement date: November 10, 2025", date(2025, 11, 10)),
    ("Sept 9th 2025 statement", date(2025, 9, 9)),
    ("Ricevuta 05/06/25", date(2025, 6, 5)),
    ("13/25/2025 is no date, 25/12/2024 is", date(2024, 12, 25)),
])
def test_formats_in_italian_english_and_numbers(text, expected):
    assert detect_date(text, today=TODAY) == expected


def test_ambiguous_numeric_dates_follow_the_configured_order():
    assert detect_date("04/05/2025", today=TODAY) == date(2025, 5, 4)
    with override_settings(RIPIANO_DATE_ORDER="MDY"):
        assert detect_date("04/05/2025", today=TODAY) == date(2025, 4, 5)
        # An impossible month-first reading still yields the only valid date.
        assert detect_date("25/12/2024", today=TODAY) == date(2024, 12, 25)
    with override_settings(RIPIANO_DATE_ORDER="YMD"):
        assert detect_date("Ref 25.06.30", today=TODAY) == date(2025, 6, 30)
        assert detect_date("2025-06-30", today=TODAY) == date(2025, 6, 30)


def test_future_and_ancient_dates_and_non_dates_are_ignored():
    assert detect_date("Valid until 31/12/2030, issued 01/02/2025", today=TODAY) == date(2025, 2, 1)
    assert detect_date("Tomorrow 19/11/2026", today=TODAY) == date(2026, 11, 19)
    assert detect_date("Founded 12/05/1850; printed 12/05/1990", today=TODAY) == date(1990, 5, 12)
    assert detect_date("Version 1.2.3, part 10.20.30.40, phone 02-12-34 56", today=TODAY) is None
    assert detect_date("Code 12.05.90 and 01/02/27", today=TODAY) is None  # two-digit years: 2000 to today only
    assert detect_date("Total 1.234,56 EUR; IBAN IT60X0542811101000000123456", today=TODAY) is None
    assert detect_date("", today=TODAY) is None and detect_date(None, today=TODAY) is None


def test_first_plausible_date_wins_over_later_ones():
    text = "Spett.le Rossi\nMilano, 2 ottobre 2025\nRif. fattura del 2025-01-15, scadenza 30/10/2025"
    assert detect_date(text, today=TODAY) == date(2025, 10, 2)
    assert detect_date("x" * 5000 + " 07/07/2025", today=TODAY) == date(2025, 7, 7)


def _pdf_bytes():
    from io import BytesIO

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    data = BytesIO()
    writer.write(data)
    return data.getvalue()


class _Page:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


def _process(document, tmp_path, text=""):
    def fake_ocr(args, **kwargs):
        Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())

    def fake_convert(source, name, mime, destination):
        Path(destination).write_bytes(_pdf_bytes())

    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False), patch("archive.tasks.subprocess.run", side_effect=fake_ocr), \
            patch("archive.tasks.convert_office", side_effect=fake_convert), \
            patch("archive.tasks.PdfReader", lambda path: type("R", (), {"pages": [_Page(text)]})()):
        process_document(str(document.id))
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    return document


def _upload(owner, tmp_path, name, data):
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        return ingest_document(owner, SimpleUploadedFile(name, data))


def _reprocess(client, document, tmp_path, text):
    with patch("archive.tasks.process_document.delay"):
        assert client.post(f"/api/documents/{document.id}/reprocess").status_code == 202
    return _process(document, tmp_path, text)


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1")


@pytest.mark.django_db
def test_processing_fills_an_empty_date_and_records_it(owner, tmp_path):
    document = _process(_upload(owner, tmp_path, "letter.pdf", _pdf_bytes()), tmp_path, "Milano, 10 novembre 2025\nGentile cliente")
    assert (document.document_date, document.document_date_origin) == (date(2025, 11, 10), Document.DateOrigin.DETECTED)
    event = DocumentEvent.objects.filter(document=document, actor_kind=DocumentEvent.ActorKind.DETECTION).get()
    assert event.action == DocumentEvent.Action.FILED_AUTOMATICALLY
    assert event.changes == [{"field": "document_date", "from": None, "to": "2025-11-10"}]
    # A detected date stays when the text later shows another one.
    client = Client()
    client.force_login(owner)
    document = _reprocess(client, document, tmp_path, "Roma, 01/01/2024")
    assert document.document_date == date(2025, 11, 10)


@pytest.mark.django_db
def test_detection_can_be_switched_off(owner, tmp_path):
    with override_settings(RIPIANO_DATE_DETECTION=False):
        document = _process(_upload(owner, tmp_path, "letter.pdf", _pdf_bytes()), tmp_path, "Milano, 10/11/2025")
    assert document.document_date is None and document.document_date_origin == Document.DateOrigin.NONE


@pytest.mark.django_db
def test_manual_dates_are_never_replaced_even_on_retry(owner, tmp_path):
    client = Client()
    client.force_login(owner)
    document = _upload(owner, tmp_path, "letter.pdf", _pdf_bytes())
    response = client.patch(f"/api/documents/{document.id}", {"document_date": "2024-02-03"}, content_type="application/json")
    assert response.status_code == 200 and response.json()["document_date_origin"] == "manual"
    document = _process(document, tmp_path, "Milano, 10/11/2025")
    assert document.document_date == date(2024, 2, 3)

    # Cleared by hand: stays empty through Retry OCR.
    assert client.patch(f"/api/documents/{document.id}", {"document_date": None}, content_type="application/json").status_code == 200
    document = _reprocess(client, document, tmp_path, "Milano, 10/11/2025")
    assert document.document_date is None and document.document_date_origin == Document.DateOrigin.MANUAL

    other = _upload(owner, tmp_path, "other.pdf", _pdf_bytes() + b"\n%other")
    assert client.post("/api/documents/bulk-date", {"document_ids": [str(other.id)], "document_date": None},
                       content_type="application/json").status_code == 200
    other = _process(other, tmp_path, "Milano, 10/11/2025")
    assert other.document_date is None and other.document_date_origin == Document.DateOrigin.MANUAL
    assert not DocumentEvent.objects.filter(actor_kind=DocumentEvent.ActorKind.DETECTION).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("fixture", ["email-notice.eml", "outlook-notice.msg"])
def test_email_uploads_take_the_date_header_and_a_known_sender(owner, tmp_path, fixture):
    expected_sender = "Comune di Esempio" if fixture.endswith(".eml") else "Amministrazione"
    sender = Correspondent.objects.create(owner=owner, name=expected_sender.upper())
    Correspondent.objects.create(owner=owner, name="Someone else")
    document = _process(_upload(owner, tmp_path, fixture, (FIXTURES / fixture).read_bytes()), tmp_path, "Data 01/02/2024")
    # The header wins over a date in the body.
    assert (document.document_date, document.document_date_origin) == (date(2026, 11, 10), Document.DateOrigin.SOURCE)
    assert (document.correspondent_id, document.correspondent_origin) == (sender.id, Document.FilingOrigin.SOURCE)
    event = DocumentEvent.objects.get(document=document, actor_kind=DocumentEvent.ActorKind.DETECTION)
    assert {change["field"] for change in event.changes} == {"document_date", "correspondent"}


@pytest.mark.django_db
def test_email_sender_never_creates_or_replaces_a_correspondent(owner, tmp_path):
    data = (FIXTURES / "email-notice.eml").read_bytes()
    document = _process(_upload(owner, tmp_path, "notice.eml", data), tmp_path)
    assert document.correspondent_id is None and not Correspondent.objects.exists()
    assert document.document_date == date(2026, 11, 10)

    chosen = Correspondent.objects.create(owner=owner, name="Chosen")
    Correspondent.objects.create(owner=owner, name="comune.example")
    second = _upload(owner, tmp_path, "again.eml", data + b"\n")
    Document.objects.filter(pk=second.pk).update(correspondent=chosen, correspondent_origin=Document.FilingOrigin.MANUAL)
    second = _process(second, tmp_path)
    assert second.correspondent_id == chosen.id and second.correspondent_origin == Document.FilingOrigin.MANUAL


def test_sender_matches_display_name_address_or_domain_exactly(db):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    stranger = get_user_model().objects.create_user("stranger", password="secure-password-1")
    domain = Correspondent.objects.create(owner=owner, name="Enel.it")
    name = Correspondent.objects.create(owner=owner, name="Enel Energia")
    Correspondent.objects.create(owner=stranger, name="Acme")
    assert matching_correspondent(owner.id, "Enel Energia <bollette@enel.it>") == name.id
    assert matching_correspondent(owner.id, "Servizio clienti <bollette@ENEL.IT>") == domain.id
    assert matching_correspondent(owner.id, "Enel <bollette@mail.enel.it>") is None
    assert matching_correspondent(owner.id, "Acme <a@acme.test>") is None  # another person's correspondent
    assert matching_correspondent(owner.id, "") is None


@pytest.mark.django_db
def test_mail_rule_attachments_use_text_then_email_date_and_sender(owner, tmp_path):
    account = MailAccount.objects.create(owner=owner, name="Home", host="imap.example.test", port=993, username="me@example.test", secret="x")
    acme = Correspondent.objects.create(owner=owner, name="Acme Energy")
    received = datetime(2025, 5, 4, 10, 0, tzinfo=dt_timezone.utc)

    def imported(name, text):
        document = _upload(owner, tmp_path, name, _pdf_bytes() + name.encode())
        DocumentEmail.objects.create(document=document, account=account, account_name="Home", sender="Acme Energy <billing@acme.test>",
                                     subject="Bill", received_at=received, message_id=f"<{name}>")
        return _process(document, tmp_path, text)

    with_date = imported("bill.pdf", "Fattura del 15/04/2025")
    assert (with_date.document_date, with_date.document_date_origin) == (date(2025, 4, 15), Document.DateOrigin.DETECTED)
    assert with_date.correspondent_id == acme.id and with_date.correspondent_origin == Document.FilingOrigin.SOURCE
    without = imported("scan.pdf", "no date here")
    assert (without.document_date, without.document_date_origin) == (date(2025, 5, 4), Document.DateOrigin.SOURCE)
