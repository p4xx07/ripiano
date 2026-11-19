"""Round-7 judge findings and owner decisions: share links of turned-off accounts (D9), password to forget an agent
(D10), workflow run details in Italian, guidance after a repeated OCR failure, kept hand-added tags, and numbers
after a hyphen in search."""

import ast
import json
import subprocess
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, override_settings
from django.utils import timezone

from archive import workflows
from archive.api_language import run_detail_to_italian
from archive.message_catalog import _template
from archive.messages_it import EXACT, RUN_DETAILS
from archive.models import AgentAudit, AgentGrant, Document, DocumentTag, ShareBundle, ShareLink, Tag, Workflow, WorkflowRun
from archive.tasks import PROCESSING_ERRORS, process_document
from archive.test_bundles import create_bundle, png, upload
from archive.test_share_links import make_document

User = get_user_model()
PASSWORD = "secure-password-1"


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def send(client, method, url, body):
    return getattr(client, method)(url, json.dumps(body), content_type="application/json")


# --- D9: share links and bundles end when the account is turned off -------------------------------------------------


@pytest.mark.django_db
def test_turning_an_account_off_ends_its_share_links_and_bundles_for_good(tmp_path, django_capture_on_commit_callbacks):
    admin = User.objects.create_superuser("admin", password=PASSWORD)
    anna = User.objects.create_user("anna", password=PASSWORD)
    media = tmp_path / "media"
    document, original, _ = make_document(anna, media, "lease.pdf")
    anna_client = client_for(anna)
    with override_settings(MEDIA_ROOT=media, PUBLIC_ORIGIN="https://archive.example"):
        link = anna_client.post(f"/api/documents/{document.id}/shares", {"expires_in_days": 7}, content_type="application/json").json()
        link_url = link["url"].replace("https://archive.example", "")
        scan = upload(anna, media, "scan.png", png("red"))
        bundle = create_bundle(anna_client, [scan.id], django_capture_on_commit_callbacks).json()
        bundle_url = bundle["url"].replace("https://archive.example", "")
        anonymous = Client()
        assert anonymous.get(link_url).status_code == 200
        assert anonymous.get(bundle_url).status_code == 200
        unknown_link = anonymous.get("/api/share-links/" + "x" * 43)
        unknown_bundle = anonymous.get("/api/share-bundles/" + "x" * 43)

        admin_client = client_for(admin)
        assert send(admin_client, "patch", f"/api/people/{anna.pk}", {"is_active": False, "current_password": PASSWORD}).status_code == 200
        # The same answer as an unknown link: nothing tells a visitor the account exists or was turned off.
        for url, unknown in ((link_url, unknown_link), (bundle_url, unknown_bundle)):
            ended = anonymous.get(url)
            assert ended.status_code == unknown.status_code == 404 and ended.json() == unknown.json()
        assert ShareLink.objects.get().revoked_reason == "account_off"
        assert ShareBundle.objects.get().revoked_reason == "account_off"

        # Turning the account back on does not revive them; the owner sees why they ended.
        assert send(admin_client, "patch", f"/api/people/{anna.pk}", {"is_active": True, "current_password": PASSWORD}).status_code == 200
        assert anonymous.get(link_url).status_code == 404 and anonymous.get(bundle_url).status_code == 404
        anna_client = client_for(anna)
        shares = anna_client.get(f"/api/documents/{document.id}/shares").json()["shares"]
        assert shares[0]["active"] is False and shares[0]["revoked_reason"] == "account_off"
        bundles = anna_client.get("/api/share-bundles").json()["bundles"]
        assert bundles[0]["active"] is False and bundles[0]["revoked_reason"] == "account_off"
        # A new link works again.
        fresh = anna_client.post(f"/api/documents/{document.id}/shares", {"expires_in_days": 7}, content_type="application/json").json()
        assert fresh["revoked_reason"] is None
        assert anonymous.get(fresh["url"].replace("https://archive.example", "")).status_code == 200


@pytest.mark.django_db
def test_an_inactive_owners_links_are_refused_even_if_not_revoked(tmp_path, django_capture_on_commit_callbacks):
    anna = User.objects.create_user("anna", password=PASSWORD)
    media = tmp_path / "media"
    document, _, _ = make_document(anna, media, "lease.pdf")
    anna_client = client_for(anna)
    with override_settings(MEDIA_ROOT=media, PUBLIC_ORIGIN="https://archive.example"):
        link = anna_client.post(f"/api/documents/{document.id}/shares", {"expires_in_days": 7}, content_type="application/json").json()
        scan = upload(anna, media, "scan.png", png("red"))
        bundle = create_bundle(anna_client, [scan.id], django_capture_on_commit_callbacks).json()
        User.objects.filter(pk=anna.pk).update(is_active=False)  # turned off outside the People screen
        anonymous = Client()
        assert anonymous.get(link["url"].replace("https://archive.example", "")).json() == {"error": "Link not found"}
        assert anonymous.get(bundle["url"].replace("https://archive.example", "")).json() == {"error": "Link not found"}


# --- D10: removing an agent with its activity log asks for the password -----------------------------------------------


@pytest.mark.django_db
def test_forgetting_an_agent_needs_the_owners_password():
    cache.clear()
    owner = User.objects.create_user("owner", password=PASSWORD)
    client = client_for(owner)
    revoked = AgentGrant.objects.create(owner=owner, name="Gone", token_hash="c" * 64, scopes=["documents:search"],
                                        expires_at=timezone.now() + timedelta(days=3), revoked_at=timezone.now())
    AgentAudit.objects.create(grant=revoked, action="search_documents", outcome="ok")
    url = f"/api/agents/{revoked.id}?forget=1"
    missing = client.delete(url)
    assert missing.status_code == 400 and missing.json() == {"error": "Invalid JSON"}
    wrong = send(client, "delete", url, {"password": "not-the-password"})
    assert wrong.status_code == 400 and wrong.json() == {"error": "Your password is not correct"}
    # The same message as creating an agent with a wrong password, in Italian too.
    created = send(client, "post", "/api/agents", {"password": "not-the-password", "name": "x", "scopes": ["documents:search"]})
    assert created.status_code == wrong.status_code and created.json() == wrong.json()
    italian = client.delete(url, json.dumps({"password": "nope"}), content_type="application/json", HTTP_ACCEPT_LANGUAGE="it")
    assert italian.json()["error"] == EXACT["Your password is not correct"]
    assert AgentGrant.objects.filter(pk=revoked.pk).exists() and AgentAudit.objects.filter(grant=revoked).exists()
    assert send(client, "delete", url, {"password": PASSWORD}).json() == {"deleted": True}
    assert not AgentAudit.objects.filter(grant_id=revoked.id).exists()


@pytest.mark.django_db
def test_forgetting_an_agent_shares_the_sign_in_throttle():
    cache.clear()
    owner = User.objects.create_user("owner", password=PASSWORD)
    client = client_for(owner)
    revoked = AgentGrant.objects.create(owner=owner, name="Gone", token_hash="c" * 64, scopes=["documents:search"],
                                        expires_at=timezone.now() + timedelta(days=3), revoked_at=timezone.now())
    url = f"/api/agents/{revoked.id}?forget=1"
    statuses = [send(client, "delete", url, {"password": "wrong"}).status_code for _ in range(12)]
    assert statuses[0] == 400 and statuses[-1] == 429
    blocked = send(client, "delete", url, {"password": PASSWORD})
    assert blocked.json() == {"error": "Too many attempts. Wait a few minutes and try again."}
    assert AgentGrant.objects.filter(pk=revoked.pk).exists()
    # Plain revoke needs no password.
    active = AgentGrant.objects.create(owner=owner, name="Live", token_hash="d" * 64, scopes=["documents:search"],
                                       expires_at=timezone.now() + timedelta(days=3))
    assert client.delete(f"/api/agents/{active.id}").json() == {"revoked": True}
    cache.clear()


# --- Workflow run details in the reader's language, and kept hand-added tags ---------------------------------------


def _detail_templates():
    """Every run-detail part written in archive/workflows.py."""
    tree = ast.parse(Path(workflows.__file__).read_text())
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append"
                and isinstance(node.func.value, ast.Name) and node.func.value.id in ("changes", "outcome")):
            values = node.args
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "WebhookError":
            values = node.args
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id.endswith("_DETAIL") for target in node.targets):
            values = [node.value]
        else:
            continue
        for value in values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                found.add(value.value)
            elif isinstance(value, ast.JoinedStr):
                found.add(_template(value))
    return found


def test_every_run_detail_part_has_an_italian_version():
    parts = _detail_templates()
    assert {"added tag {0}", "kept tag {0} (added by hand)", "webhook refused ({0})"} <= parts
    assert not parts - set(RUN_DETAILS), sorted(parts - set(RUN_DETAILS))
    assert all(english != italian and italian.strip() for english, italian in RUN_DETAILS.items())
    assert run_detail_to_italian("conditions matched; nothing needed changing") == RUN_DETAILS["conditions matched; nothing needed changing"]
    assert run_detail_to_italian("email sent to 2 recipients without the file (over 25 MB)") == "email inviata a 2 destinatari senza il file (oltre 25 MB)"
    assert run_detail_to_italian("set field Paid to yes") == "impostato il campo Paid a sì"
    # Names that contain the separators stay whole; unknown text stays English.
    assert (run_detail_to_italian("added tag Casa, mutuo, removed tag Old; webhook delivered")
            == "aggiunta l'etichetta Casa, mutuo, rimossa l'etichetta Old; webhook consegnato")
    assert run_detail_to_italian("something new, added tag A") == "something new, added tag A"


@pytest.mark.django_db
def test_run_details_follow_accept_language_and_name_kept_hand_added_tags():
    owner = User.objects.create_user("owner", password=PASSWORD)
    keep, drop, add = (Tag.objects.create(owner=owner, name=name) for name in ("Mine, by hand", "Auto", "Filed"))
    document = Document.objects.create(owner=owner, title="Letter", original_name="a.pdf", original_path="a.pdf", original_mime="application/pdf",
                                       original_sha256="0" * 64, original_size=1, status=Document.Status.READY, extracted_text="hello")
    DocumentTag.objects.create(document=document, tag=keep, origin=DocumentTag.Origin.MANUAL)
    DocumentTag.objects.create(document=document, tag=drop, origin=DocumentTag.Origin.SOURCE)
    workflow = Workflow.objects.create(owner=owner, name="Tidy", trigger=Workflow.Trigger.UPDATED, filter_text="hello")
    workflow.add_tags.add(add)
    workflow.remove_tags.add(keep, drop)
    client = client_for(owner)
    ran = send(client, "post", f"/api/workflows/{workflow.id}/run", {"document_id": str(document.id)})
    assert ran.status_code == 200, ran.json()
    detail = WorkflowRun.objects.get().detail
    assert detail == "added tag Filed, kept tag Mine, by hand (added by hand), removed tag Auto"
    assert set(DocumentTag.objects.filter(document=document).values_list("tag__name", flat=True)) == {"Mine, by hand", "Filed"}
    english = client.get("/api/workflows").json()["runs"][0]["detail"]
    italian = client.get("/api/workflows", HTTP_ACCEPT_LANGUAGE="it").json()["runs"][0]["detail"]
    assert english == detail
    assert italian == "aggiunta l'etichetta Filed, mantenuta l'etichetta Mine, by hand (aggiunta a mano), rimossa l'etichetta Auto"
    # A workflow that does not match answers in Italian too.
    other = Document.objects.create(owner=owner, title="Other", original_name="b.pdf", original_path="b.pdf", original_mime="application/pdf",
                                    original_sha256="1" * 64, original_size=1, status=Document.Status.READY, extracted_text="nothing")
    unmatched = client.post(f"/api/workflows/{workflow.id}/run", json.dumps({"document_id": str(other.id)}), content_type="application/json",
                            HTTP_ACCEPT_LANGUAGE="it").json()
    assert unmatched["matched"] is False and unmatched["detail"] == EXACT["This document does not match the workflow’s conditions."]


@pytest.mark.django_db
def test_failed_workflow_runs_on_overview_are_localized():
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = Document.objects.create(owner=owner, title="Letter", original_name="a.pdf", original_path="a.pdf", original_mime="application/pdf",
                                       original_sha256="0" * 64, original_size=1, status=Document.Status.READY)
    workflow = Workflow.objects.create(owner=owner, name="Notify", trigger=Workflow.Trigger.ADDED)
    WorkflowRun.objects.create(workflow=workflow, document=document, trigger="added", status=WorkflowRun.Status.FAILED,
                               detail="set type Bill; webhook refused (500)")
    italian = client_for(owner).get("/api/jobs", HTTP_ACCEPT_LANGUAGE="it").json()["workflow_failures"][0]["detail"]
    assert italian == "impostato il tipo Bill; webhook rifiutato (500)"


# --- L4: a repeated OCR failure stops suggesting Retry OCR ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_second_ocr_failure_suggests_rescanning_instead_of_retrying(tmp_path):
    owner = User.objects.create_user("owner", password=PASSWORD)
    client = client_for(owner)
    failure = subprocess.CalledProcessError(1, "ocrmypdf", stderr="ValueError: broken xref")
    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False), patch("archive.ingestion.process_document.delay"), \
            patch("archive.tasks.process_document.delay"), patch("archive.tasks.subprocess.run", side_effect=failure):
        upload_response = client.post("/api/documents", {"document": SimpleUploadedFile(
            "letter.pdf", b"%PDF-1.4\nbroken", content_type="application/pdf")})
        document_id = upload_response.json()["id"]
        process_document(document_id)
        first = Document.objects.get(pk=document_id)
        assert first.error == PROCESSING_ERRORS["generic"] and "Retry OCR" in first.error
        assert client.post(f"/api/documents/{document_id}/retry").status_code == 202
        process_document(document_id)
        again = Document.objects.get(pk=document_id)
        assert again.status == Document.Status.FAILED and again.error == PROCESSING_ERRORS["generic_again"]
        assert "Retry OCR" not in again.error
        italian = client.get(f"/api/documents/{document_id}", HTTP_ACCEPT_LANGUAGE="it").json()["error"]
        assert italian == EXACT[PROCESSING_ERRORS["generic_again"]]


# --- L2: a number after a hyphen in a title, combined with another word -------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="stored tsvector search runs on PostgreSQL")
def test_a_number_from_a_hyphenated_title_combines_with_other_words():
    owner = User.objects.create_user("owner", password=PASSWORD)
    for title, text in (("j3r7-58458-three-pages", "A lease with an otter."), ("Fattura-2026-031", "Bolletta luce"), ("Unrelated 99999", "otter")):
        Document.objects.create(owner=owner, title=title, original_name="scan.pdf", original_path=title, original_mime="application/pdf",
                                original_sha256=(title * 64)[:64], original_size=1, status=Document.Status.READY, extracted_text=text)
    client = client_for(owner)

    def titles(query):
        return [item["title"] for item in client.get("/api/documents", {"q": query}).json()["documents"]]

    assert titles("otter 58458") == ["j3r7-58458-three-pages"]
    assert titles("58458 three") == ["j3r7-58458-three-pages"]
    assert titles("031 bolletta") == ["Fattura-2026-031"]
    assert titles("otter 12345") == []


@pytest.mark.django_db
def test_turning_on_an_account_turned_off_elsewhere_does_not_revive_its_links():
    """Review M1: an account switched off outside People (admin, shell, older version) keeps no live links."""
    from archive.models import ShareLink

    User = get_user_model()
    admin = User.objects.create_superuser("d9-admin", password="secure-password-1")
    owner = User.objects.create_user("d9-elsewhere", password="secure-password-1")
    doc = Document.objects.create(owner=owner, title="Lease", original_name="l.pdf", original_path="l.pdf", original_mime="application/pdf",
                                  original_sha256="9" * 64, original_size=1, status=Document.Status.READY)
    link = ShareLink.objects.create(owner=owner, document=doc, token_hash="d9" * 32, expires_at=timezone.now() + timedelta(days=3))
    User.objects.filter(pk=owner.pk).update(is_active=False)  # not through People
    client = Client()
    client.force_login(admin)
    response = client.patch(f"/api/people/{owner.pk}", {"is_active": True, "current_password": "secure-password-1"}, content_type="application/json")
    assert response.status_code == 200, response.content
    link.refresh_from_db()
    assert link.revoked_at is not None and link.revoked_reason == "account_off"
