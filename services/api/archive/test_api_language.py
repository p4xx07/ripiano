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
