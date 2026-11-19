import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone

from archive.mcp_server import _execute
from archive.models import (AgentGrant, Correspondent, CustomField, Document, DocumentAccess, DocumentEvent, DocumentTag,
                            DocumentType, Tag, Workflow)
from archive.workflows import run_for_document


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1")


def make_document(owner, title="Lease", **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path="originals/aa/x.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10,
                                   status=Document.Status.READY, extracted_text="Secret OCR words", processed_at=timezone.now(), **values)


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def history(client, document):
    response = client.get(f"/api/documents/{document.pk}/history")
    assert response.status_code == 200, response.content
    return response.json()["events"]


def changes_by_field(event):
    return {item["field"]: (item["from"], item["to"]) for item in event["changes"]}


@pytest.mark.django_db
def test_patch_records_readable_diff_and_noop_writes_nothing(owner):
    house, bills = Tag.objects.create(owner=owner, name="House"), Tag.objects.create(owner=owner, name="Bills")
    landlord = Correspondent.objects.create(owner=owner, name="Landlord")
    lease = DocumentType.objects.create(owner=owner, name="Lease")
    document = make_document(owner)
    DocumentTag.objects.create(document=document, tag=bills)
    client = client_for(owner)
    body = {"title": "Lease 2026", "document_date": "2026-03-01", "correspondent_id": str(landlord.pk),
            "document_type_id": str(lease.pk), "tags": [str(house.pk)], "asn": 42}
    assert client.patch(f"/api/documents/{document.pk}", body, content_type="application/json").status_code == 200

    [event] = history(client, document)
    assert event["action"] == "updated"
    assert event["actor"] == {"kind": "user", "name": "", "user": "owner"}
    assert changes_by_field(event) == {
        "title": ("Lease", "Lease 2026"), "document_date": (None, "2026-03-01"), "correspondent": (None, "Landlord"),
        "document_type": (None, "Lease"), "asn": (None, "42"), "tags": (["Bills"], ["House"]),
    }
    assert "Secret OCR" not in json.dumps(event)

    # Saving the same values again, or only follow-up details, records nothing.
    assert client.patch(f"/api/documents/{document.pk}", body, content_type="application/json").status_code == 200
    assert client.patch(f"/api/documents/{document.pk}", {"action_note": "Call"}, content_type="application/json").status_code == 200
    assert DocumentEvent.objects.filter(document=document).count() == 1


@pytest.mark.django_db
def test_bulk_actions_and_trash_restore_are_recorded(owner):
    tag = Tag.objects.create(owner=owner, name="Car")
    sender = Correspondent.objects.create(owner=owner, name="Garage")
    first, second = make_document(owner, "One"), make_document(owner, "Two")
    client = client_for(owner)
    ids = [str(first.pk), str(second.pk)]

    def post(url, body):
        response = client.post(url, json.dumps(body), content_type="application/json")
        assert response.status_code == 200, response.content

    post("/api/documents/bulk-tags", {"document_ids": ids, "tag_id": str(tag.pk), "action": "add"})
    post("/api/documents/bulk-filing", {"document_ids": ids, "field": "correspondent", "value_id": str(sender.pk)})
    post("/api/documents/bulk-date", {"document_ids": ids, "document_date": "2026-01-31"})
    # Already-set values change nothing and add no event.
    post("/api/documents/bulk-date", {"document_ids": ids, "document_date": "2026-01-31"})
    events = history(client, first)
    assert [changes_by_field(event) for event in events] == [
        {"document_date": (None, "2026-01-31")}, {"correspondent": (None, "Garage")}, {"tags": ([], ["Car"])},
    ]
    assert DocumentEvent.objects.filter(document=second).count() == 3

    post("/api/documents/bulk-trash", {"document_ids": ids, "action": "trash"})
    post("/api/documents/bulk-trash", {"document_ids": ids, "action": "restore"})
    assert client.post(f"/api/documents/{first.pk}/trash").status_code == 200
    assert client.post(f"/api/documents/{first.pk}/restore").status_code == 200
    assert [event["action"] for event in history(client, first)][:4] == ["restored", "trashed", "restored", "trashed"]
    assert history(client, second)[0]["action"] == "restored"


@pytest.mark.django_db
def test_upload_records_created_event_with_channel(owner, tmp_path):
    client = client_for(owner)
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        response = client.post("/api/documents", {"document": SimpleUploadedFile("scan.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")})
    assert response.status_code == 202
    [event] = history(client, Document.objects.get(pk=response.json()["id"]))
    assert event["action"] == "created" and event["actor"]["user"] == "owner"
    assert event["changes"] == [{"field": "source", "from": None, "to": "web"}]


@pytest.mark.django_db
def test_custom_field_changes_are_recorded(owner):
    field = CustomField.objects.create(owner=owner, name="Amount", kind=CustomField.Kind.NUMBER)
    document = make_document(owner)
    client = client_for(owner)
    url = f"/api/documents/{document.pk}/custom-fields/{field.pk}"
    assert client.put(url, json.dumps({"value": "12.50"}), content_type="application/json").status_code == 200
    assert client.delete(url).status_code == 200
    events = history(client, document)
    assert [item["changes"] for item in events] == [
        [{"field": "custom_field", "name": "Amount", "from": "12.5", "to": None}],
        [{"field": "custom_field", "name": "Amount", "from": None, "to": "12.5"}],
    ]


@pytest.mark.django_db
def test_agent_writes_are_attributed_to_the_grant(owner):
    tag = Tag.objects.create(owner=owner, name="Insurance")
    kind = DocumentType.objects.create(owner=owner, name="Policy")
    document = make_document(owner)
    grant = AgentGrant.objects.create(owner=owner, name="Mac classifier", token_hash="h" * 64,
                                      scopes=["documents:tag", "documents:file"], expires_at=timezone.now() + timedelta(days=1))
    assert "error" not in _execute(grant, "change_document_tags", {"document_id": str(document.pk), "add": [str(tag.pk)]})[1]
    assert "error" not in _execute(grant, "set_document_filing", {"document_id": str(document.pk), "document_type_id": str(kind.pk)})[1]
    events = history(client_for(owner), document)
    assert [event["actor"] for event in events] == [{"kind": "agent", "name": "Mac classifier", "user": None}] * 2
    assert changes_by_field(events[0]) == {"document_type": (None, "Policy")}
    assert changes_by_field(events[1]) == {"tags": ([], ["Insurance"])}


@pytest.mark.django_db
def test_workflow_changes_are_attributed_to_the_workflow(owner):
    bills = Tag.objects.create(owner=owner, name="Bills")
    acme = Correspondent.objects.create(owner=owner, name="Acme")
    flow = Workflow.objects.create(owner=owner, name="Acme bills", trigger=Workflow.Trigger.ADDED, set_correspondent=acme)
    flow.add_tags.add(bills)
    document = make_document(owner)
    assert len(run_for_document(document, "added")) == 1
    [event] = history(client_for(owner), document)
    assert event["actor"] == {"kind": "workflow", "name": "Acme bills", "user": None}
    assert changes_by_field(event) == {"correspondent": (None, "Acme"), "tags": ([], ["Bills"])}


@pytest.mark.django_db
def test_shared_recipients_read_history_and_others_cannot(owner):
    editor = get_user_model().objects.create_user("editor", password="secure-password-2")
    stranger = get_user_model().objects.create_user("stranger", password="secure-password-3")
    document = make_document(owner)
    DocumentAccess.objects.create(document=document, user=editor, level=DocumentAccess.Level.EDIT)
    owner_client = client_for(owner)
    assert owner_client.patch(f"/api/documents/{document.pk}", {"asn": 7}, content_type="application/json").status_code == 200
    editor_client = client_for(editor)
    assert editor_client.patch(f"/api/documents/{document.pk}", {"title": "Shared lease", "document_date": "2026-02-02"},
                               content_type="application/json").status_code == 200

    owner_events = history(owner_client, document)
    assert owner_events[0]["actor"]["user"] == "editor"
    assert changes_by_field(owner_events[0]) == {"title": ("Lease", "Shared lease"), "document_date": (None, "2026-02-02")}
    # The recipient sees the history, but not owner-only archive details such as the ASN.
    editor_events = history(editor_client, document)
    assert len(editor_events) == 1 and editor_events[0]["actor"]["user"] == "editor"
    assert client_for(stranger).get(f"/api/documents/{document.pk}/history").status_code == 404
    assert Client().get(f"/api/documents/{document.pk}/history").status_code in (401, 403)


@pytest.mark.django_db
def test_history_pages_and_rejects_bad_offsets(owner):
    document = make_document(owner)
    DocumentEvent.objects.bulk_create([DocumentEvent(document=document, changes=[{"field": "title", "from": str(i), "to": str(i + 1)}])
                                       for i in range(55)])
    client = client_for(owner)
    first = client.get(f"/api/documents/{document.pk}/history").json()
    assert len(first["events"]) == 50 and first["next_offset"] == 50
    second = client.get(f"/api/documents/{document.pk}/history", {"offset": 50}).json()
    assert len(second["events"]) == 5 and second["next_offset"] is None
    assert client.get(f"/api/documents/{document.pk}/history", {"offset": "x"}).status_code == 400


@pytest.mark.django_db
def test_automatic_filing_names_the_rule_or_source(owner):
    from archive import mail
    from archive.classification import apply_rules
    from archive.models import ClassificationRule, MailAccount, MailRule, StorageSource
    from archive.storage_sources import _file

    utilities, scans = Tag.objects.create(owner=owner, name="Utilities"), Tag.objects.create(owner=owner, name="Scans")
    energy = Correspondent.objects.create(owner=owner, name="Acme Energy")
    account = MailAccount.objects.create(owner=owner, name="Home", host="imap.example.test", port=993, username="me@example.test",
                                         secret=mail.encrypt_secret("app-password"))
    rule = MailRule.objects.create(owner=owner, account=account, name="Bills", correspondent=energy)
    emailed = make_document(owner, "Bill")
    mail._apply_filing(emailed, rule, [utilities], {"account": account, "account_name": "Home", "sender": "", "subject": "",
                                                    "received_at": None, "message_id": ""})
    [event] = history(client_for(owner), emailed)
    assert (event["action"], event["actor"]) == ("filed_automatically", {"kind": "email_rule", "name": "Bills", "user": None})
    assert changes_by_field(event) == {"correspondent": (None, "Acme Energy"), "tags": ([], ["Utilities"])}

    source = StorageSource.objects.create(owner=owner, name="Scanner share", kind=StorageSource.Kind.FOLDER)
    source.tags.add(scans)
    scanned = make_document(owner, "Scan")
    _file(scanned, source)
    assert history(client_for(owner), scanned)[0]["actor"] == {"kind": "source", "name": "Scanner share", "user": None}

    ClassificationRule.objects.create(owner=owner, tag=scans, pattern="secret ocr", field=ClassificationRule.Field.TEXT)
    ruled = make_document(owner, "Ruled")
    apply_rules(ruled)
    [event] = history(client_for(owner), ruled)
    assert event["actor"]["kind"] == "matching_rules" and changes_by_field(event) == {"tags": ([], ["Scans"])}
    apply_rules(ruled)  # nothing new to change
    assert DocumentEvent.objects.filter(document=ruled).count() == 1
