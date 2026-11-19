"""Round-5 judge findings: persistent suggestion rejection, agent clean-up, email snippets,
paper-copy history, MCP tag names, account deactivation, and private API caching."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.mcp_server import GrantVerifier, _call, _execute
from archive.models import (AgentAudit, AgentGrant, ApiToken, Correspondent, Document, DocumentEvent, DocumentTag, DocumentType,
                            Location, Movement, PhysicalCopy, SuggestionDismissal, Tag, TagOverride)

PASSWORD = "secure-password-1"


def _document(owner, title, text, **extra):
    return Document.objects.create(
        owner=owner, title=title, original_name=extra.pop("original_name", "bill.pdf"), original_path=title,
        original_mime=extra.pop("original_mime", "application/pdf"), original_sha256=(title * 64)[:64], original_size=10,
        status=Document.Status.READY, extracted_text=text, **extra,
    )


def _post(client, url, body):
    return client.post(url, json.dumps(body), content_type="application/json")


@pytest.mark.django_db
def test_a_rejected_suggestion_stays_rejected_for_that_document_and_is_recorded():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    stranger = get_user_model().objects.create_user("stranger", password=PASSWORD)
    source = _document(owner, "Acme electricity May", "Electricity invoice from Acme Energy for May")
    target = _document(owner, "Acme electricity June", "Acme Energy electricity invoice for June")
    tag = Tag.objects.create(owner=owner, name="Utilities")
    sender = Correspondent.objects.create(owner=owner, name="Acme Energy")
    kind = DocumentType.objects.create(owner=owner, name="Invoice")
    DocumentTag.objects.create(document=source, tag=tag, origin=DocumentTag.Origin.MANUAL)
    Document.objects.filter(pk=source.pk).update(correspondent=sender, correspondent_origin=Document.FilingOrigin.MANUAL,
                                                 document_type=kind, document_type_origin=Document.FilingOrigin.MANUAL)
    client = Client()
    client.force_login(owner)
    suggestions = client.get(f"/api/documents/{target.id}/filing-suggestions").json()
    assert [item["name"] for item in suggestions["tags"]] == ["Utilities"]
    assert [item["name"] for item in suggestions["correspondents"]] == ["Acme Energy"]

    endpoint = f"/api/documents/{target.id}/filing-suggestions/dismiss"
    # Owner only, and only the owner's own labels.
    outsider = Client()
    outsider.force_login(stranger)
    assert _post(outsider, endpoint, {"kind": "tag", "id": str(tag.id)}).status_code == 404
    assert Client().post(endpoint, "{}", content_type="application/json").status_code == 401
    assert _post(client, endpoint, {"kind": "colour", "id": str(tag.id)}).status_code == 400
    assert _post(client, endpoint, {"kind": "tag", "id": "nope"}).status_code == 400
    assert _post(client, endpoint, {"kind": "tag", "id": str(Tag.objects.create(owner=stranger, name="X").id)}).status_code == 404

    rejected = _post(client, endpoint, {"kind": "tag", "id": str(tag.id)})
    assert rejected.status_code == 200 and rejected.json()["changed"] is True
    assert TagOverride.objects.filter(document=target, tag=tag).exists()  # like removing the tag by hand
    assert _post(client, endpoint, {"kind": "sender", "id": str(sender.id)}).json()["dismissed"]["kind"] == "correspondent"
    assert _post(client, endpoint, {"kind": "document_type", "id": str(kind.id)}).status_code == 200
    again = _post(client, endpoint, {"kind": "correspondent", "id": str(sender.id)})
    assert again.status_code == 200 and again.json()["changed"] is False
    assert SuggestionDismissal.objects.filter(document=target).count() == 2

    # A new session (another browser) does not see them again.
    fresh = Client()
    fresh.force_login(owner)
    after = fresh.get(f"/api/documents/{target.id}/filing-suggestions").json()
    assert after == {"tags": [], "correspondents": [], "document_types": []}
    target.refresh_from_db()
    assert target.correspondent_id is None and not DocumentTag.objects.filter(document=target).exists()

    events = DocumentEvent.objects.filter(document=target).order_by("created_at")
    recorded = [change for event in events for change in event.changes if change["field"] == "dismissed_suggestion"]
    assert [(change["kind"], change["name"]) for change in recorded] == [("tag", "Utilities"), ("correspondent", "Acme Energy"), ("document_type", "Invoice")]

    # Rejection is per document: another similar document still gets the sender suggestion.
    other = _document(owner, "Acme electricity July", "Acme Energy electricity invoice for July")
    assert [item["name"] for item in client.get(f"/api/documents/{other.id}/filing-suggestions").json()["correspondents"]] == ["Acme Energy"]

    # A tag already on the document is removed, not rejected.
    DocumentTag.objects.create(document=other, tag=tag, origin=DocumentTag.Origin.MANUAL)
    assert _post(client, f"/api/documents/{other.id}/filing-suggestions/dismiss", {"kind": "tag", "id": str(tag.id)}).status_code == 409

    # Adding the tag by hand later clears the rejection, as for any manual removal.
    patched = client.patch(f"/api/documents/{target.id}", json.dumps({"tags": [str(tag.id)]}), content_type="application/json")
    assert patched.status_code == 200
    assert not TagOverride.objects.filter(document=target, tag=tag).exists()


@pytest.mark.django_db
def test_learned_suggestions_and_auto_filing_skip_a_rejected_sender():
    from archive.classification import _add_learned

    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    target = _document(owner, "Acme bill", "Acme Energy electricity")
    sender = Correspondent.objects.create(owner=owner, name="Acme Energy")
    SuggestionDismissal.objects.create(document=target, correspondent=sender)
    result = {"tags": [], "correspondents": [], "document_types": []}
    with patch("archive.learning._load", return_value={"rank": {}, "kinds": {}}), \
            patch("archive.learning.predict", return_value={"correspondents": [(str(sender.id), 0.95)]}):
        _add_learned(target, result, set(), {"tags": 3, "correspondents": 2, "document_types": 2}, {"correspondents": {str(sender.id)}, "document_types": set()})
    assert result["correspondents"] == []


@pytest.mark.django_db
def test_revoked_or_expired_agents_can_be_removed_with_their_activity():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    other = get_user_model().objects.create_user("other", password=PASSWORD)
    client = Client()
    client.force_login(owner)
    active = AgentGrant.objects.create(owner=owner, name="Active", token_hash="a" * 64, scopes=["documents:search"],
                                       expires_at=timezone.now() + timedelta(days=3))
    expired = AgentGrant.objects.create(owner=owner, name="Old", token_hash="b" * 64, scopes=["documents:search"],
                                        expires_at=timezone.now() - timedelta(days=1))
    revoked = AgentGrant.objects.create(owner=owner, name="Gone", token_hash="c" * 64, scopes=["documents:search"],
                                        expires_at=timezone.now() + timedelta(days=3), revoked_at=timezone.now())
    AgentAudit.objects.create(grant=revoked, action="search_documents", outcome="ok")
    refused = client.delete(f"/api/agents/{active.id}?forget=1")
    assert refused.status_code == 409 and AgentGrant.objects.filter(pk=active.pk).exists()
    outsider = Client()
    outsider.force_login(other)
    assert outsider.delete(f"/api/agents/{revoked.id}?forget=1").status_code == 404
    assert client.delete(f"/api/agents/{revoked.id}?forget=1").json() == {"deleted": True}
    assert client.delete(f"/api/agents/{expired.id}?forget=1").status_code == 200
    assert not AgentAudit.objects.filter(grant_id=revoked.id).exists()  # its activity log goes with it
    assert [grant["name"] for grant in client.get("/api/agents").json()["grants"]] == ["Active"]
    # Plain DELETE still only revokes.
    assert client.delete(f"/api/agents/{active.id}").json() == {"revoked": True}
    assert AgentGrant.objects.filter(pk=active.pk, revoked_at__isnull=False).exists()


@pytest.mark.django_db
def test_email_snippets_start_from_the_message_body():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    text = ("From Comune di Prova <tributi@example.org>\nTo me@example.org\nDate Tue, 04 Nov 2026 10:00:00 +0100\n"
            "Subject Avviso TARI 2026 lampone urgente\nAttachments: avviso.pdf\nGentile contribuente, l'avviso TARI 2026 lampone è disponibile.")
    _document(owner, "Avviso TARI", text, original_name="notice.eml", original_mime="message/rfc822")
    client = Client()
    client.force_login(owner)
    found = client.get("/api/documents", {"q": "lampone"}).json()["documents"]
    assert "disponibile" in found[0]["snippet"] and "lampone" in found[0]["snippet"]
    assert "+0100" not in found[0]["snippet"] and "Subject" not in found[0]["snippet"]
    # A word only in the subject is shown from the subject, without the header rows before it.
    subject_only = client.get("/api/documents", {"q": "urgente"}).json()["documents"][0]["snippet"]
    assert subject_only.startswith("Avviso TARI 2026 lampone urgente") and "+0100" not in subject_only


@pytest.mark.django_db
def test_paper_copy_history_names_who_moved_it():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    document = _document(owner, "Lease", "lease")
    shelf = Location.objects.create(owner=owner, name="Shelf")
    copy = PhysicalCopy.objects.create(document=document, location=shelf)
    Movement.objects.create(physical_copy=copy, kind=Movement.Kind.PLACEMENT, to_location=shelf, moved_by=owner)
    client = Client()
    client.force_login(owner)
    move = client.get(f"/api/copies/{copy.id}/history").json()["movements"][0]
    assert move["by"] == "owner" and "T" in move["at"]


@pytest.mark.django_db
def test_mcp_tags_accept_exact_names_but_not_ambiguous_or_guarded_ones():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    other = get_user_model().objects.create_user("other", password=PASSWORD)
    bills = Tag.objects.create(owner=owner, name="Bills")
    Tag.objects.create(owner=owner, name="Utenze")
    Tag.objects.create(owner=owner, name="utenze")
    guarded = Tag.objects.create(owner=owner, name="Cloud only")
    Tag.objects.create(owner=other, name="Foreign")
    document = _document(owner, "Bill", "bill")
    tagger = AgentGrant.objects.create(owner=owner, name="Tagger", token_hash="d" * 64, scopes=["documents:search", "documents:tag"],
                                       expires_at=timezone.now() + timedelta(days=3))
    AgentGrant.objects.create(owner=owner, name="Cloud", token_hash="e" * 64, scopes=["documents:search"], filter_tag=guarded,
                              expires_at=timezone.now() + timedelta(days=3))
    _, added = _execute(tagger, "change_document_tags", {"document_id": str(document.id), "add": ["bills"]})
    assert added["added"] == [str(bills.id)] and DocumentTag.objects.filter(document=document, tag=bills).exists()
    _, ambiguous = _execute(tagger, "change_document_tags", {"document_id": str(document.id), "add": ["UTENZE"]})
    assert "Several tags" in ambiguous["error"]
    _, foreign = _execute(tagger, "change_document_tags", {"document_id": str(document.id), "add": ["Foreign"]})
    assert foreign["error"] == "Tag not found"
    _, by_name_guard = _execute(tagger, "change_document_tags", {"document_id": str(document.id), "add": ["cloud ONLY"]})
    assert "another agent" in by_name_guard["error"]
    _, conflict = _execute(tagger, "change_document_tags", {"document_id": str(document.id), "add": ["Bills"], "remove": [str(bills.id)]})
    assert "conflicting" in conflict["error"]
    _, removed = _execute(tagger, "change_document_tags", {"document_id": str(document.id), "remove": ["Bills"]})
    assert removed["removed"] == [str(bills.id)]


@pytest.mark.django_db
def test_a_denied_agent_call_names_the_probed_document():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    document = _document(owner, "Payslip", "salary")
    grant = AgentGrant.objects.create(owner=owner, name="Finder", token_hash="f" * 64, scopes=["documents:search"],
                                      expires_at=timezone.now() + timedelta(days=3))
    with patch("archive.mcp_server._grant", return_value=grant):
        assert async_to_sync(_call)("get_document_text", {"document_id": str(document.id)}).is_error
        assert async_to_sync(_call)("get_document_text", {"document_id": "not-an-id"}).is_error
    entries = list(AgentAudit.objects.filter(grant=grant).order_by("created_at"))
    assert [(entry.outcome, entry.document_id) for entry in entries] == [("denied", document.id), ("denied", None)]


@pytest.mark.django_db
def test_turning_an_account_off_ends_its_tokens_agents_and_sessions_for_good():
    admin = get_user_model().objects.create_superuser("admin", password=PASSWORD)
    anna = get_user_model().objects.create_user("anna", password="anna-long-password-7")
    anna_browser = Client()
    anna_browser.force_login(anna)
    token = _post(anna_browser, "/api/account/tokens", {"name": "Script", "password": "anna-long-password-7", "expires_in_days": 30}).json()["token"]
    agent_token = _post(anna_browser, "/api/agents", {"password": "anna-long-password-7", "name": "Local", "scopes": ["documents:search"], "expires_in_days": 30}).json()["token"]
    api = Client(HTTP_AUTHORIZATION=f"Token {token}")
    assert api.get("/api/tags").status_code == 200
    assert async_to_sync(GrantVerifier().verify_token)(agent_token)

    admin_client = Client()
    admin_client.force_login(admin)
    assert admin_client.patch(f"/api/people/{anna.pk}", json.dumps({"is_active": False, "current_password": PASSWORD}), content_type="application/json").status_code == 200
    assert admin_client.patch(f"/api/people/{anna.pk}", json.dumps({"is_active": True, "current_password": PASSWORD}), content_type="application/json").status_code == 200

    assert api.get("/api/tags").status_code == 401  # REST token stays revoked
    assert async_to_sync(GrantVerifier().verify_token)(agent_token) is None  # MCP agent stays revoked
    assert ApiToken.objects.filter(user=anna, revoked_at__isnull=True).count() == 0
    assert AgentGrant.objects.filter(owner=anna, revoked_at__isnull=True).count() == 0
    assert anna_browser.get("/api/tags").status_code == 401  # the old browser session ended too


@pytest.mark.django_db
def test_signed_in_api_answers_are_not_cached():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    client = Client()
    client.force_login(owner)
    assert client.get("/api/tags")["Cache-Control"] == "private, no-store"
    # Round 6 (judge 3, L7): signed-out API answers such as /api/session are not cached either.
    assert Client().get("/api/health")["Cache-Control"] == "private, no-store"
