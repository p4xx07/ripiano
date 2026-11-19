"""Round-6 judge findings: "updated" workflows after bulk and agent changes, damaged PDFs, agent activity refusals,
JSON CSRF failures, signed-out cache headers, download extensions, scan-ID reuse, and file-name search."""

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone
from pypdf import PdfReader, PdfWriter

from archive.mcp_server import _call, _execute
from archive.messages_it import EXACT
from archive.models import (AgentAudit, AgentGrant, Correspondent, Document, DocumentTag, Tag, Workflow, WorkflowRun)
from archive.tasks import PROCESSING_ERRORS, process_document

PASSWORD = "secure-password-1"


def _document(owner, title, text="Invoice from Acme", **extra):
    return Document.objects.create(
        owner=owner, title=title, original_name=extra.pop("original_name", f"{title}.pdf"), original_path=extra.pop("original_path", title),
        original_mime=extra.pop("original_mime", "application/pdf"), original_sha256=extra.pop("original_sha256", (title * 64)[:64]),
        original_size=10, status=Document.Status.READY, extracted_text=text, processed_at=timezone.now(), **extra,
    )


def _post(client, url, body):
    return client.post(url, json.dumps(body), content_type="application/json")


def _signed_in(user):
    client = Client()
    client.force_login(user)
    return client


def _blank_pdf(pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(200, 200)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


# --- H1: "updated" workflows run after bulk and MCP-agent changes ---------------------------------------------------


@pytest.mark.django_db
def test_updated_workflows_run_after_bulk_tag_filing_and_date_changes():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    urgent = Tag.objects.create(owner=owner, name="Urgent")
    acme = Correspondent.objects.create(owner=owner, name="Acme")
    tagged = Workflow.objects.create(owner=owner, name="Urgent follow-up", trigger=Workflow.Trigger.UPDATED, filter_tag=urgent, set_needs_action=True)
    filed = Workflow.objects.create(owner=owner, name="Acme follow-up", trigger=Workflow.Trigger.UPDATED, filter_correspondent=acme, set_needs_action=True)
    dated = Workflow.objects.create(owner=owner, name="Any change", trigger=Workflow.Trigger.UPDATED, filter_text="dated")
    first, second, third = _document(owner, "First"), _document(owner, "Second"), _document(owner, "Third dated")
    client = _signed_in(owner)

    assert _post(client, "/api/documents/bulk-tags", {"document_ids": [str(first.id)], "tag_id": str(urgent.id), "action": "add"}).status_code == 200
    first.refresh_from_db()
    assert first.action_status == Document.ActionStatus.OPEN
    assert WorkflowRun.objects.filter(workflow=tagged, document=first, trigger="updated").count() == 1

    assert _post(client, "/api/documents/bulk-filing", {"document_ids": [str(second.id)], "field": "correspondent", "value_id": str(acme.id)}).status_code == 200
    second.refresh_from_db()
    assert second.action_status == Document.ActionStatus.OPEN
    assert WorkflowRun.objects.filter(workflow=filed, document=second).count() == 1

    assert _post(client, "/api/documents/bulk-date", {"document_ids": [str(third.id)], "document_date": "2026-11-10"}).status_code == 200
    assert WorkflowRun.objects.filter(workflow=dated, document=third).count() == 1
    # Each change runs the workflows once; the workflows' own changes start nothing further.
    assert WorkflowRun.objects.count() == 3


@pytest.mark.django_db
def test_agent_changes_run_updated_workflows_but_never_touch_another_agents_filter_tag():
    """An agent's tag or filing change runs the owner's "updated" workflows, as the owner's own change does.

    Choice: the workflow runs with the owner's rules, but when an agent started it, it leaves the filter tags of the
    owner's *other* active agents alone (the same tags the MCP tool refuses). Otherwise an agent could add a workflow's
    trigger tag and let the workflow widen another agent's view, which the tool guard forbids. The skip is written in
    the run detail so the owner can see it. The same workflow run by the owner's own change still adds the tag.
    """
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    bills = Tag.objects.create(owner=owner, name="Bills")
    trigger = Tag.objects.create(owner=owner, name="Paid")
    other_scope = Tag.objects.create(owner=owner, name="Accountant")
    plain = Tag.objects.create(owner=owner, name="Archived")
    acme = Correspondent.objects.create(owner=owner, name="Acme")
    agent = AgentGrant.objects.create(owner=owner, name="Bills agent", token_hash="a" * 64, scopes=["documents:tag", "documents:filing"],
                                      filter_tag=bills, expires_at="2099-01-01T00:00:00Z")
    AgentGrant.objects.create(owner=owner, name="Accountant agent", token_hash="b" * 64, scopes=["documents:search"],
                              filter_tag=other_scope, expires_at="2099-01-01T00:00:00Z")
    flow = Workflow.objects.create(owner=owner, name="Paid bills", trigger=Workflow.Trigger.UPDATED, filter_tag=trigger, set_needs_action=True)
    flow.add_tags.add(other_scope, plain)
    filing = Workflow.objects.create(owner=owner, name="Acme", trigger=Workflow.Trigger.UPDATED, filter_correspondent=acme)
    filing.remove_tags.add(other_scope)
    doc = _document(owner, "Electricity")
    DocumentTag.objects.create(document=doc, tag=bills)

    _, result = _execute(agent, "change_document_tags", {"document_id": str(doc.id), "add": ["Paid"]})
    assert "error" not in result
    doc.refresh_from_db()
    tags = set(DocumentTag.objects.filter(document=doc).values_list("tag_id", flat=True))
    assert doc.action_status == Document.ActionStatus.OPEN and plain.id in tags
    assert other_scope.id not in tags  # the accountant agent's view did not widen
    run = WorkflowRun.objects.get(workflow=flow, document=doc)
    assert "skipped tag Accountant" in run.detail and "added tag Archived" in run.detail

    # A filing change runs workflows too, and cannot remove another agent's filter tag either.
    DocumentTag.objects.create(document=doc, tag=other_scope, origin=DocumentTag.Origin.RULE)
    _, result = _execute(agent, "set_document_filing", {"document_id": str(doc.id), "correspondent_id": str(acme.id)})
    assert "error" not in result
    assert WorkflowRun.objects.filter(workflow=filing, document=doc).count() == 1
    assert DocumentTag.objects.filter(document=doc, tag=other_scope).exists()

    # The owner's own change runs the same workflow without the agent guard.
    DocumentTag.objects.filter(document=doc, tag=other_scope).delete()
    Workflow.objects.filter(pk=filing.pk).update(enabled=False)  # it would remove the tag again
    DocumentTag.objects.filter(document=doc, tag=trigger).delete()  # so the bulk add below is a real change
    assert _post(_signed_in(owner), "/api/documents/bulk-tags", {"document_ids": [str(doc.id)], "tag_id": str(trigger.id), "action": "add"}).status_code == 200
    assert DocumentTag.objects.filter(document=doc, tag=other_scope).exists()


# --- M1: a damaged PDF is not marked Ready ----------------------------------------------------------------------------


def _upload_and_process(tmp_path, data, ocr_pages):
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    client = _signed_in(owner)

    def fake_ocr(args, **kwargs):
        # OCR "repairs" what it can and writes only the pages it recovered.
        Path(args[-1]).write_bytes(_blank_pdf(ocr_pages))

    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False), patch("archive.ingestion.process_document.delay"):
        response = client.post("/api/documents", {"document": SimpleUploadedFile("letter.pdf", data, content_type="application/pdf")})
        assert response.status_code == 202
        with patch("archive.tasks.subprocess.run", side_effect=fake_ocr):
            process_document(response.json()["id"])
    return client, Document.objects.get(pk=response.json()["id"])


@pytest.mark.django_db
def test_a_truncated_pdf_is_flagged_for_attention_with_a_clear_message(tmp_path):
    # Round 8 (judge 1, M2): the readable pages are kept and the document is processed with a warning, not failed.
    whole = _blank_pdf(3)
    truncated = whole[:len(whole) // 2]
    with pytest.raises(Exception):
        len(PdfReader(BytesIO(truncated)).pages)
    with override_settings(MEDIA_ROOT=tmp_path):
        client, document = _upload_and_process(tmp_path, truncated, ocr_pages=1)
        assert document.status == Document.Status.READY and document.processing_warning == "damaged_pdf"
        assert document.archive_path and document.original_path  # nothing discarded
        inbox = client.get("/api/documents", {"view": "exceptions"}).json()["documents"]
        assert [item["id"] for item in inbox] == [str(document.id)]
        assert inbox[0]["warning"] == PROCESSING_ERRORS["damaged_pdf"]
        italian = client.get(f"/api/documents/{document.id}", HTTP_ACCEPT_LANGUAGE="it").json()
        assert italian["warning"] == EXACT[PROCESSING_ERRORS["damaged_pdf"]]


@pytest.mark.django_db
def test_an_intact_pdf_still_becomes_ready(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        _, document = _upload_and_process(tmp_path, _blank_pdf(3), ocr_pages=3)
    assert document.status == Document.Status.READY and document.error == ""


# --- Low items ------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_guarded_tag_refusals_are_logged_as_denied_and_activity_names_the_document():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    bills, other = Tag.objects.create(owner=owner, name="Bills"), Tag.objects.create(owner=owner, name="Other")
    grant = AgentGrant.objects.create(owner=owner, name="Agent", token_hash="c" * 64, scopes=["documents:tag"], filter_tag=bills,
                                      expires_at="2099-01-01T00:00:00Z")
    AgentGrant.objects.create(owner=owner, name="Second", token_hash="d" * 64, scopes=["documents:search"], filter_tag=other,
                              expires_at="2099-01-01T00:00:00Z")
    doc = _document(owner, "Gas bill")
    DocumentTag.objects.create(document=doc, tag=bills)
    with patch("archive.mcp_server._grant", return_value=grant):
        assert async_to_sync(_call)("change_document_tags", {"document_id": str(doc.id), "add": [str(other.id)]}).is_error
        assert async_to_sync(_call)("change_document_tags", {"document_id": str(doc.id), "add": [str(uuid4())]}).is_error
    assert list(AgentAudit.objects.order_by("id").values_list("outcome", flat=True)) == ["denied", "error"]
    events = _signed_in(owner).get("/api/agents/events").json()["events"]
    assert {event["document_title"] for event in events} == {"Gas bill"}


@pytest.mark.django_db
def test_a_failed_csrf_check_answers_in_json_and_in_italian():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    client = Client(enforce_csrf_checks=True)
    client.force_login(owner)
    response = _post(client, "/api/tags", {"name": "x"})
    assert response.status_code == 403 and response["Content-Type"].startswith("application/json")
    assert response.json()["error"] == "This request could not be verified. Reload the page and try again."
    italian = client.post("/api/tags", "{}", content_type="application/json", HTTP_ACCEPT_LANGUAGE="it")
    assert italian.json()["error"] == EXACT["This request could not be verified. Reload the page and try again."]


@pytest.mark.django_db
def test_signed_out_api_answers_are_not_cached():
    assert Client().get("/api/session")["Cache-Control"] == "private, no-store"


@pytest.mark.django_db
def test_a_pdf_uploaded_with_an_image_name_downloads_as_pdf(tmp_path):
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    client = _signed_in(owner)
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        created = client.post("/api/documents", {"document": SimpleUploadedFile("scan.png", _blank_pdf(1), content_type="image/png")}).json()
        download = client.get(f"/api/documents/{created['id']}/original")
        assert download["Content-Type"] == "application/pdf"
        assert 'filename="scan.pdf"' in download["Content-Disposition"]
        assert b"".join(download.streaming_content).startswith(b"%PDF-")
        jpeg = _document(owner, "Photo", original_name="photo.jpeg", original_path="originals/aa/x.jpg", original_mime="image/jpeg")
        (tmp_path / "originals" / "aa").mkdir(parents=True, exist_ok=True)
        (tmp_path / "originals" / "aa" / "x.jpg").write_bytes(b"x")
        same = client.get(f"/api/documents/{jpeg.id}/original")
        assert 'filename="photo.jpeg"' in same["Content-Disposition"]  # .jpeg and .jpg are the same type
        assert b"".join(same.streaming_content) == b"x"


@pytest.mark.django_db
def test_reusing_a_scan_id_with_a_different_file_is_refused(tmp_path):
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    client = _signed_in(owner)
    scan_id = str(uuid4())
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        first = client.post("/api/documents", {"document": SimpleUploadedFile("a.pdf", _blank_pdf(1))}, HTTP_X_RIPIANO_SCAN_ID=scan_id)
        retry = client.post("/api/documents", {"document": SimpleUploadedFile("a.pdf", _blank_pdf(1))}, HTTP_X_RIPIANO_SCAN_ID=scan_id)
        other = client.post("/api/documents", {"document": SimpleUploadedFile("b.pdf", _blank_pdf(2))}, HTTP_X_RIPIANO_SCAN_ID=scan_id,
                            HTTP_ACCEPT_LANGUAGE="it")
    assert first.status_code == 202
    assert retry.status_code == 200 and retry.json()["id"] == first.json()["id"]
    assert other.status_code == 409
    assert other.json()["error"] == EXACT["This scan ID was already used for a different file. Send the file again as a new scan."]
    assert Document.objects.filter(owner=owner).count() == 1


@pytest.mark.django_db
def test_original_file_names_are_searchable():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    doc = _document(owner, "Renamed title", text="nothing here", original_name="r6j1-email-notice.eml")
    found = _signed_in(owner).get("/api/documents", {"q": "r6j1-email-notice"}).json()["documents"]
    assert [item["id"] for item in found] == [str(doc.id)]


@pytest.mark.django_db
def test_changes_that_change_nothing_run_no_workflows():
    """Review L1/L2: a bulk or agent call that leaves the document as it was runs no workflow."""
    owner = get_user_model().objects.create_user("noop-owner", password="secure-password-1")
    tag = Tag.objects.create(owner=owner, name="Already")
    doc = _document(owner, "noop")
    DocumentTag.objects.create(document=doc, tag=tag, origin=DocumentTag.Origin.MANUAL)
    workflow = Workflow.objects.create(owner=owner, name="Any update", trigger=Workflow.Trigger.UPDATED, set_needs_action=True)
    assert _post(_signed_in(owner), "/api/documents/bulk-tags", {"document_ids": [str(doc.id)], "tag_id": str(tag.id), "action": "add"}).status_code == 200
    assert not WorkflowRun.objects.filter(workflow=workflow, document=doc).exists()
