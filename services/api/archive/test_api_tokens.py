from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.models import ApiToken, Document, Tag


@pytest.mark.django_db
def test_api_tokens_act_as_their_owner_without_csrf_and_can_be_revoked():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")  # the archive owner may manage agents
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    Tag.objects.create(owner=other, name="Not yours")
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(owner)
    assert browser.post("/api/account/tokens", {"name": "Script", "password": "secure-password-1"}, content_type="application/json").status_code == 403  # CSRF
    session = Client()
    session.force_login(owner)
    assert session.post("/api/account/tokens", {"name": "Script", "password": "wrong"}, content_type="application/json").status_code == 400
    created = session.post("/api/account/tokens", {"name": "Script", "password": "secure-password-1", "expires_in_days": 30}, content_type="application/json").json()
    token = created["token"]
    assert token.startswith("rip_") and token not in ApiToken.objects.get().token_hash
    assert session.get("/api/account/tokens").json()["tokens"][0]["prefix"] == token[:10]

    api = Client(enforce_csrf_checks=True, HTTP_AUTHORIZATION=f"Token {token}")
    assert api.post("/api/tags", {"name": "From script"}, content_type="application/json").status_code == 201
    assert [item["name"] for item in api.get("/api/tags").json()["tags"]] == ["From script"]
    assert api.get("/api/session").status_code == 403  # tokens cannot touch sign-in or security
    assert api.get("/api/account/tokens").status_code == 403
    assert api.post("/api/agents", {"name": "x"}, content_type="application/json").status_code == 403
    assert api.post("/api/share-bundles", {"document_ids": []}, content_type="application/json").status_code == 403
    assert Client(HTTP_AUTHORIZATION="Token rip_stale").get("/api/share-links/" + "a" * 43).status_code == 404  # public path, header ignored
    assert ApiToken.objects.get().last_used_at is not None
    assert Client(HTTP_AUTHORIZATION="Token rip_wrong").get("/api/tags").status_code == 401

    ApiToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert api.get("/api/tags").status_code == 401
    ApiToken.objects.update(expires_at=timezone.now() + timedelta(days=1))
    owner.set_password("a-new-secure-password")
    owner.save()
    assert api.get("/api/tags").status_code == 401  # a new password ends every token
    ApiToken.objects.update(revoked_at=None)
    session.force_login(owner)  # the password change also ended the browser session
    assert session.delete(f"/api/account/tokens/{created['id']}").status_code == 200
    assert api.get("/api/tags").status_code == 401
    intruder = Client()
    intruder.force_login(other)
    assert intruder.delete(f"/api/account/tokens/{created['id']}").status_code == 404


@pytest.mark.django_db
def test_schema_lists_api_routes_with_methods_and_parameters():
    assert Client().get("/api/schema.json").status_code == 401
    client = Client()
    client.force_login(get_user_model().objects.create_user("reader", password="secure-password-1"))
    schema = client.get("/api/schema.json").json()
    assert schema["openapi"] == "3.1.0"
    detail = schema["paths"]["/api/documents/{document_id}"]
    assert set(detail) >= {"get", "patch"}
    assert detail["get"]["parameters"][0] == {"name": "document_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}
    assert set(schema["paths"]["/api/workflows"]) == {"get", "post"}
    assert "/api/share-bundles/{token}" in schema["paths"] and not any(path.startswith("/admin") for path in schema["paths"])
