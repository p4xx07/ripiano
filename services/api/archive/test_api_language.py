import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.api_language import to_italian
from archive.message_catalog import extract
from archive.messages_it import EXACT, TEMPLATES


def test_reviewed_api_messages_have_valid_source_keys_and_templates():
    exact, templates = extract()
    required = {"Invalid credentials", "Sign in required", "Document not found", "Choose a file", "File exceeds the upload limit", "The source document changed. Search again before adding it."}
    assert required <= exact
    assert required <= set(EXACT)
    assert set(EXACT) <= exact
    assert set(TEMPLATES) <= templates
    # Every user-facing message has an Italian version: a new English message fails here until it is translated.
    assert not exact - set(EXACT), sorted(exact - set(EXACT))[:10]
    assert not templates - set(TEMPLATES), sorted(templates - set(TEMPLATES))[:10]
    assert all(english != italian and italian.strip() for english, italian in EXACT.items())
    for english, italian in TEMPLATES.items():
        assert sorted(re.findall(r"\{\d+\}", english)) == sorted(re.findall(r"\{\d+\}", italian)), english


def test_templates_fill_in_values():
    english = next(key for key in TEMPLATES if key.startswith("ASN {0} is already used by “{1}”"))
    italian = to_italian("ASN 7 is already used by “Bolletta luce”")
    assert italian != "ASN 7 is already used by “Bolletta luce”"
    assert "7" in italian and "Bolletta luce" in italian
    assert english  # sanity
    assert to_italian("Some text nobody wrote") == "Some text nobody wrote"


@pytest.mark.django_db
def test_api_errors_follow_accept_language():
    get_user_model().objects.create_user("person", password="secure-password-1")
    client = Client()
    english = client.post("/api/session", {"username": "person", "password": "wrong"}, content_type="application/json")
    assert english.json()["error"] == "Invalid credentials" and english["Vary"].count("Accept-Language")
    italian = client.post("/api/session", {"username": "person", "password": "wrong"}, content_type="application/json", HTTP_ACCEPT_LANGUAGE="it")
    assert italian.status_code == 401
    assert italian.json()["error"] == EXACT["Invalid credentials"] and italian["Content-Language"] == "it"
    english_preferred = client.post("/api/session", {"username": "person", "password": "wrong"}, content_type="application/json", HTTP_ACCEPT_LANGUAGE="it;q=0, en;q=1")
    assert english_preferred.json()["error"] == "Invalid credentials"
    # Django's own password rules come from its Italian catalog.
    client.force_login(get_user_model().objects.get(username="person"))
    weak = client.post("/api/account/password", {"current_password": "secure-password-1", "new_password": "123456789012"}, content_type="application/json", HTTP_ACCEPT_LANGUAGE="it-IT,it;q=0.9")
    assert weak.status_code == 400 and "password" in weak.json()["error"].lower() and "too common" not in weak.json()["error"]


def test_field_names_in_messages_are_readable_and_translated():
    from archive.field_labels import label

    assert label("filter_filename") == "File name filter"
    if "{0} must be text up to {1} characters" in TEMPLATES:
        italian = to_italian("File name filter must be text up to 200 characters")
        assert "Filtro nome file" in italian and "200" in italian
    if "Enter the {0}" in TEMPLATES:
        assert "nome" in to_italian("Enter the name")
    assert to_italian(f"{label('document_type')} not found") == "Tipo di documento: elemento non trovato"
    assert to_italian(f"{label('recursive')} must be true or false") == "Ricorsivo: il valore deve essere vero o falso"
    # User data in other positions is never translated.
    assert "“Note”" in to_italian("ASN 7 is already used by “Note”")


@pytest.mark.django_db
def test_library_filter_errors_are_sentences():
    user = get_user_model().objects.create_user("person", password="secure-password-1")
    client = Client()
    client.force_login(user)
    english = client.get("/api/documents", {"tag_id": "nope"}).json()["error"]
    assert english == "Invalid tag filter"
    italian = client.get("/api/documents", {"date_from": "nope"}, HTTP_ACCEPT_LANGUAGE="it").json()["error"]
    assert italian == EXACT["Invalid start date"]


@pytest.mark.django_db
def test_stored_processing_errors_are_localized_without_changing_document_data():
    from archive.models import Document
    from archive.tasks import PROCESSING_ERRORS

    owner = get_user_model().objects.create_user("italian-errors", password="secure-password-1")
    original = PROCESSING_ERRORS["generic"]
    document = Document.objects.create(
        owner=owner, title="Document not found", original_name="scan.pdf", original_path="originals/scan.pdf",
        original_mime="application/pdf", original_sha256="0" * 64, original_size=1,
        status=Document.Status.FAILED, error=original,
    )
    client = Client()
    client.force_login(owner)
    english = client.get("/api/documents").json()["documents"][0]
    assert english["error"] == original and english["title"] == "Document not found"
    italian = client.get("/api/documents", HTTP_ACCEPT_LANGUAGE="it").json()["documents"][0]
    assert italian["error"] == EXACT[original]
    assert italian["title"] == "Document not found"
    detail = client.get(f"/api/documents/{document.id}", HTTP_ACCEPT_LANGUAGE="it").json()
    assert detail["error"] == EXACT[original]
    jobs = client.get("/api/jobs", HTTP_ACCEPT_LANGUAGE="it").json()
    assert jobs["documents_failed"]["items"][0]["error"] == EXACT[original]
