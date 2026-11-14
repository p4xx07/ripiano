import json
from asgiref.sync import async_to_sync
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.classification import apply_rules
from archive.mcp_server import GrantVerifier, _call, _execute
from archive.models import AgentAudit, AgentGrant, Correspondent, Document, DocumentTag, DocumentType, FilingRule, Tag


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
    _execute(grant, "change_document_tags", {"document_id": str(in_scope.id), "remove": [str(secret.id)]})
    _, correction = _execute(grant, "change_document_tags", {"document_id": str(in_scope.id), "add": [str(secret.id)]})
    assert correction["suppressed"] == [str(secret.id)]
    assert not DocumentTag.objects.filter(document=in_scope, tag=secret).exists()
    grant.scopes = ["documents:search"]
    assert _execute(grant, "search_documents", {"query": "electricity"})[1]["documents"] == []


@pytest.mark.django_db(transaction=True)
def test_agent_filing_permission_is_separate_and_preserves_human_choices():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    bills = Tag.objects.create(owner=owner, name="Bills")
    first = Document.objects.create(owner=owner, title="Acme bill", original_name="bill.pdf", original_path="a",
                                    original_mime="application/pdf", original_sha256="a" * 64, original_size=1)
    outside = Document.objects.create(owner=owner, title="Private", original_name="private.pdf", original_path="b",
                                      original_mime="application/pdf", original_sha256="b" * 64, original_size=1)
    DocumentTag.objects.create(document=first, tag=bills)
    acme = Correspondent.objects.create(owner=owner, name="Acme")
    human = Correspondent.objects.create(owner=owner, name="Chosen by me")
    invoice = DocumentType.objects.create(owner=owner, name="Invoice")
    foreign = Correspondent.objects.create(owner=other, name="Private sender")
    limited = AgentGrant.objects.create(owner=owner, name="Tag only", token_hash="a" * 64,
                                        scopes=["documents:tag"], expires_at="2099-01-01T00:00:00Z")
    filing = AgentGrant.objects.create(owner=owner, name="File bills", token_hash="b" * 64,
                                       scopes=["documents:search", "documents:filing"], filter_tag=bills,
                                       expires_at="2099-01-01T00:00:00Z")

    client = Client()
    client.force_login(owner)
    created = client.post("/api/agents", json.dumps({"name": "Another filer", "scopes": ["documents:filing"], "expires_in_days": 1}), content_type="application/json")
    assert created.status_code == 201
    assert created.json()["scopes"] == ["documents:filing"]

    with patch("archive.mcp_server._grant", return_value=limited):
        denied = async_to_sync(_call)("set_document_filing", {"document_id": str(first.id), "correspondent_id": str(acme.id)})
    assert denied.is_error and AgentAudit.objects.get(grant=limited).outcome == "denied"
    with patch("archive.mcp_server._grant", return_value=filing):
        options = async_to_sync(_call)("list_filing_options", {})
        assert {item["name"] for item in options.structured_content["correspondents"]} == {"Acme", "Chosen by me"}
        assert [item["name"] for item in options.structured_content["document_types"]] == ["Invoice"]
        assert async_to_sync(_call)("set_document_filing", {"document_id": str(outside.id), "correspondent_id": str(acme.id)}).is_error
        assert async_to_sync(_call)("set_document_filing", {"document_id": str(first.id), "correspondent_id": str(foreign.id)}).is_error
        assert async_to_sync(_call)("set_document_filing", {"document_id": str(first.id), "correspondent_id": str(acme.id), "document_type_id": str(invoice.id)}).is_error
        changed = async_to_sync(_call)("set_document_filing", {"document_id": str(first.id), "correspondent_id": str(acme.id)})
        typed = async_to_sync(_call)("set_document_filing", {"document_id": str(first.id), "document_type_id": str(invoice.id)})
    assert not changed.is_error and changed.structured_content["origin"] == Document.FilingOrigin.MODEL
    assert not typed.is_error
    first.refresh_from_db()
    assert first.correspondent == acme and first.document_type == invoice
    assert first.correspondent_origin == first.document_type_origin == Document.FilingOrigin.MODEL
    search = _execute(filing, "search_documents", {})[1]["documents"][0]
    assert search["correspondent"]["name"] == "Acme" and search["document_type"]["name"] == "Invoice"

    FilingRule.objects.create(owner=owner, kind=FilingRule.Kind.CORRESPONDENT, correspondent=human,
                              pattern="Acme", field=FilingRule.Field.TITLE)
    apply_rules(first)
    first.refresh_from_db()
    assert first.correspondent == acme and first.correspondent_origin == Document.FilingOrigin.MODEL
    assert client.patch(f"/api/documents/{first.id}", json.dumps({"correspondent_id": str(human.id)}), content_type="application/json").status_code == 200
    with patch("archive.mcp_server._grant", return_value=filing):
        protected = async_to_sync(_call)("set_document_filing", {"document_id": str(first.id), "correspondent_id": str(acme.id)})
    assert protected.is_error and AgentAudit.objects.filter(grant=filing, action="set_document_filing", outcome="error").exists()
    first.refresh_from_db()
    assert first.correspondent == human and first.correspondent_origin == Document.FilingOrigin.MANUAL
    first.document_type_origin = Document.FilingOrigin.SOURCE
    first.save(update_fields=["document_type_origin"])
    with patch("archive.mcp_server._grant", return_value=filing):
        protected_type = async_to_sync(_call)("set_document_filing", {"document_id": str(first.id), "document_type_id": str(invoice.id)})
    assert protected_type.is_error
    first.refresh_from_db()
    assert first.document_type == invoice and first.document_type_origin == Document.FilingOrigin.SOURCE
    assert _execute(filing, "list_filing_options", {"offset": True})[1]["error"] == "Invalid offset"
    Correspondent.objects.bulk_create(Correspondent(owner=owner, name=f"Other {index:03d}") for index in range(201))
    first_page = _execute(filing, "list_filing_options", {})[1]
    second_page = _execute(filing, "list_filing_options", {"offset": 200})[1]
    assert len(first_page["correspondents"]) == 200 and first_page["next_offset"] == 200
    assert len(second_page["correspondents"]) == 3 and second_page["next_offset"] is None
