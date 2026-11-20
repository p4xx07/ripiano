"""Round-8 judge findings and owner decision D11: a password change or reset ends share links and bundles, a partly
salvaged damaged PDF is processed with a warning, workflow runs that held every action back say "skipped", agents'
out-of-scope reads are logged as refusals, unknown API paths answer in JSON, and a sticker made without a location
gets a first history entry."""

import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, override_settings

from archive.mcp_server import _call
from archive.messages_it import DISPLAY, EXACT
from archive.models import (AgentAudit, AgentGrant, Document, DocumentTag, Movement, PhysicalCopy, ShareBundle, ShareLink, Tag, Workflow,
                            WorkflowRun)
from archive.tasks import PROCESSING_ERRORS
from archive.test_bundles import create_bundle, png, upload
from archive.test_round6_fixes import _blank_pdf, _document, _execute, _upload_and_process
from archive.test_share_links import make_document

User = get_user_model()
PASSWORD = "secure-password-1"
NEW_PASSWORD = "another-secure-password-2"


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def send(client, method, url, body):
    return getattr(client, method)(url, json.dumps(body), content_type="application/json")


# --- D11: a password change or an admin reset ends share links and bundles ------------------------------------------


def _share_everything(owner, media, django_capture_on_commit_callbacks):
    document, _, _ = make_document(owner, media, "lease.pdf")
    client = client_for(owner)
    link = client.post(f"/api/documents/{document.id}/shares", {"expires_in_days": 7}, content_type="application/json").json()
    scan = upload(owner, media, "scan.png", png("red"))
    bundle = create_bundle(client, [scan.id], django_capture_on_commit_callbacks).json()
    return document, link["url"].replace("https://archive.example", ""), bundle["url"].replace("https://archive.example", "")


def _assert_ended(owner, document, link_url, bundle_url):
    anonymous = Client()
    unknown = anonymous.get("/api/share-links/" + "x" * 43)
    for url in (link_url, bundle_url):
        ended = anonymous.get(url)
        assert ended.status_code == 404 and ended.json() == unknown.json() == {"error": "Link not found"}
    assert set(ShareLink.objects.filter(owner=owner).values_list("revoked_reason", flat=True)) == {"password_changed"}
    assert set(ShareBundle.objects.filter(owner=owner).values_list("revoked_reason", flat=True)) == {"password_changed"}
    # The owner's lists say why they ended (the web shows it).
    client = client_for(User.objects.get(pk=owner.pk))  # signed in again with the new password
    share = client.get(f"/api/documents/{document.id}/shares").json()["shares"][0]
    assert share["active"] is False and share["revoked_reason"] == "password_changed"
    bundle = client.get("/api/share-bundles").json()["bundles"][0]
    assert bundle["active"] is False and bundle["revoked_reason"] == "password_changed"


@pytest.mark.django_db
def test_changing_your_password_ends_your_share_links_and_bundles(tmp_path, django_capture_on_commit_callbacks):
    cache.clear()
    anna = User.objects.create_user("anna", password=PASSWORD)
    bruno = User.objects.create_user("bruno", password=PASSWORD)
    media = tmp_path / "media"
    with override_settings(MEDIA_ROOT=media, PUBLIC_ORIGIN="https://archive.example"):
        document, link_url, bundle_url = _share_everything(anna, media, django_capture_on_commit_callbacks)
        _, bruno_link, bruno_bundle = _share_everything(bruno, media, django_capture_on_commit_callbacks)
        assert Client().get(link_url).status_code == 200 and Client().get(bundle_url).status_code == 200
        changed = send(client_for(anna), "post", "/api/account/password", {"current_password": PASSWORD, "new_password": NEW_PASSWORD})
        assert changed.status_code == 200
        _assert_ended(anna, document, link_url, bundle_url)
        # Someone else's links are untouched, and a new link works again.
        assert Client().get(bruno_link).status_code == 200 and Client().get(bruno_bundle).status_code == 200
        fresh = client_for(User.objects.get(pk=anna.pk)).post(f"/api/documents/{document.id}/shares", {"expires_in_days": 7}, content_type="application/json").json()
        assert fresh["revoked_reason"] is None
        assert Client().get(fresh["url"].replace("https://archive.example", "")).status_code == 200


@pytest.mark.django_db
def test_an_admin_password_reset_ends_that_persons_share_links_and_bundles(tmp_path, django_capture_on_commit_callbacks):
    cache.clear()
    admin = User.objects.create_superuser("admin", password=PASSWORD)
    anna = User.objects.create_user("anna", password=PASSWORD)
    media = tmp_path / "media"
    with override_settings(MEDIA_ROOT=media, PUBLIC_ORIGIN="https://archive.example"):
        document, link_url, bundle_url = _share_everything(anna, media, django_capture_on_commit_callbacks)
        reset = send(client_for(admin), "patch", f"/api/people/{anna.pk}", {"password": NEW_PASSWORD, "current_password": PASSWORD})
        assert reset.status_code == 200
        _assert_ended(anna, document, link_url, bundle_url)


@pytest.mark.django_db
def test_resaving_the_same_password_hash_keeps_share_links(tmp_path):
    anna = User.objects.create_user("anna", password=PASSWORD)
    document, _, _ = make_document(anna, tmp_path / "media", "lease.pdf")
    with override_settings(MEDIA_ROOT=tmp_path / "media", PUBLIC_ORIGIN="https://archive.example"):
        client_for(anna).post(f"/api/documents/{document.id}/shares", {"expires_in_days": 7}, content_type="application/json")
    anna.save()  # e.g. last_login; no new password
    assert ShareLink.objects.get().revoked_at is None


# --- Judge 1 M2: a partly salvaged damaged PDF is processed with a warning --------------------------------------------


@pytest.mark.django_db
def test_a_partly_salvaged_pdf_is_ready_with_a_warning_and_its_readable_pages(tmp_path):
    whole = _blank_pdf(3)
    truncated = whole[:len(whole) // 2]
    with override_settings(MEDIA_ROOT=tmp_path):
        client, document = _upload_and_process(tmp_path, truncated, ocr_pages=1)
        assert document.status == Document.Status.READY and document.error == "" and document.processing_failures == 0
        assert document.processing_warning == "damaged_pdf"
        payload = client.get(f"/api/documents/{document.id}").json()
        assert payload["processing_warning"] == "damaged_pdf" and payload["warning"] == PROCESSING_ERRORS["damaged_pdf"]
        assert payload["processing_warning_reviewed_at"] is None and payload["archive_available"] is True
        italian = client.get(f"/api/documents/{document.id}", HTTP_ACCEPT_LANGUAGE="it").json()
        assert italian["warning"] == EXACT[PROCESSING_ERRORS["damaged_pdf"]]
        # Not a failure to retry, but still listed under Needs attention until the owner has checked it.
        assert client.get("/api/jobs").json()["documents_failed"]["total"] == 0
        assert [item["id"] for item in client.get("/api/documents", {"view": "exceptions"}).json()["documents"]] == [str(document.id)]
        assert client.get("/api/overview").json()["documents"]["warnings"] == 1
        # The searchable PDF and the readable pages are available (the damaged original cannot be opened).
        assert client.get(f"/api/documents/{document.id}/archive").status_code == 200
        pages = client.get(f"/api/documents/{document.id}/pages")
        assert pages.status_code == 200 and pages.json()["count"] == 1 and pages.json()["source"] == "searchable"
        # Reviewing it takes it off the list.
        reviewed = send(client, "patch", f"/api/documents/{document.id}", {"processing_warning_reviewed": True})
        assert reviewed.status_code == 200 and reviewed.json()["processing_warning_reviewed_at"]
        assert client.get("/api/documents", {"view": "exceptions"}).json()["documents"] == []
        assert client.get("/api/overview").json()["documents"]["warnings"] == 0


@pytest.mark.django_db
def test_only_documents_with_a_warning_can_be_reviewed(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        client, document = _upload_and_process(tmp_path, _blank_pdf(2), ocr_pages=2)
        assert document.status == Document.Status.READY and document.processing_warning == ""
        refused = send(client, "patch", f"/api/documents/{document.id}", {"processing_warning_reviewed": True})
        assert refused.status_code == 400 and refused.json() == {"error": "Only documents with a processing warning can be reviewed"}
        assert "Only documents with a processing warning can be reviewed" in EXACT


# --- Judge 3 L2: a run that held every action back is "skipped" --------------------------------------------------------


@pytest.mark.django_db
def test_a_workflow_run_whose_every_action_was_held_back_is_skipped():
    owner = User.objects.create_user("owner", password=PASSWORD)
    bills, trigger = Tag.objects.create(owner=owner, name="Bills"), Tag.objects.create(owner=owner, name="Paid")
    other_scope, plain = Tag.objects.create(owner=owner, name="Accountant"), Tag.objects.create(owner=owner, name="Archived")
    agent = AgentGrant.objects.create(owner=owner, name="Bills agent", token_hash="a" * 64, scopes=["documents:tag"], filter_tag=bills,
                                      expires_at="2099-01-01T00:00:00Z")
    AgentGrant.objects.create(owner=owner, name="Accountant agent", token_hash="b" * 64, scopes=["documents:search"],
                              filter_tag=other_scope, expires_at="2099-01-01T00:00:00Z")
    guarded_only = Workflow.objects.create(owner=owner, name="Guarded only", trigger=Workflow.Trigger.UPDATED, filter_tag=trigger)
    guarded_only.add_tags.add(other_scope)
    mixed = Workflow.objects.create(owner=owner, name="Mixed", trigger=Workflow.Trigger.UPDATED, filter_tag=trigger)
    mixed.add_tags.add(other_scope, plain)
    doc = _document(owner, "Electricity")
    DocumentTag.objects.create(document=doc, tag=bills)

    _, result = _execute(agent, "change_document_tags", {"document_id": str(doc.id), "add": ["Paid"]})
    assert "error" not in result
    skipped = WorkflowRun.objects.get(workflow=guarded_only, document=doc)
    assert skipped.status == WorkflowRun.Status.SKIPPED == "skipped" and skipped.detail.startswith("skipped tag Accountant")
    assert WorkflowRun.objects.get(workflow=mixed, document=doc).status == WorkflowRun.Status.APPLIED
    runs = {run["workflow"]: run["status"] for run in client_for(owner).get("/api/workflows").json()["runs"]}
    assert runs == {"Guarded only": "skipped", "Mixed": "applied"}


# --- Judge 3 L6: an agent reading outside its filter is a refusal ----------------------------------------------------


@pytest.mark.django_db
def test_an_agent_reading_a_document_outside_its_filter_is_logged_as_denied():
    owner = User.objects.create_user("owner", password=PASSWORD)
    bills = Tag.objects.create(owner=owner, name="Bills")
    grant = AgentGrant.objects.create(owner=owner, name="Agent", token_hash="c" * 64, scopes=["documents:search", "documents:text"],
                                      filter_tag=bills, expires_at="2099-01-01T00:00:00Z")
    outside = _document(owner, "Private letter")
    with patch("archive.mcp_server._grant", return_value=grant):
        assert async_to_sync(_call)("get_document_text", {"document_id": str(outside.id)}).is_error
        assert async_to_sync(_call)("get_document_text", {"document_id": str(uuid4())}).is_error  # no such document
    audits = list(AgentAudit.objects.order_by("id").values_list("outcome", "document_id"))
    assert audits == [("denied", outside.id), ("error", None)]


# --- Judge 2 L4: unknown API paths answer in JSON, even in DEBUG -------------------------------------------------------


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_an_unknown_api_path_answers_json_without_the_url_list():
    owner = User.objects.create_user("owner", password=PASSWORD)
    for client in (Client(), client_for(owner)):
        response = client.get("/api/no-such-route")
        assert response.status_code == 404 and response.json() == {"error": "Not found"}
        assert b"api/documents" not in response.content
    italian = Client().get("/api/no-such-route", HTTP_ACCEPT_LANGUAGE="it")
    assert italian.json() == {"error": EXACT["Not found"]}
    # A view's own JSON 404 is kept.
    assert client_for(owner).get(f"/api/documents/{uuid4()}").json() == {"error": "Document not found"}


# --- Judge 1 L2: a sticker created without a location has a "created" history entry ----------------------------------


@pytest.mark.django_db
def test_a_sticker_created_without_a_location_starts_its_history():
    owner = User.objects.create_user("owner", password=PASSWORD)
    doc = _document(owner, "Lease")
    client = client_for(owner)
    created = send(client, "post", f"/api/documents/{doc.id}/copies", {})
    assert created.status_code == 201
    copy = PhysicalCopy.objects.get(document=doc)
    assert list(Movement.objects.filter(physical_copy=copy).values_list("kind", flat=True)) == ["created"]
    history = client.get(f"/api/copies/{copy.id}/history").json()["movements"]
    assert len(history) == 1 and history[0]["to"] == [] and history[0]["note"] == "Sticker created" and history[0]["by"] == "owner"
    italian = client.get(f"/api/copies/{copy.id}/history", HTTP_ACCEPT_LANGUAGE="it").json()["movements"]
    assert italian[0]["note"] == DISPLAY["Sticker created"]


# --- Review of the round-8 fixes ---------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_migration_requeues_old_damaged_pdf_failures_and_can_be_reversed():
    """Old failures never went through filing, so they are processed again from the start (review M1, L5)."""
    from importlib import import_module

    from django.apps import apps

    migration = import_module("archive.migrations.0061_processing_warning_skipped_runs_sticker_created")
    owner = User.objects.create_user("owner", password=PASSWORD)
    old = _document(owner, "Damaged", archive_path="archive/x.pdf")
    Document.objects.filter(pk=old.pk).update(status=Document.Status.FAILED, error=PROCESSING_ERRORS["damaged_pdf"], processing_failures=2)
    other = _document(owner, "Other failure")
    Document.objects.filter(pk=other.pk).update(status=Document.Status.FAILED, error="Something else")
    migration.salvaged_pdfs_are_processed(apps, None)
    old.refresh_from_db()
    assert old.status == Document.Status.PENDING and old.processed_at is None and old.error == "" and old.processing_failures == 0
    assert Document.objects.get(pk=other.pk).status == Document.Status.FAILED
    # The every-minute reconcile task queues it for normal processing (first run: filing and "added" workflows).
    from archive.tasks import reconcile_pending_documents

    with patch("archive.tasks.process_document.delay") as queued:
        reconcile_pending_documents()
    assert [call.args[0] for call in queued.call_args_list] == [str(old.id)]
    # Not shown as a warning while it waits.
    client = client_for(owner)
    assert client.get("/api/overview").json()["documents"]["warnings"] == 0
    assert client.get(f"/api/documents/{old.id}").json()["processing_warning"] is None
    migration.back_to_failed(apps, None)
    old.refresh_from_db()
    assert old.status == Document.Status.FAILED and old.error == PROCESSING_ERRORS["damaged_pdf"] and old.processing_warning == ""


@pytest.mark.django_db
def test_reprocessing_replaces_a_stale_warning(tmp_path):
    whole = _blank_pdf(3)
    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False):
        client, document = _upload_and_process(tmp_path, whole[:len(whole) // 2], ocr_pages=1)
        assert document.processing_warning == "damaged_pdf"
        from archive.tasks import process_document

        # A later failed run clears it (the file did not get through at all).
        Document.objects.filter(pk=document.pk).update(status=Document.Status.PENDING)
        with patch("archive.tasks.subprocess.run", side_effect=OSError("ocr gone")):
            process_document(str(document.id))
        document.refresh_from_db()
        assert document.status == Document.Status.FAILED and document.processing_warning == ""
        assert client.get("/api/overview").json()["documents"]["warnings"] == 0


@pytest.mark.django_db
def test_previews_of_a_salvaged_pdf_come_from_the_searchable_pdf_not_an_old_cache(tmp_path):
    whole = _blank_pdf(3)
    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False):
        client, document = _upload_and_process(tmp_path, whole[:len(whole) // 2], ocr_pages=1)
        from archive.versions import _preview_dir

        stale = _preview_dir(document) / f"v{document.version_number}-1.png"  # the key used before this fix
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_bytes(b"\x89PNG\r\n\x1a\nstale")
        (_preview_dir(document) / f"v{document.version_number}-original-1.png").write_bytes(b"\x89PNG\r\n\x1a\noriginal")
        rendered = []

        def fake_gs(args, **kwargs):
            rendered.append(args[-1])
            output = next(item for item in args if item.startswith("-sOutputFile="))[len("-sOutputFile="):]
            Path(output).write_bytes(b"\x89PNG\r\n\x1a\nfresh")

        with patch("archive.versions.subprocess.run", side_effect=fake_gs):
            response = client.get(f"/api/documents/{document.id}/pages/1.png")
        assert response.status_code == 200 and b"".join(response.streaming_content).endswith(b"fresh")
        assert rendered == [str(tmp_path / document.archive_path)]


@pytest.mark.django_db
def test_revoked_bundles_lose_their_zip_at_once(tmp_path, django_capture_on_commit_callbacks):
    cache.clear()
    anna = User.objects.create_user("anna", password=PASSWORD)
    media = tmp_path / "media"
    with override_settings(MEDIA_ROOT=media, PUBLIC_ORIGIN="https://archive.example"):
        _share_everything(anna, media, django_capture_on_commit_callbacks)
        bundle = ShareBundle.objects.get()
        zip_file = media / bundle.zip_path
        assert bundle.zip_path and zip_file.exists()
        with django_capture_on_commit_callbacks(execute=True):
            send(client_for(anna), "post", "/api/account/password", {"current_password": PASSWORD, "new_password": NEW_PASSWORD})
        bundle.refresh_from_db()
        assert bundle.zip_path == "" and not zip_file.exists()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_the_json_404_leaves_other_answers_alone():
    owner = User.objects.create_user("owner", password=PASSWORD)
    client = client_for(owner)
    # A known route with the wrong method stays 405.
    assert client.delete("/api/overview").status_code == 405
    # A trailing slash is an unknown API path too: JSON, no URL list.
    slash = client.get("/api/overview/")
    assert slash.status_code == 404 and slash.json() == {"error": "Not found"}
    # Paths outside /api/ (the MCP server is a separate process behind the gateway) keep Django's own answer.
    outside = client.get("/mcp")
    assert outside.status_code == 404 and not outside.get("Content-Type", "").startswith("application/json")
