import json
from asgiref.sync import async_to_sync

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.mcp_server import GrantVerifier, _execute
from archive.models import AgentGrant, Document, DocumentTag, Tag


@pytest.mark.django_db(transaction=True)
def test_named_grants_are_hashed_scoped_and_revocable():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    user = get_user_model().objects.create_user("other", password="secure-password-2")
    client = Client()
    client.force_login(user)
    assert client.get("/api/agents").status_code == 403
    client.force_login(owner)
    tag = Tag.objects.create(owner=owner, name="Bills")
    response = client.post("/api/agents", json.dumps({
        "name": "Local Mac", "scopes": ["documents:search", "documents:tag"],
        "filter_tag_id": str(tag.id), "expires_in_days": 30,
    }), content_type="application/json")
    assert response.status_code == 201
    body = response.json()
    token = body["token"]
    grant = AgentGrant.objects.get(pk=body["id"])
    assert token.startswith("rpa_") and token not in grant.token_hash
    assert "token" not in client.get("/api/agents").content.decode()
    verified = async_to_sync(GrantVerifier().verify_token)(token)
    assert verified and verified.client_id == str(grant.id)
    assert verified.scopes == ["documents:search", "documents:tag"]
    assert async_to_sync(GrantVerifier().verify_token)("rpa_wrong") is None
    assert client.delete(f"/api/agents/{grant.id}").status_code == 200
    assert async_to_sync(GrantVerifier().verify_token)(token) is None


@pytest.mark.django_db
def test_agent_document_filter_and_tag_changes_are_isolated():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    bills = Tag.objects.create(owner=owner, name="Bills")
    secret = Tag.objects.create(owner=owner, name="Secret")
    foreign = Tag.objects.create(owner=other, name="Foreign")
    in_scope = Document.objects.create(owner=owner, title="Invoice", original_name="invoice.pdf", original_path="x", original_mime="application/pdf", original_sha256="a" * 64, original_size=1, extracted_text="electricity")
    out_scope = Document.objects.create(owner=owner, title="Letter", original_name="letter.pdf", original_path="y", original_mime="application/pdf", original_sha256="b" * 64, original_size=1, extracted_text="secret")
    DocumentTag.objects.create(document=in_scope, tag=bills)
    grant = AgentGrant.objects.create(owner=owner, name="Bills only", token_hash="a" * 64, scopes=["documents:search", "documents:text", "documents:tag"], filter_tag=bills, expires_at="2099-01-01T00:00:00Z")

    _, search = _execute(grant, "search_documents", {})
    assert [document["id"] for document in search["documents"]] == [str(in_scope.id)]
    assert _execute(grant, "get_document_text", {"document_id": str(out_scope.id)})[1]["error"]
    assert _execute(grant, "change_document_tags", {"document_id": str(out_scope.id), "add": [str(secret.id)]})[1]["error"]
    assert _execute(grant, "change_document_tags", {"document_id": str(in_scope.id), "add": [str(foreign.id)]})[1]["error"]
    _, changed = _execute(grant, "change_document_tags", {"document_id": str(in_scope.id), "add": [str(secret.id)]})
    assert changed["added"] == [str(secret.id)]
    assert DocumentTag.objects.filter(document=in_scope, tag=secret, origin=DocumentTag.Origin.MODEL).exists()
    assert DocumentTag.objects.filter(document=in_scope, tag=bills).exists()
    grant.scopes = ["documents:search"]
    assert _execute(grant, "search_documents", {"query": "electricity"})[1]["documents"] == []
