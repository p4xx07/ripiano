"""Round-10 judge 3 findings: backups succeed while documents are being processed or after a worker was killed (H1),
a workflow started by an agent's change does not disclose the document (M1), weak passwords are refused everywhere a
password is set (L1), a database outage answers JSON 503 on /api/ and /mcp even in DEBUG (L4/L5), and a processing
document can be cancelled at any time (L6; see also test_job_controls and test_round9_fixes)."""

import json
import shutil
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.test import Client, override_settings
from django.utils import timezone

from archive import backup, mcp_server
from archive.backup import WORK_DIR, BackupError, create_snapshot, restore_snapshot, verify_snapshot
from archive.models import AgentGrant, Document, DocumentAccess, DocumentTag, ProcessingClaim, Tag, Workflow, WorkflowRun
from archive.tasks import SPLIT_JOURNAL, _split, process_document, remove_stale_work_dirs
from archive.test_backup import fake_database_command

User = get_user_model()
PASSWORD = "secure-password-1"


def database_down(message="connection refused", sqlstate=None):
    """What Django raises when PostgreSQL cannot be reached: its OperationalError caused by the driver's."""
    import psycopg

    cause = psycopg.OperationalError(message)
    if sqlstate:
        cause = type("Driver", (psycopg.OperationalError,), {"sqlstate": sqlstate})(message)
    error = OperationalError(message)
    error.__cause__ = cause
    return error


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def send(client, method, url, body, **extra):
    return getattr(client, method)(url, json.dumps(body), content_type="application/json", **extra)


def _doc(owner, title="Scan", **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path=f"originals/aa/{title}.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10, **values)


def _media(tmp_path):
    media = tmp_path / "media"
    (media / "originals" / "ab").mkdir(parents=True)
    (media / "originals" / "ab" / "example.pdf").write_bytes(b"original")
    return media


# --- H1: work folders are never part of a snapshot -----------------------------------------------------------------


@pytest.mark.django_db
def test_backup_skips_processing_work_folders_but_still_refuses_unknown_media(tmp_path):
    media = _media(tmp_path)
    running = media / WORK_DIR / str(uuid.uuid4())
    running.mkdir(parents=True)
    (running / "input.pdf").write_bytes(b"half-made")
    (running / SPLIT_JOURNAL).write_text("originals/ab/part.pdf\n")
    for legacy in ("work-2h1kr9ex", "tmpab12cd_x"):  # left by a killed worker of an earlier version
        (media / legacy).mkdir()
        (media / legacy / "input.pdf").write_bytes(b"old")
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=tmp_path / "backups"), \
            patch("archive.backup._database_command", side_effect=fake_database_command):
        snapshot = create_snapshot()
        assert [entry["path"] for entry in verify_snapshot(snapshot)["files"]] == ["originals/ab/example.pdf"]
        assert sorted(path.name for path in (snapshot / "media").iterdir()) == ["originals"]
        (media / "stray").mkdir()
        (media / "stray" / "file.bin").write_bytes(b"?")
        with pytest.raises(BackupError, match="unexpected media path"):
            create_snapshot()
        shutil.rmtree(media / "stray")
        (media / "workshop.txt").write_bytes(b"?")  # only folders named like work folders are skipped
        with pytest.raises(BackupError, match="unexpected media path"):
            create_snapshot()


@pytest.mark.django_db
def test_a_backup_taken_while_a_document_is_being_processed_succeeds_and_holds_its_original(tmp_path):
    from archive.ingestion import ingest_document
    from archive.test_barcodes import fake_ocr, page, pdf

    owner = User.objects.create_user("owner", password=PASSWORD)
    media = tmp_path / "media"
    taken = []

    def ocr(args, **kwargs):
        # The worker is in the middle of text recognition: its work folder holds unfinished files.
        work = list((media / WORK_DIR).iterdir())
        assert len(work) == 1 and uuid.UUID(work[0].name) == ProcessingClaim.objects.get().token
        (work[0] / "half.pdf").write_bytes(b"unfinished")
        with patch("archive.backup._database_command", side_effect=fake_database_command):
            taken.append(create_snapshot())
        return fake_ocr(args, **kwargs)

    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=tmp_path / "backups", RIPIANO_BARCODES=False), \
            patch("archive.ingestion.process_document.delay"), patch("archive.tasks.subprocess.run", side_effect=ocr):
        document = ingest_document(owner, SimpleUploadedFile("letter.pdf", pdf(page("A letter"))))
        process_document(str(document.id))
        document.refresh_from_db()
        assert document.status == Document.Status.READY
        # Mid-processing snapshot: the original, no archive PDF yet, nothing from the work folder.
        assert [entry["path"] for entry in verify_snapshot(taken[0])["files"]] == [document.original_path]
        # The finished run left nothing behind, and a later snapshot has both files.
        assert not list((media / WORK_DIR).iterdir())
        with patch("archive.backup._database_command", side_effect=fake_database_command):
            later = create_snapshot()
        assert sorted(entry["path"] for entry in verify_snapshot(later)["files"]) == sorted([document.archive_path, document.original_path])


@pytest.mark.django_db
def test_work_folders_are_removed_as_soon_as_their_run_no_longer_holds_the_document(tmp_path):
    owner = User.objects.create_user("owner", password=PASSWORD)
    kept = _doc(owner, "part")
    live = ProcessingClaim.objects.create(document=_doc(owner, "live", status=Document.Status.PROCESSING))
    originals = tmp_path / "originals" / "aa"
    originals.mkdir(parents=True)
    (tmp_path / kept.original_path).write_bytes(b"committed part")
    (originals / "orphan.pdf").write_bytes(b"part of a split that never committed")
    running, killed, unknown = (tmp_path / WORK_DIR / name for name in (str(live.token), str(uuid.uuid4()), "not-a-token"))
    for folder in (running, killed, unknown):
        folder.mkdir(parents=True)
        (folder / "input.pdf").write_bytes(b"x")
    (killed / SPLIT_JOURNAL).write_text(f"originals/aa/orphan.pdf\n{kept.original_path}\n")
    with override_settings(MEDIA_ROOT=tmp_path):
        # No waiting: the killed run's folder is minutes old at most, and it goes with its uncommitted split parts.
        assert remove_stale_work_dirs() == 1
        assert running.exists() and unknown.exists() and not killed.exists()
        assert not (originals / "orphan.pdf").exists() and (tmp_path / kept.original_path).exists()
        # Once the stall is detected (or the owner cancels) the claim goes, and the folder with it.
        live.delete()
        assert remove_stale_work_dirs() == 1 and not running.exists()


@pytest.mark.django_db
def test_stalled_detection_removes_the_killed_runs_folder_in_the_same_pass(tmp_path):
    from django.db.models.functions import Now

    from archive.tasks import reconcile_pending_documents

    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, status=Document.Status.PROCESSING, processing_started_at=timezone.now())
    claim = ProcessingClaim.objects.create(document=document)
    ProcessingClaim.objects.filter(pk=claim.pk).update(beat_at=Now() - timedelta(minutes=10))
    folder = tmp_path / WORK_DIR / str(claim.token)
    folder.mkdir(parents=True)
    (folder / "input.pdf").write_bytes(b"x")
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.tasks.process_document.delay"):
        reconcile_pending_documents()  # first sighting: only noted
        assert folder.exists()
        reconcile_pending_documents()  # declared gone, requeued, folder removed
    assert Document.objects.get(pk=document.pk).status == Document.Status.PENDING and not folder.exists()


def test_a_worker_start_removes_leftover_work_folders():
    from ripiano import celery

    with patch("archive.tasks.remove_stale_work_dirs") as cleanup:
        celery._remove_leftover_work_folders(sender=None)
    cleanup.assert_called_once_with()
    with patch("archive.tasks.remove_stale_work_dirs", side_effect=OSError("disk")):
        celery._remove_leftover_work_folders(sender=None)  # never stops the worker from starting


@pytest.mark.django_db
def test_a_run_that_lost_its_document_cannot_split_the_scan(tmp_path):
    from archive.test_barcodes import page, pdf

    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, status=Document.Status.PROCESSING)
    scan = tmp_path / "scan.pdf"
    scan.write_bytes(pdf(page("one"), page("two")))
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.tasks.process_document.delay"):
        assert _split(document, scan, [(0, 1), (1, 2)], journal=tmp_path / SPLIT_JOURNAL, token=uuid.uuid4()) is False
    assert Document.objects.count() == 1 and not (tmp_path / SPLIT_JOURNAL).exists()


@pytest.mark.django_db
def test_backup_copies_again_when_a_finished_pdf_is_replaced_midway_and_skips_a_vanished_file(tmp_path):
    media = _media(tmp_path)
    archive = media / "archive" / "ab" / "doc.pdf"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"first result")
    real_copy, state = shutil.copy2, {"replaced": False}

    def copy(source, destination, **kwargs):
        if source == archive and not state["replaced"]:
            state["replaced"] = True
            real_copy(source, destination, **kwargs)
            archive.write_bytes(b"reprocessed result")  # replaced right after it was read
            (destination).write_bytes(b"reprocessed result")
            return destination
        if str(source).endswith("example.pdf"):
            source.unlink()  # a rolled-back split removes its part while the backup runs
        return real_copy(source, destination, **kwargs)

    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=tmp_path / "backups"), \
            patch("archive.backup._database_command", side_effect=fake_database_command), patch("archive.backup.shutil.copy2", side_effect=copy):
        snapshot = create_snapshot()
    assert [entry["path"] for entry in verify_snapshot(snapshot, check_schema=False)["files"]] == ["archive/ab/doc.pdf"]
    assert (snapshot / "media/archive/ab/doc.pdf").read_bytes() == b"reprocessed result"


@pytest.mark.django_db
def test_restore_queues_documents_that_were_being_processed_and_ignores_leftover_work_files(tmp_path):
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, status=Document.Status.PROCESSING, processing_started_at=timezone.now())
    ready = _doc(owner, "done", status=Document.Status.READY)
    ProcessingClaim.objects.create(document=document)
    assert backup._requeue_interrupted_processing() == 1
    document.refresh_from_db()
    assert document.status == Document.Status.PENDING and document.processing_started_at is None
    assert not ProcessingClaim.objects.exists() and Document.objects.get(pk=ready.pk).status == Document.Status.READY

    media = _media(tmp_path)
    target = tmp_path / "restored"
    (target / WORK_DIR / "old").mkdir(parents=True)
    (target / WORK_DIR / "old" / "input.pdf").write_bytes(b"left by a killed worker")
    Document.objects.all().delete()
    User.objects.all().delete()
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=tmp_path / "backups"), \
            patch("archive.backup._database_command", side_effect=fake_database_command):
        snapshot = create_snapshot()
        with override_settings(MEDIA_ROOT=target), patch("archive.backup._requeue_interrupted_processing") as requeue:
            restore_snapshot(snapshot.name)
            requeue.assert_called_once_with()
            assert (target / "originals/ab/example.pdf").read_bytes() == b"original"
            (target / "stray.bin").write_bytes(b"?")
            with pytest.raises(BackupError, match="empty media volume"):
                restore_snapshot(snapshot.name)


# --- M1: an agent's change cannot make a workflow disclose the document ---------------------------------------------


def _agent(owner):
    return AgentGrant.objects.create(owner=owner, name="Tagger", token_hash="c" * 64, scopes=["documents:tag"],
                                     expires_at=timezone.now() + timedelta(days=30))


@pytest.mark.django_db
def test_a_workflow_started_by_an_agent_holds_back_sharing_webhook_and_email():
    from archive.api_language import run_detail_to_italian
    from archive.workflows import HELD_EMAIL, HELD_SHARE, HELD_WEBHOOK, run_for_document

    owner = User.objects.create_user("owner", password=PASSWORD)
    anna = User.objects.create_user("anna", password="secure-password-2")
    filed = Tag.objects.create(owner=owner, name="Filed")
    flow = Workflow.objects.create(owner=owner, name="Share invoices", trigger=Workflow.Trigger.UPDATED, webhook_url="https://hooks.example.test/in",
                                   email_to="partner@example.test", share_with=[{"kind": "person", "id": anna.pk, "level": "view"}])
    flow.add_tags.add(filed)
    by_agent, by_owner = _doc(owner, "agent"), _doc(owner, "owner")
    with patch("archive.tasks.send_workflow_notifications.delay") as notify:
        with pytest.MonkeyPatch.context() as immediate:
            immediate.setattr("django.db.transaction.on_commit", lambda func, **kwargs: func())
            run = run_for_document(by_agent, Workflow.Trigger.UPDATED, agent_grant=_agent(owner))[0]
            notify.assert_not_called()
            assert not DocumentAccess.objects.filter(document=by_agent).exists()
            # Actions that stay inside the archive still run, so the run is "applied" and says what it held back.
            assert DocumentTag.objects.filter(document=by_agent, tag=filed).exists()
            assert run.status == WorkflowRun.Status.APPLIED
            assert run.detail == f"added tag Filed, {HELD_SHARE}, {HELD_WEBHOOK}, {HELD_EMAIL}"
            assert run_detail_to_italian(run.detail) != run.detail and "agente" in run_detail_to_italian(run.detail)

            # The same workflow started by the owner's own change shares and notifies as before.
            run = run_for_document(by_owner, Workflow.Trigger.UPDATED)[0]
            assert DocumentAccess.objects.filter(document=by_owner, user=anna, level="view").exists()
            assert "shared with anna (view)" in run.detail and "queued webhook" in run.detail
            notify.assert_called_once_with(str(run.id))


@pytest.mark.django_db
def test_a_workflow_that_only_discloses_is_recorded_as_skipped_for_an_agent():
    from archive.workflows import HELD_SHARE, run_for_document

    owner = User.objects.create_user("owner", password=PASSWORD)
    anna = User.objects.create_user("anna", password="secure-password-2")
    Workflow.objects.create(owner=owner, name="Share", trigger=Workflow.Trigger.UPDATED, share_with=[{"kind": "person", "id": anna.pk, "level": "edit"}])
    document = _doc(owner)
    run = run_for_document(document, Workflow.Trigger.UPDATED, agent_grant=_agent(owner))[0]
    assert (run.status, run.detail) == (WorkflowRun.Status.SKIPPED, HELD_SHARE)
    assert not DocumentAccess.objects.exists()


# --- L1: weak passwords are refused wherever a password is set ------------------------------------------------------

WEAK = {
    "aaaaaaaaaaaa": "repeats the same few characters",
    "qwertyuiopas": "neighbouring keys",
    "abcdefghijkl": "neighbouring keys",
    "123456789012": "only digits",
    "password1234": "commonly used",
}


@pytest.mark.django_db
def test_setup_refuses_weak_passwords():
    with override_settings(RIPIANO_SETUP_KEY="known-setup-key"):
        client = Client()
        for password, reason in {**WEAK, "judge3judge3": "too close to the username", "Judge3-2026!": "too close to the username"}.items():
            response = send(client, "post", "/api/setup", {"username": "judge3", "password": password, "setup_key": "known-setup-key"})
            assert response.status_code == 400 and reason in response.json()["error"], password
        assert send(client, "post", "/api/setup", {"username": "judge3", "password": "short", "setup_key": "known-setup-key"}).json()["error"] == \
            "Username and a password of at least 12 characters are required"
        assert not User.objects.exists()
        italian = send(client, "post", "/api/setup", {"username": "judge3", "password": "aaaaaaaaaaaa", "setup_key": "known-setup-key"}, HTTP_ACCEPT_LANGUAGE="it")
        assert italian.json()["error"] == "Questa password ripete gli stessi pochi caratteri. Scegline una più difficile da indovinare"
        assert send(client, "post", "/api/setup", {"username": "judge3", "password": "long-enough-password", "setup_key": "known-setup-key"}).status_code == 201


@pytest.mark.django_db
def test_people_and_own_password_change_refuse_weak_passwords():
    admin = User.objects.create_superuser("admin", password=PASSWORD)
    anna = User.objects.create_user("anna", password="secure-password-2")
    client = client_for(admin)
    for password, reason in {**WEAK, "annaannaanna": "too close to the username"}.items():
        created = send(client, "post", "/api/people", {"username": "anna2", "password": password.replace("anna", "anna2"), "current_password": PASSWORD})
        assert created.status_code == 400 and reason in created.json()["error"], password
        reset = send(client, "patch", f"/api/people/{anna.pk}", {"password": password, "current_password": PASSWORD})
        assert reset.status_code == 400 and reason in reset.json()["error"], password
    for password, reason in {**WEAK, "adminadminadmin": "too close to the username"}.items():
        changed = send(client, "post", "/api/account/password", {"current_password": PASSWORD, "new_password": password})
        assert changed.status_code == 400 and reason in changed.json()["error"], password
    assert send(client, "post", "/api/account/password", {"current_password": PASSWORD, "new_password": "short"}).json()["error"] == \
        "Use a new password of at least 12 characters"
    assert admin.check_password(PASSWORD) and User.objects.get(pk=anna.pk).check_password("secure-password-2")
    # A long password that merely includes the username stays allowed.
    assert send(client, "post", "/api/account/password", {"current_password": PASSWORD, "new_password": "admin-likes-green-tea"}).json() == {"changed": True}


# --- L4/L5: a database outage answers JSON 503, never an HTML debug page --------------------------------------------


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_api_answers_json_503_when_the_database_is_down_even_in_debug():
    client = Client(raise_request_exception=False)
    with patch("archive.views.get_user_model", side_effect=database_down()):
        response = client.get("/api/session")
        italian = client.get("/api/session", HTTP_ACCEPT_LANGUAGE="it")
    assert response.status_code == 503 and response["Content-Type"] == "application/json" and response["Retry-After"] == "5"
    assert response.json() == {"error": "Ripiano can't reach its database right now; try again in a moment"}
    assert italian.json() == {"error": "Ripiano non riesce a raggiungere il suo database in questo momento; riprova tra poco"}
    # A failure outside the view (here: the session lookup of a signed-in request) is answered the same way.
    signed_in = Client(raise_request_exception=False)
    signed_in.force_login(User.objects.create_user("owner", password=PASSWORD))
    with patch("django.contrib.sessions.backends.db.SessionStore.load", side_effect=database_down("server closed the connection", "57P01")):
        assert signed_in.get("/api/documents").status_code == 503


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_any_other_api_failure_is_json_500_without_a_traceback():
    client = Client(raise_request_exception=False)
    with patch("archive.views.get_user_model", side_effect=RuntimeError("secret detail in a traceback")):
        response = client.get("/api/session")
    assert response.status_code == 500 and response["Content-Type"] == "application/json"
    assert "secret detail" not in response.content.decode() and "Traceback" not in response.content.decode()
    assert response.json()["error"].startswith("Ripiano ran into a problem")


def _mcp_post(headers):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}', "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/mcp", "raw_path": b"/mcp", "root_path": "", "scheme": "http", "http_version": "1.1",
             "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 1),
             "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"), (b"accept", b"application/json, text/event-stream"),
                         (b"authorization", b"Bearer rpa_some-agent-token"), *headers]}
    try:
        async_to_sync(mcp_server.app)(scope, receive, send)
    except OperationalError:
        pass  # the server logs it after answering
    return sent


@pytest.mark.django_db
def test_mcp_answers_json_503_when_the_database_is_down():
    with patch.object(AgentGrant.objects, "select_related", side_effect=database_down()):
        sent = _mcp_post([])
        italian = _mcp_post([(b"accept-language", b"it-IT,it;q=0.9")])
    assert [message["type"] for message in sent] == ["http.response.start", "http.response.body"]
    assert sent[0]["status"] == 503 and dict(sent[0]["headers"])[b"content-type"] == b"application/json"
    assert json.loads(sent[1]["body"]) == {"error": "Ripiano can't reach its database right now; try again in a moment"}
    assert json.loads(italian[1]["body"])["error"].startswith("Ripiano non riesce a raggiungere")
    # With the database back, the same request is an ordinary 401 for this unknown token.
    assert _mcp_post([])[0]["status"] == 401
