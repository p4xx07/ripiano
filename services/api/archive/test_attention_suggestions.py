from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.attention_suggestions import suggest_attention
from archive.models import Document

TODAY = date(2026, 11, 24)


@pytest.mark.parametrize("title,text,expected", [
    ("PagoPA TARI", "Emesso il 10/11/2026\nScadenza: 15/12/2026\nImporto EUR 82", {"kind": "payment", "date": "2026-12-15"}),
    ("Avviso MAV", "Da pagare entro 3 gennaio 2027", {"kind": "payment", "date": "2027-01-03"}),
    ("Ricevuta PagoPA", "Pagamento effettuato il 20/11/2026. Scadenza 15/12/2026", None),
    ("Bollettino", "Scadenza 15/12/2026 e scadenza rata 15/01/2027", None),
    ("Bollettino", "Emesso il 10/11/2026; importo EUR 82", None),
    ("PagoPA", "Scadenza 15/12/2025", None),
    ("PagoPA", "Scadenza 15/12/27", None),
    ("PagoPA", "Scadenza:\nData emissione: 15/12/2026", None),
    ("PagoPA", "Scadenza: 15/12/2025\nData emissione: 15/12/2026", None),
    ("Biglietto concerto", "Data evento: 14 marzo 2027\nIngresso ore 20:00", {"kind": "event", "date": "2027-03-14"}),
    ("Concert ticket", "Event date: March 14, 2027", {"kind": "event", "date": "2027-03-14"}),
    ("Biglietto concerto", "Acquistato il 12/11/2026, senza data evento", None),
])
def test_conservative_future_date_suggestions(title, text, expected):
    assert suggest_attention(title, text, today=TODAY) == expected


@pytest.mark.django_db
def test_attention_suggestion_requires_document_access_and_ready_ocr():
    owner = get_user_model().objects.create_user("owner", password="test-password-1")
    other = get_user_model().objects.create_user("other", password="test-password-2")
    document = Document.objects.create(
        owner=owner, title="PagoPA TARI", original_name="tari.pdf", original_path="originals/tari.pdf",
        original_mime="application/pdf", original_sha256="a" * 64, original_size=1,
        status=Document.Status.READY, extracted_text="Scadenza: 15/12/2026",
    )
    client = Client()
    url = f"/api/documents/{document.id}/attention-suggestion"
    assert client.get(url).status_code == 401
    client.force_login(other)
    assert client.get(url).status_code == 404
    client.force_login(owner)
    with patch("archive.attention_suggestions.timezone.localdate", return_value=TODAY):
        response = client.get(url)
    assert response.status_code == 200 and response.json()["suggestion"] == {"kind": "payment", "date": "2026-12-15"}
    Document.objects.filter(pk=document.pk).update(status=Document.Status.PENDING)
    assert client.get(url).json()["suggestion"] is None
