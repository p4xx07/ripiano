"""Findings of the independent review of the round-10 fixes (.omo/evidence/round10-fixes-review.md).

M1: disclosure stays held back in later runs while an agent-set value is why the workflow matches. M2: a held-back
run does not use up the one-time webhook and email. M3: Idempotency-Key on POSTs. L1-L6, L8: see each test.
"""

import json
import shutil
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import Client, override_settings
from django.utils import timezone

from archive import backup, idempotency
from archive.backup import BackupError, create_snapshot, restore_snapshot
from archive.models import (AgentGrant, Correspondent, Document, DocumentAccess, DocumentNote, DocumentTag, DocumentVersion,
                            IdempotencyRecord, ProcessingClaim, Tag, Workflow, WorkflowRun)
from archive.test_backup import fake_database_command
from archive.test_round10_fixes import database_down
from archive.workflows import HELD_EMAIL, HELD_SHARE, run_for_document, run_scheduled

User = get_user_model()
PASSWORD = "secure-password-1"


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def send(client, method, url, body, **extra):
    return getattr(client, method)(url, json.dumps(body), content_type="application/json", **extra)


def _doc(owner, title="Scan", **values):
    values.setdefault("status", Document.Status.READY)
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path=f"originals/aa/{title}.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10, **values)


def _agent(owner):
    return AgentGrant.objects.create(owner=owner, name="Tagger", token_hash="c" * 64, scopes=["documents:tag"],
                                     expires_at=timezone.now() + timedelta(days=30))


@pytest.fixture
def immediate_commit(monkeypatch):
    """Run on-commit work at once, so a test can look at notifications between steps."""
    monkeypatch.setattr("django.db.transaction.on_commit", lambda func, **kwargs: func())


@pytest.fixture
def people(db):
    return User.objects.create_user("owner", password=PASSWORD), User.objects.create_user("luca", password="secure-password-2")


def _sharing_workflow(owner, luca, tag, trigger=Workflow.Trigger.UPDATED, **values):
    return Workflow.objects.create(owner=owner, name="Share with Luca", trigger=trigger, filter_tag=tag, email_to="accountant@example.test",
                                   share_with=[{"kind": "person", "id": luca.pk, "level": "view"}], **values)


def _agent_tags(document, tag):
    """What the MCP change_document_tags tool leaves behind."""
    DocumentTag.objects.create(document=document, tag=tag, origin=DocumentTag.Origin.MODEL)


# --- M1 / M2 ----------------------------------------------------------------------------------------------------------


def test_the_owners_later_edits_do_not_complete_a_share_an_agents_tag_asked_for(people, immediate_commit):
    owner, luca = people
    share = Tag.objects.create(owner=owner, name="Share with Luca")
    other = Tag.objects.create(owner=owner, name="Other")
    flow = _sharing_workflow(owner, luca, share)
    document = _doc(owner)
    client = client_for(owner)
    with patch("archive.tasks.send_workflow_notifications.delay") as notify:
        _agent_tags(document, share)
        run_for_document(document, Workflow.Trigger.UPDATED, agent_grant=_agent(owner))
        # A typo fix, a save that lists the tags again plus one more, and a bulk change: the agent's tag is still the
        # agent's, so nothing is disclosed.
        assert send(client, "patch", f"/api/documents/{document.id}", {"title": "Scan, corrected"}).status_code == 200
        assert send(client, "patch", f"/api/documents/{document.id}", {"tags": [str(share.id), str(other.id)]}).status_code == 200
        assert DocumentTag.objects.get(document=document, tag=share).origin == DocumentTag.Origin.MODEL
        assert DocumentTag.objects.get(document=document, tag=other).origin == DocumentTag.Origin.MANUAL
        bulk = send(client, "post", "/api/documents/bulk-tags", {"action": "remove", "document_ids": [str(document.id)], "tag_id": str(other.id)})
        assert bulk.status_code == 200
        assert not DocumentAccess.objects.exists()
        notify.assert_not_called()
        runs = WorkflowRun.objects.filter(workflow=flow)
        assert runs.count() == 4 and all(run.held_back and HELD_SHARE in run.detail for run in runs)
        assert sum(HELD_EMAIL in run.detail for run in runs) == 4  # still due, held back each time

        # The owner adds the tag herself: it is hers now, the document is shared and the email goes out once (M2).
        assert send(client, "patch", f"/api/documents/{document.id}", {"add_tag_id": str(share.id)}).status_code == 200
        assert DocumentAccess.objects.filter(document=document, user=luca).exists()
        latest = WorkflowRun.objects.filter(workflow=flow).first()
        assert not latest.held_back and "queued email" in latest.detail
        notify.assert_called_once_with(str(latest.id))
        assert send(client, "patch", f"/api/documents/{document.id}", {"title": "Scan, again"}).status_code == 200
        notify.assert_called_once()  # the one-time email is used up now


def test_a_scheduled_workflow_waits_until_a_person_confirms_the_agents_tag(people, immediate_commit):
    owner, luca = people
    tag = Tag.objects.create(owner=owner, name="Accountant")
    flow = _sharing_workflow(owner, luca, tag, trigger=Workflow.Trigger.SCHEDULED, schedule_days=0, schedule_field=Workflow.DateField.DOCUMENT_DATE)
    document = _doc(owner, document_date=date.today())
    _agent_tags(document, tag)
    with patch("archive.tasks.send_workflow_notifications.delay") as notify:
        assert run_scheduled() == 1
        run = WorkflowRun.objects.get(workflow=flow)
        assert run.held_back and run.status == WorkflowRun.Status.SKIPPED and not DocumentAccess.objects.exists()
        assert run_scheduled() == 0 and WorkflowRun.objects.count() == 1  # looked at again, still held, nothing new
        notify.assert_not_called()
        bulk = send(client_for(owner), "post", "/api/documents/bulk-tags", {"action": "add", "document_ids": [str(document.id)], "tag_id": str(tag.id)})
        assert bulk.status_code == 200
        assert run_scheduled() == 1
        run.refresh_from_db()
        assert not run.held_back and run.status == WorkflowRun.Status.APPLIED and WorkflowRun.objects.count() == 1
        assert DocumentAccess.objects.filter(document=document, user=luca).exists()
        notify.assert_called_once_with(str(run.id))
        assert run_scheduled() == 0


def test_agent_set_sender_holds_back_and_run_now_or_the_owners_choice_releases(people):
    owner, luca = people
    sender = Correspondent.objects.create(owner=owner, name="Acme")
    Workflow.objects.create(owner=owner, name="Share Acme", trigger=Workflow.Trigger.UPDATED, filter_correspondent=sender,
                            share_with=[{"kind": "person", "id": luca.pk, "level": "view"}])
    by_agent = _doc(owner, "agent", correspondent=sender, correspondent_origin=Document.FilingOrigin.MODEL)
    chosen = _doc(owner, "chosen", correspondent=sender, correspondent_origin=Document.FilingOrigin.MODEL)
    client = client_for(owner)
    assert send(client, "patch", f"/api/documents/{by_agent.id}", {"title": "agent, renamed"}).status_code == 200
    assert not DocumentAccess.objects.exists()
    flow = Workflow.objects.get()
    assert send(client, "post", f"/api/workflows/{flow.id}/run", {"document_id": str(by_agent.id)}).status_code < 300
    assert DocumentAccess.objects.filter(document=by_agent, user=luca).exists()
    # Choosing the sender herself makes it hers.
    assert send(client, "patch", f"/api/documents/{chosen.id}", {"correspondent_id": str(sender.id)}).status_code == 200
    assert DocumentAccess.objects.filter(document=chosen, user=luca).exists()


def test_what_a_held_back_run_files_is_marked_as_the_agents_so_a_second_workflow_is_held_back_too(people):
    owner, luca = people
    first, second = Tag.objects.create(owner=owner, name="Invoices"), Tag.objects.create(owner=owner, name="To Luca")
    tagging = Workflow.objects.create(owner=owner, name="Tag", trigger=Workflow.Trigger.UPDATED, filter_tag=first, order=1)
    tagging.add_tags.add(second)
    _sharing_workflow(owner, luca, second, order=2)
    document = _doc(owner)
    _agent_tags(document, first)
    run_for_document(document, Workflow.Trigger.UPDATED, agent_grant=_agent(owner))
    assert DocumentTag.objects.get(document=document, tag=second).origin == DocumentTag.Origin.MODEL
    assert send(client_for(owner), "patch", f"/api/documents/{document.id}", {"title": "renamed"}).status_code == 200
    assert not DocumentAccess.objects.exists()


def test_a_held_back_run_keeps_the_one_time_email_for_the_owners_own_change(people, django_capture_on_commit_callbacks):
    """M2: the workflow has no agent-settable condition; the agent's run holds the email, the owner's next change sends it."""
    owner, _luca = people
    flow = Workflow.objects.create(owner=owner, name="Tell me", trigger=Workflow.Trigger.UPDATED, email_to="me@example.test", add_note="Seen")
    document = _doc(owner)
    with patch("archive.tasks.send_workflow_notifications.delay") as notify, django_capture_on_commit_callbacks(execute=True):
        held = run_for_document(document, Workflow.Trigger.UPDATED, agent_grant=_agent(owner))[0]
        assert held.held_back and HELD_EMAIL in held.detail
        notify.assert_not_called()
        for title in ("one", "two"):
            assert send(client_for(owner), "patch", f"/api/documents/{document.id}", {"title": title}).status_code == 200
    details = list(WorkflowRun.objects.filter(workflow=flow).order_by("created_at").values_list("detail", flat=True))
    assert sum("queued email" in detail for detail in details) == 1 and "queued email" in details[1]
    assert notify.call_count == 1 and DocumentNote.objects.filter(document=document, body="Seen").count() == 1
    listed = client_for(owner).get("/api/workflows").json()["runs"]
    assert sorted(run["held_back"] for run in listed) == [False, False, True]


# --- M3: Idempotency-Key ------------------------------------------------------------------------------------------------


def _note(client, document, key, body="Paid on Monday", **extra):
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key is not None else {}
    return send(client, "post", f"/api/documents/{document.id}/notes", {"body": body}, **headers, **extra)


def test_a_repeated_post_with_the_same_key_returns_the_first_answer_and_creates_nothing_new(people):
    owner, luca = people
    document, other = _doc(owner), _doc(owner, "other")
    client, key = client_for(owner), str(uuid.uuid4())
    first = _note(client, document, key)
    again = _note(client, document, key)
    assert first.status_code == again.status_code == 201 and first.json() == again.json()
    assert "Idempotent-Replay" not in first and again["Idempotent-Replay"] == "true"
    assert DocumentNote.objects.count() == 1
    # The stored answer is not readable in the table.
    assert "Paid on Monday" not in IdempotencyRecord.objects.get().body
    # Another key, or no key, is a new request.
    assert _note(client, document, str(uuid.uuid4())).status_code == 201 and _note(client, document, None).status_code == 201
    assert DocumentNote.objects.count() == 3
    # Never across paths or people.
    crossed = _note(client, other, key)
    assert crossed.status_code == 422 and "different request" in crossed.json()["error"] and not DocumentNote.objects.filter(document=other).exists()
    theirs = _doc(luca, "theirs")
    assert _note(client_for(luca), theirs, key).json()["id"] != first.json()["id"]
    assert DocumentNote.objects.filter(document=theirs).count() == 1


def test_idempotency_keeps_nothing_for_refused_requests_and_checks_the_key(people):
    owner, _luca = people
    document, client, key = _doc(owner), client_for(owner), "retry-1"
    assert _note(client, document, key, body="").status_code == 400
    assert not IdempotencyRecord.objects.exists()
    assert _note(client, document, key).status_code == 201  # the corrected request runs
    for bad in ("", "has space", "x" * 65, "caffè"):
        assert _note(client, document, bad).status_code == 400, bad
    assert DocumentNote.objects.count() == 1
    # A request without a session is answered as always; the header changes nothing.
    assert _note(Client(), document, key).status_code in (401, 403)
    # An action POST is covered the same way: the second identical retry does not act twice.
    failed = _doc(owner, "failed", status=Document.Status.FAILED)
    with patch("archive.tasks.process_document.delay") as queued:
        one = client.post(f"/api/documents/{failed.id}/retry", HTTP_IDEMPOTENCY_KEY="retry-ocr")
        two = client.post(f"/api/documents/{failed.id}/retry", HTTP_IDEMPOTENCY_KEY="retry-ocr")
    assert one.status_code == two.status_code == 202 and one.json() == two.json() and queued.call_count == 1


def test_a_second_request_waits_for_the_first_and_an_abandoned_or_failed_one_frees_the_key(people):
    owner, _luca = people
    document, client = _doc(owner), client_for(owner)
    running = IdempotencyRecord.objects.create(user=owner, key="busy", path=f"/api/documents/{document.id}/notes")
    with patch.object(idempotency, "WAIT_SECONDS", 0):
        waiting = _note(client, document, "busy")
    assert waiting.status_code == 409 and "still being handled" in waiting.json()["error"] and not DocumentNote.objects.exists()

    # The first request finishes while the second waits: the second gets its answer.
    def finish(_seconds):
        from archive.mail import encrypt_secret

        IdempotencyRecord.objects.filter(pk=running.pk).update(status=201, body=encrypt_secret('{"id": "first"}'))

    with patch("archive.idempotency.time.sleep", side_effect=finish):
        assert _note(client, document, "busy").json() == {"id": "first"}
    assert not DocumentNote.objects.exists()

    # A first request that died (no answer after 90 s) or whose answer is older than ten minutes no longer blocks.
    IdempotencyRecord.objects.filter(pk=running.pk).update(status=None, body="", created_at=timezone.now() - timedelta(minutes=2))
    assert _note(client, document, "busy").status_code == 201
    IdempotencyRecord.objects.update(created_at=timezone.now() - timedelta(minutes=11))
    assert _note(client, document, "busy").status_code == 201 and DocumentNote.objects.count() == 2

    # A request that crashes releases its key, so the retry runs.
    crashing = Client(raise_request_exception=False)
    crashing.force_login(owner)
    with patch("archive.views.DocumentNote.objects.create", side_effect=RuntimeError("boom")):
        assert _note(crashing, document, "crash").status_code == 500
    assert not IdempotencyRecord.objects.filter(key="crash").exists()
    assert _note(crashing, document, "crash").status_code == 201


# --- L1: a run that lost its document writes nothing -------------------------------------------------------------------


@pytest.mark.django_db
def test_a_cancelled_run_adds_no_barcode_tags_or_archive_number_and_does_not_publish_its_pdf(tmp_path):
    from archive.barcodes import BarcodeScan
    from archive.tasks import _save_result, apply_barcodes

    owner = User.objects.create_user("owner", password=PASSWORD)
    Tag.objects.create(owner=owner, name="Taxes")
    document = _doc(owner, status=Document.Status.FAILED)  # cancelled by the owner; the claim is gone
    scan = BarcodeScan(pages=1, scanned=1, asn=42, tags=["Taxes"])
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.barcodes.scan_pdf", return_value=scan):
        apply_barcodes(document, tmp_path / "x.pdf", tmp_path / "x.pdf", tmp_path, token=uuid.uuid4())
        assert not DocumentTag.objects.exists() and Document.objects.get(pk=document.pk).asn is None
        published = []
        assert _save_result(document, uuid.uuid4(), ["status"], publish=lambda: published.append(1)) is False
        assert not published
        # The run that still holds the document does both.
        Document.objects.filter(pk=document.pk).update(status=Document.Status.PROCESSING)
        claim = ProcessingClaim.objects.create(document=document)
        apply_barcodes(document, tmp_path / "x.pdf", tmp_path / "x.pdf", tmp_path, token=claim.token)
        assert DocumentTag.objects.count() == 1 and Document.objects.get(pk=document.pk).asn == 42
        document.status = Document.Status.READY
        assert _save_result(document, claim.token, ["status"], publish=lambda: published.append(1)) is True and published == [1]


# --- L2 / L3 / L4: files and the database agree ---------------------------------------------------------------------------


def _media(tmp_path, *names):
    media = tmp_path / "media"
    for name in names:
        (media / name).parent.mkdir(parents=True, exist_ok=True)
        (media / name).write_bytes(name.encode())
    return media


@pytest.mark.django_db
def test_restore_removes_files_the_restored_database_does_not_know(tmp_path):
    from archive.models import PurgeJob

    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, archive_path="archive/aa/known.pdf")
    DocumentVersion.objects.create(document=document, number=1, note="first", original_name="v1.pdf", original_path="originals/aa/v1.pdf",
                                   original_mime="application/pdf", original_sha256="1" * 64, original_size=1, created_at=timezone.now())
    PurgeJob.objects.create(owner=owner, document_id=uuid.uuid4(), original_path="originals/aa/purging.pdf", original_sha256="2" * 64,
                            version_files=[{"path": "originals/aa/purging-v1.pdf", "sha256": "3" * 64}])
    known = [document.original_path, "archive/aa/known.pdf", "originals/aa/v1.pdf", "originals/aa/purging.pdf", "originals/aa/purging-v1.pdf"]
    unknown = ["originals/aa/split-part-without-row.pdf", "archive/aa/finished-during-copy.pdf"]
    media = _media(tmp_path, *known, *unknown)
    assert backup._remove_unknown_media([media / name for name in known + unknown], media) == 2
    assert all((media / name).exists() for name in known) and not any((media / name).exists() for name in unknown)
    # With no documents at all there is nothing to compare with: nothing is removed.
    Document.objects.all().delete()
    assert backup._remove_unknown_media([media / name for name in known], media) == 0


@pytest.mark.django_db
def test_restore_survives_a_failed_requeue_and_cleanup(tmp_path, caplog):
    media = _media(tmp_path, "originals/ab/example.pdf")
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=tmp_path / "backups"), \
            patch("archive.backup._database_command", side_effect=fake_database_command):
        snapshot = create_snapshot()
        with override_settings(MEDIA_ROOT=tmp_path / "restored"), \
                patch("archive.backup._requeue_interrupted_processing", side_effect=OperationalError("gone")), \
                patch("archive.backup._remove_unknown_media", side_effect=OSError("disk")):
            restore_snapshot(snapshot.name)  # logged and left to the scheduler's stall detection
            assert (tmp_path / "restored/originals/ab/example.pdf").exists()
    assert "could not be queued again" in caplog.text and "could not be removed" in caplog.text


@pytest.mark.django_db
def test_backup_fails_when_a_documents_file_disappears_or_keeps_changing(tmp_path):
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner)
    media = _media(tmp_path, document.original_path, "archive/aa/busy.pdf")
    real_copy = shutil.copy2

    def vanish(source, destination, **kwargs):
        if str(source).endswith(document.original_path):
            source.unlink()  # removed by hand on the NAS share, or a failing disk
        return real_copy(source, destination, **kwargs)

    def churn(source, destination, **kwargs):
        if source.name == "busy.pdf":
            source.write_bytes(uuid.uuid4().bytes)  # different after every read
        return real_copy(source, destination, **kwargs)

    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=tmp_path / "backups"), \
            patch("archive.backup._database_command", side_effect=fake_database_command):
        with patch("archive.backup.shutil.copy2", side_effect=churn), pytest.raises(BackupError, match="Media changed during backup"):
            create_snapshot()
        with patch("archive.backup.shutil.copy2", side_effect=vanish), pytest.raises(BackupError, match="disappeared"):
            create_snapshot()
        assert not list((tmp_path / "backups" / "complete").iterdir()) and not list((tmp_path / "backups" / "staging").iterdir())


@pytest.mark.django_db
def test_split_leftover_cleanup_keeps_a_file_that_an_earlier_version_uses(tmp_path):
    from archive.backup import WORK_DIR
    from archive.tasks import SPLIT_JOURNAL, remove_stale_work_dirs

    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, "part")  # was given a new version; its first file lives on as version 1
    DocumentVersion.objects.create(document=document, number=1, note="first", original_name="v1.pdf", original_path="originals/aa/first.pdf",
                                   original_mime="application/pdf", original_sha256="1" * 64, original_size=1, created_at=timezone.now())
    media = _media(tmp_path, "originals/aa/first.pdf", "originals/aa/orphan.pdf")
    folder = media / WORK_DIR / str(uuid.uuid4())
    folder.mkdir(parents=True)
    (folder / SPLIT_JOURNAL).write_text("originals/aa/first.pdf\noriginals/aa/orphan.pdf\n")
    with override_settings(MEDIA_ROOT=media):
        assert remove_stale_work_dirs() == 1
    assert (media / "originals/aa/first.pdf").exists() and not (media / "originals/aa/orphan.pdf").exists()


# --- L5 / L6 / L8 ---------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_passwords_have_an_upper_limit_and_a_new_persons_name_counts():
    admin = User.objects.create_superuser("admin", password=PASSWORD)
    client = client_for(admin)
    huge = "abcdefghijklmnopqrstuvwxyz" * 80_000  # 2 MB: refused before any rule looks at it
    with patch("archive.password_rules._longest_run") as slow_rule:
        for password in (huge, "k" * 129):
            assert send(client, "post", "/api/account/password", {"current_password": PASSWORD, "new_password": password}).json()["error"] == \
                "Use a password of at most 128 characters"
        slow_rule.assert_not_called()
    assert send(client, "post", "/api/account/password", {"current_password": PASSWORD, "new_password": "9f!" + "correct horse battery staple " * 4}).json() == {"changed": True}
    named = send(client, "post", "/api/people", {"username": "ar", "name": "Annamaria", "password": "Annamaria-12", "current_password": "9f!" + "correct horse battery staple " * 4})
    assert named.status_code == 400 and "too close" in named.json()["error"]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_connection_failures_are_reported_as_an_unreachable_database():
    client = Client(raise_request_exception=False)
    for sqlstate, expected in ((None, 503), ("08006", 503), ("57P01", 503), ("40P01", 500), ("53100", 500), ("53300", 500), ("55P03", 500)):
        with patch("archive.views.get_user_model", side_effect=database_down("x", sqlstate)):
            response = client.get("/api/session")
        assert response.status_code == expected and response["Content-Type"] == "application/json", sqlstate
    with patch("archive.views.get_user_model", side_effect=OperationalError("database is locked")):  # no driver error behind it
        assert client.get("/api/session").status_code == 500


def test_stall_detection_runs_on_the_maintenance_worker():
    from django.conf import settings

    assert settings.CELERY_TASK_ROUTES["archive.tasks.reconcile_pending_documents"] == {"queue": "maintenance"}
    assert "archive.tasks.process_document" not in settings.CELERY_TASK_ROUTES
