from datetime import date, timedelta
from unittest.mock import patch

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.core import mail as outbox
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone

from archive.models import Correspondent, Document, DocumentNote, DocumentTag, DocumentType, Tag, Workflow, WorkflowRun
from archive.workflows import run_for_document, run_scheduled, send_notifications


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1")


def document(owner, title="Acme invoice May", text="Invoice from Acme Energy", **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path="originals/aa/x.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10,
                                   status=Document.Status.READY, extracted_text=text, processed_at=timezone.now(), **values)


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_added_workflow_files_matching_documents_once_and_respects_manual_choices(owner, django_capture_on_commit_callbacks):
    bills = Tag.objects.create(owner=owner, name="Bills")
    inbox = Tag.objects.create(owner=owner, name="To sort")
    acme = Correspondent.objects.create(owner=owner, name="Acme")
    invoice = DocumentType.objects.create(owner=owner, name="Invoice")
    flow = Workflow.objects.create(owner=owner, name="Acme bills", trigger=Workflow.Trigger.ADDED, filter_text="acme energy",
                                   filter_sources=["web"], set_correspondent=acme, set_document_type=invoice, set_needs_action=True,
                                   action_note="Pay it", add_note="Filed by workflow")
    flow.add_tags.add(bills)
    flow.remove_tags.add(inbox)
    target = document(owner)
    DocumentTag.objects.create(document=target, tag=inbox, origin=DocumentTag.Origin.RULE)
    other = document(owner, title="Holiday", text="Beach photos")

    assert len(run_for_document(target, "added")) == 1
    assert run_for_document(other, "added") == []
    target.refresh_from_db()
    assert (target.correspondent, target.document_type, target.action_status, target.action_note) == (acme, invoice, "open", "Pay it")
    assert target.correspondent_origin == Document.FilingOrigin.SOURCE
    assert set(DocumentTag.objects.filter(document=target).values_list("tag__name", flat=True)) == {"Bills"}
    assert DocumentNote.objects.get(document=target).body == "Filed by workflow"
    run = WorkflowRun.objects.get(document=target)
    assert "added tag Bills" in run.detail and "set sender Acme" in run.detail
    assert run_for_document(target, "added") == []  # once per document

    manual = Correspondent.objects.create(owner=owner, name="Chosen by me")
    second = document(owner, title="Acme invoice June", correspondent=manual, correspondent_origin=Document.FilingOrigin.MANUAL)
    run_for_document(second, "added")
    second.refresh_from_db()
    assert second.correspondent == manual  # a manual choice is never overwritten


@pytest.mark.django_db
def test_processing_runs_added_workflows_only_the_first_time(owner, tmp_path):
    from archive.ingestion import ingest_document
    from archive.tasks import process_document

    tag = Tag.objects.create(owner=owner, name="New")
    flow = Workflow.objects.create(owner=owner, name="Tag new", trigger=Workflow.Trigger.ADDED)
    flow.add_tags.add(tag)
    from io import BytesIO

    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    data = BytesIO()
    writer.write(data)

    def fake_ocr(args, **kwargs):
        from pathlib import Path
        Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())

    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False), patch("archive.ingestion.process_document.delay"), patch("archive.tasks.subprocess.run", side_effect=fake_ocr):
        created = ingest_document(owner, SimpleUploadedFile("a.pdf", data.getvalue()))
        process_document(str(created.id))
        assert DocumentTag.objects.filter(document=created, tag=tag).exists()
        DocumentTag.objects.filter(document=created).delete()
        Document.objects.filter(pk=created.pk).update(status=Document.Status.PENDING)
        process_document(str(created.id))  # reprocessing is not "added"
    assert not DocumentTag.objects.filter(document=created).exists()
    assert WorkflowRun.objects.filter(document=created).count() == 1


@pytest.mark.django_db
def test_updated_workflows_run_after_an_edit_and_scheduled_ones_once_after_the_date(owner, django_capture_on_commit_callbacks):
    urgent = Tag.objects.create(owner=owner, name="Urgent")
    flow = Workflow.objects.create(owner=owner, name="Flag urgent", trigger=Workflow.Trigger.UPDATED, filter_tag=urgent, set_needs_action=True)
    target = document(owner)
    client = client_for(owner)
    client.patch(f"/api/documents/{target.id}", {"title": "Renamed"}, content_type="application/json")
    assert not WorkflowRun.objects.exists()
    response = client.patch(f"/api/documents/{target.id}", {"tags": [str(urgent.id)]}, content_type="application/json")
    assert response.json()["action_status"] == "open"
    assert WorkflowRun.objects.filter(workflow=flow).count() == 1

    reminder = Workflow.objects.create(owner=owner, name="Review old", trigger=Workflow.Trigger.SCHEDULED,
                                       schedule_field=Workflow.DateField.DOCUMENT_DATE, schedule_days=30, add_note="Check this again")
    Workflow.objects.filter(pk=reminder.pk).update(created_at=timezone.now() - timedelta(days=20))
    document(owner, title="Ancient", document_date=date.today() - timedelta(days=400))  # due long before the workflow existed
    document(owner, title="Old", document_date=date.today() - timedelta(days=40))
    document(owner, title="Recent", document_date=date.today() - timedelta(days=5))
    document(owner, title="Undated")
    assert run_scheduled() == 1
    assert run_scheduled() == 0
    assert list(WorkflowRun.objects.filter(workflow=reminder).values_list("document__title", flat=True)) == ["Old"]


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test", PUBLIC_ORIGIN="https://ripiano.test")
def test_webhooks_and_emails_carry_metadata_only_and_record_failures(owner, django_capture_on_commit_callbacks):
    flow = Workflow.objects.create(owner=owner, name="Notify", trigger=Workflow.Trigger.ADDED, webhook_url="https://hooks.example.test/in",
                                   email_to="me@example.test, partner@example.test")
    target = document(owner, text="SECRET OCR CONTENT")
    sent = []
    real_client = httpx.Client

    def recording_client(**kwargs):
        def handle(request):
            assert request.url.host == "93.184.216.34" and request.headers["host"] == "hooks.example.test"
            assert request.extensions["sni_hostname"] == "hooks.example.test"
            sent.append(__import__("json").loads(request.content))
            return httpx.Response(200, stream=httpx.ByteStream(b"x" * 200_000))
        return real_client(transport=httpx.MockTransport(handle), **kwargs)

    with django_capture_on_commit_callbacks() as callbacks:
        run = run_for_document(target, "added")[0]
    assert len(callbacks) == 1
    with patch("archive.workflows.check_webhook_host", return_value=__import__("ipaddress").ip_address("93.184.216.34")), patch("httpx.Client", side_effect=recording_client):
        send_notifications(run)
    run.refresh_from_db()
    assert run.status == "applied" and "webhook delivered" in run.detail and "email sent to 2 recipients" in run.detail
    assert sent[0]["document"]["url"] == f"https://ripiano.test/?document={target.id}" and sent[0]["event"] == "document.added"
    assert "SECRET" not in str(sent) and "SECRET" not in outbox.outbox[0].body

    with patch("archive.workflows.check_webhook_host"), patch("httpx.Client", side_effect=UnicodeEncodeError("idna", "x", 0, 1, "label too long")), override_settings(EMAIL_HOST=""):
        send_notifications(run)
    run.refresh_from_db()
    assert run.status == "failed" and "webhook could not be delivered" in run.detail and "no mail server" in run.detail


@pytest.mark.django_db
def test_workflow_api_validates_and_is_owner_scoped(owner):
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    theirs = Tag.objects.create(owner=other, name="Theirs")
    mine = Tag.objects.create(owner=owner, name="Mine")
    client = client_for(owner)
    base = {"name": "Tag it", "trigger": "added", "add_tag_ids": [str(mine.id)]}
    assert client.post("/api/workflows", {**base, "add_tag_ids": [str(theirs.id)]}, content_type="application/json").json()["error"] == "Tag not found"
    assert client.post("/api/workflows", {**base, "webhook_url": "ftp://x"}, content_type="application/json").status_code == 400
    assert client.post("/api/workflows", {**base, "email_to": "not-an-address"}, content_type="application/json").status_code == 400
    assert client.post("/api/workflows", {**base, "filter_sources": ["fax"]}, content_type="application/json").status_code == 400
    created = client.post("/api/workflows", base, content_type="application/json")
    assert created.status_code == 201 and created.json()["add_tag_ids"] == [str(mine.id)]
    flow_id = created.json()["id"]
    target = document(owner)
    applied = client.post(f"/api/workflows/{flow_id}/run", {"document_id": str(target.id)}, content_type="application/json").json()
    assert applied["matched"] and "added tag Mine" in applied["run"]["detail"]
    listing = client.get("/api/workflows").json()
    assert [item["name"] for item in listing["workflows"]] == ["Tag it"] and listing["runs"][0]["document"]["id"] == str(target.id)

    intruder = client_for(other)
    assert intruder.get("/api/workflows").json() == {"workflows": [], "runs": []}
    assert intruder.patch(f"/api/workflows/{flow_id}", {"name": "Mine now"}, content_type="application/json").status_code == 404
    assert intruder.post(f"/api/workflows/{flow_id}/run", {"document_id": str(target.id)}, content_type="application/json").status_code == 404
    assert client.delete(f"/api/workflows/{flow_id}").status_code == 200


def test_webhooks_to_private_addresses_are_refused_unless_allowed():
    from archive.workflows import WebhookError, check_webhook_host

    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.5", 0))]):
        with pytest.raises(WebhookError, match="private network"):
            check_webhook_host("https://homeassistant.local/hook")
        with override_settings(RIPIANO_WEBHOOK_ALLOW_PRIVATE=True):
            check_webhook_host("https://homeassistant.local/hook")
    for address in ("127.0.0.1", "169.254.169.254", "::1", "::ffff:10.0.0.1", "64:ff9b::7f00:1"):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", (address, 0))]), pytest.raises(WebhookError):
            check_webhook_host("http://api:8000/")
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        check_webhook_host("https://example.com/hook")


@pytest.mark.django_db
def test_completed_follow_ups_stay_done_and_updated_side_effects_happen_once(owner):
    urgent = Tag.objects.create(owner=owner, name="Urgent")
    Workflow.objects.create(owner=owner, name="Flag urgent", trigger=Workflow.Trigger.UPDATED, filter_tag=urgent,
                            set_needs_action=True, add_note="Look at this")
    target = document(owner)
    client = client_for(owner)
    assert client.patch(f"/api/documents/{target.id}", {"tags": [str(urgent.id)]}, content_type="application/json").json()["action_status"] == "open"
    assert client.patch(f"/api/documents/{target.id}", {"action_status": "done"}, content_type="application/json").json()["action_status"] == "done"
    assert client.patch(f"/api/documents/{target.id}", {"title": "Renamed again"}, content_type="application/json").json()["action_status"] == "done"
    assert DocumentNote.objects.filter(document=target).count() == 1
    assert client.post("/api/workflows", {"name": "x", "trigger": "added", "filter_sources": [{}]}, content_type="application/json").status_code == 400
    assert client.post("/api/workflows", {"name": "x", "trigger": "added", "webhook_url": "https://" + "a" * 70 + ".example"}, content_type="application/json").status_code == 400
