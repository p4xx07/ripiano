"""Round-9 judge findings: the MCP server survives a database restart and has a health check, interrupted documents
recover within minutes and can be retried or cancelled, /healthz reports the database and queue server, sign-in works
while the queue server is down, agents ended by Ripiano say why, and document edits from a stale copy are refused."""

import json
import time
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, override_settings
from django.utils import timezone

from archive import mcp_server, throttle
from archive.messages_it import EXACT
from archive.models import AgentGrant, Correspondent, Document, ProcessingClaim, Tag
from archive.tasks import PROCESSING_ERRORS, STALE_AFTER, _Heartbeat, process_document, processing_stalled, reconcile_pending_documents

User = get_user_model()
PASSWORD = "secure-password-1"


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def _doc(owner, title="Scan", **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path=f"originals/aa/{title}.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10, **values)


def _grant(owner, token_hash="a" * 64):
    return AgentGrant.objects.create(owner=owner, name="Mac", token_hash=token_hash, scopes=["documents:search"],
                                     expires_at=timezone.now() + timedelta(days=30))


# --- H1: the MCP server replaces a database connection broken by a PostgreSQL restart -----------------------------


def test_mcp_database_work_drops_broken_connections_before_and_after_each_call():
    broken = MagicMock(in_atomic_block=False)
    in_transaction = MagicMock(in_atomic_block=True)
    calls = []

    @mcp_server.db_call
    def work():
        calls.append(broken.close_if_unusable_or_obsolete.call_count)
        return "done"

    with patch.object(mcp_server.connections, "all", return_value=[broken, in_transaction]):
        assert async_to_sync(work)() == "done"
    # Checked before the ORM work (a connection broken while idle is replaced) and after it (as Django does per request).
    assert calls == [1] and broken.close_if_unusable_or_obsolete.call_count == 2
    in_transaction.close_if_unusable_or_obsolete.assert_not_called()


@pytest.mark.django_db
def test_every_mcp_entry_point_uses_the_connection_handling():
    owner = User.objects.create_user("owner", password=PASSWORD)
    _grant(owner)
    with patch.object(mcp_server, "release_stale_connections") as release:
        assert async_to_sync(mcp_server.GrantVerifier().verify_token)("rpa_unknown") is None
        with patch("archive.mcp_server._grant", return_value=None):
            async_to_sync(mcp_server._list_allowed)()
            async_to_sync(mcp_server._call)("search_documents", {})
    assert release.call_count == 6


@pytest.mark.skipif(connection.vendor != "postgresql", reason="a server-side disconnect needs PostgreSQL")
@pytest.mark.django_db(transaction=True)
def test_mcp_token_check_works_after_the_database_dropped_its_connection():
    import hashlib

    import psycopg

    owner = User.objects.create_user("owner", password=PASSWORD)
    token = "rpa_" + "x" * 40
    _grant(owner, hashlib.sha256(token.encode()).hexdigest())
    connection.ensure_connection()
    pid = connection.connection.info.backend_pid
    settings_dict = connection.settings_dict
    with psycopg.connect(host=settings_dict["HOST"], port=settings_dict["PORT"], dbname=settings_dict["NAME"],
                         user=settings_dict["USER"], password=settings_dict["PASSWORD"], autocommit=True) as admin:
        admin.execute("SELECT pg_terminate_backend(%s)", [pid])  # what a PostgreSQL restart does to every connection
    assert async_to_sync(mcp_server.GrantVerifier().verify_token)(token) is not None


def _asgi_get(app, path):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    async_to_sync(app)({"type": "http", "method": "GET", "path": path, "headers": [], "query_string": b""}, receive, send)
    return sent[0]["status"], json.loads(sent[1]["body"])


@pytest.mark.django_db
def test_mcp_health_endpoint_checks_the_database():
    with patch("archive.health.database_ok", return_value=True):
        assert _asgi_get(mcp_server.app, "/healthz") == (200, {"status": "ok", "database": "ok"})
    with patch("archive.health.database_ok", return_value=False):
        assert _asgi_get(mcp_server.app, "/healthz") == (503, {"status": "unavailable", "database": "down"})


# --- L4: /healthz reports the database and the queue server; /livez only the process --------------------------------


@pytest.fixture
def fresh_health():
    from archive import health

    health.forget()
    yield health
    health.forget()


@pytest.mark.django_db
def test_healthz_answers_503_while_the_database_or_the_broker_is_down(fresh_health):
    client = Client()
    with patch("archive.health.broker_ok", return_value=True):
        assert client.get("/healthz").json() == {"status": "ok", "database": "ok", "broker": "ok"}
        fresh_health.forget()
        with patch("archive.health.database_ok", return_value=False):
            down = client.get("/healthz")
            assert down.status_code == 503 and down.json() == {"status": "unavailable", "database": "down", "broker": "ok"}
    fresh_health.forget()
    with patch("archive.health.broker_ok", return_value=False):
        down = client.get("/healthz")
        assert down.status_code == 503 and down.json()["broker"] == "down"
        assert client.get("/livez").json() == {"status": "ok"}


@pytest.mark.django_db
def test_public_healthz_is_cheap_and_does_not_say_which_part_is_down(fresh_health):
    """Review L4: through the web container (no sign-in) only the status is told, and the checks run at most every few seconds."""
    client = Client()
    with patch("archive.health.broker_ok", return_value=False) as broker, patch("archive.health.database_ok", return_value=True) as database:
        for _ in range(5):
            public = client.get("/healthz", HTTP_X_RIPIANO_FORWARDED="1")
            assert public.status_code == 503 and public.json() == {"status": "unavailable"}
        assert client.get("/healthz").json() == {"status": "unavailable", "database": "ok", "broker": "down"}  # inside the stack
        assert broker.call_count == 1 and database.call_count == 1
    with patch("archive.health.broker_ok", return_value=True), patch("archive.health.database_ok", return_value=True), \
            patch("archive.health.CACHE_SECONDS", 0):
        assert client.get("/healthz", HTTP_X_RIPIANO_FORWARDED="1").json() == {"status": "ok"}


def test_the_web_container_forwards_livez_and_marks_healthz():
    """Review L3/L4: the upload reachability probe needs /livez; the public /healthz must be marked as forwarded."""
    from pathlib import Path

    conf = (Path(__file__).resolve().parents[3] / "apps/web/nginx.conf").read_text()
    health_block = conf.split("location = /healthz {")[1].split("}")[0]
    assert 'proxy_set_header X-Ripiano-Forwarded "1";' in health_block
    assert "location = /livez {" in conf


def test_mcp_health_check_does_not_wait_behind_agent_calls():
    """Review L9: the check has its own thread and a time limit; an unanswered query reads as "down", not a hang."""
    import threading

    import asyncio

    release = threading.Event()

    async def check():
        started = time.monotonic()
        answer = await mcp_server._database_ok()
        elapsed = time.monotonic() - started
        release.set()  # let the stuck query end so the test's event loop can close
        return answer, elapsed

    try:
        with patch("archive.health.database_ok", side_effect=lambda: release.wait(5) or True), patch.object(mcp_server, "HEALTH_TIMEOUT_SECONDS", 0.1):
            answer, elapsed = asyncio.run(check())
        assert answer is False and elapsed < 2
    finally:
        release.set()


@pytest.mark.django_db
def test_health_checks_report_real_failures():
    from archive import health

    assert health.database_ok() is True
    with override_settings(CELERY_BROKER_URL="redis://127.0.0.1:1/0"):
        assert health.broker_ok() is False
    with patch.object(connection, "cursor", side_effect=__import__("django.db", fromlist=["OperationalError"]).OperationalError("closed")):
        assert health.database_ok() is False
    # "connection already closed" is an InterfaceError, not a DatabaseError (review L9).
    with patch.object(connection, "cursor", side_effect=__import__("django.db", fromlist=["InterfaceError"]).InterfaceError("connection already closed")):
        assert health.database_ok() is False


# --- L5: sign-in keeps working while the cache (queue server) is down ------------------------------------------------


@pytest.mark.django_db
def test_sign_in_works_while_the_cache_is_unreachable(caplog):
    User.objects.create_user("owner", password=PASSWORD)
    throttle.forget_fallback()
    from django.core.cache import cache

    with patch.object(cache, "get", side_effect=ConnectionError("broker down")), \
            patch.object(cache, "add", side_effect=ConnectionError("broker down")):
        client = Client()
        wrong = client.post("/api/session", json.dumps({"username": "owner", "password": "wrong-password-x"}), content_type="application/json")
        assert wrong.status_code == 401
        right = client.post("/api/session", json.dumps({"username": "owner", "password": PASSWORD}), content_type="application/json")
        assert right.status_code == 200
    assert "Sign-in throttle unavailable" in caplog.text
    throttle.forget_fallback()


@pytest.mark.django_db
def test_sign_in_is_still_limited_per_process_while_the_cache_is_down():
    """Review L5: the cache fails after a successful read too (add/incr); failures are then counted in this process."""
    from django.core.cache import cache

    User.objects.create_user("owner", password=PASSWORD)
    throttle.forget_fallback()
    try:
        attempt = lambda password: Client().post("/api/session", json.dumps({"username": "owner", "password": password}), content_type="application/json")  # noqa: E731
        with patch.object(cache, "add", side_effect=TimeoutError("no answer")) as add, patch.object(cache, "incr", side_effect=TimeoutError("no answer")):
            statuses = [attempt("wrong-password-x").status_code for _ in range(throttle.LIMIT_PER_USERNAME)]
            assert statuses == [401] * throttle.LIMIT_PER_USERNAME
            assert attempt(PASSWORD).status_code == 429  # limited although the cache never counted anything
            assert add.call_count == 1  # the cache is left alone for a while instead of timing out on every attempt
        # A programming error is not mistaken for an outage.
        throttle.forget_fallback()
        with patch.object(cache, "get", side_effect=TypeError("wrong key type")), pytest.raises(TypeError):
            throttle.sign_in_blocked(("signin:u:x", "signin:a:y"))
    finally:
        throttle.forget_fallback()


# --- L3: an agent ended by a password change or a turned-off account says why --------------------------------------


@pytest.mark.django_db
def test_agents_ended_by_ripiano_carry_a_reason():
    owner = User.objects.create_superuser("owner", password=PASSWORD)
    member = User.objects.create_user("anna", password=PASSWORD)
    own = _grant(owner, "a" * 64)
    by_hand = _grant(owner, "b" * 64)
    client = client_for(owner)
    assert client.delete(f"/api/agents/{by_hand.id}").status_code == 200
    owner.set_password("another-secure-password-2")
    owner.save()
    client = client_for(owner)
    reasons = {item["id"]: item["revoked_reason"] for item in client.get("/api/agents").json()["grants"]}
    assert reasons == {str(own.id): "password_changed", str(by_hand.id): None}

    theirs = _grant(member, "c" * 64)
    from archive.people_views import _end_access

    _end_access(member)
    theirs.refresh_from_db()
    assert theirs.revoked_at and theirs.revoked_reason == "account_off"


# --- M1: a document whose worker died recovers within minutes, and the owner may retry or cancel it ---------------
# Round-9 review M1: each run holds a claim; only the run still holding it may save its result.


def _claim(document, age=timedelta(0), suspected=False):
    """As if a worker had claimed ``document`` and last reported ``age`` ago."""
    claim, _ = ProcessingClaim.objects.update_or_create(document=document, defaults={"suspected": suspected})
    ProcessingClaim.objects.filter(pk=claim.pk).update(beat_at=timezone.now() - age)
    return ProcessingClaim.objects.get(pk=claim.pk)


def _reconcile(passes=2):
    with patch("archive.tasks.process_document.delay") as queued:
        for _ in range(passes):
            reconcile_pending_documents()
    return queued


@pytest.mark.django_db
def test_a_processing_document_without_a_heartbeat_is_requeued_within_minutes():
    owner = User.objects.create_user("owner", password=PASSWORD)
    now = timezone.now()
    alive = _doc(owner, "alive", status=Document.Status.PROCESSING, processing_started_at=now - timedelta(minutes=30))
    _claim(alive, timedelta(seconds=20))
    dead = _doc(owner, "dead", status=Document.Status.PROCESSING, processing_started_at=now - timedelta(minutes=3), processing_failures=1)
    _claim(dead, STALE_AFTER + timedelta(seconds=5))
    # From before the update that introduced claims: processing, with nobody holding it.
    unclaimed = _doc(owner, "unclaimed", status=Document.Status.PROCESSING, processing_started_at=now - timedelta(minutes=3))
    queued = _reconcile()
    alive.refresh_from_db()
    dead.refresh_from_db()
    unclaimed.refresh_from_db()
    assert alive.status == Document.Status.PROCESSING  # a long OCR with a live worker is left alone
    assert dead.status == Document.Status.PENDING and unclaimed.status == Document.Status.PENDING
    # An interruption is not an OCR failure: the two are counted apart (review L6).
    assert (dead.processing_interruptions, dead.processing_failures) == (1, 1)
    assert not ProcessingClaim.objects.filter(document__in=[dead, unclaimed]).exists()
    assert {call.args[0] for call in queued.call_args_list} == {str(dead.id), str(unclaimed.id)}


@pytest.mark.django_db
def test_one_late_heartbeat_is_not_a_stopped_worker():
    """A clock jump or a database outage delays one heartbeat: the first scheduler pass only notes it (review M1)."""
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, status=Document.Status.PROCESSING, processing_started_at=timezone.now() - timedelta(minutes=20))
    claim = _claim(document, timedelta(minutes=5))
    queued = _reconcile(passes=1)
    document.refresh_from_db()
    assert document.status == Document.Status.PROCESSING and document.processing_interruptions == 0
    assert ProcessingClaim.objects.get(pk=document.pk).suspected
    queued.assert_not_called()
    # The worker is alive: its next heartbeat clears the note, and later passes leave the document alone.
    with patch("archive.tasks.HEARTBEAT_SECONDS", 0.05):
        _Heartbeat.beat(document.id, claim.token)
    after = ProcessingClaim.objects.get(pk=document.pk)
    assert not after.suspected and after.token == claim.token
    _reconcile(passes=3).assert_not_called()
    document.refresh_from_db()
    assert document.status == Document.Status.PROCESSING and document.processing_interruptions == 0


@pytest.mark.django_db
def test_a_heartbeat_dated_in_the_future_is_not_proof_of_life():
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, status=Document.Status.PROCESSING, processing_started_at=timezone.now())
    _claim(document, -timedelta(hours=4))  # the clock was set back after the worker's last report
    assert processing_stalled(document)
    assert client_for(owner).get("/api/jobs").json()["documents_waiting"]["items"][0]["stalled"] is True
    _reconcile()
    assert Document.objects.get(pk=document.pk).status == Document.Status.PENDING


@pytest.mark.django_db
def test_a_document_that_keeps_killing_its_worker_stops_after_three_tries():
    owner = User.objects.create_user("owner", password=PASSWORD)
    old = timezone.now() - timedelta(minutes=10)
    # Two earlier OCR failures do not count towards "interrupted" (review L6).
    patient = _doc(owner, "patient", status=Document.Status.PROCESSING, processing_started_at=old, processing_failures=2)
    document = _doc(owner, status=Document.Status.PROCESSING, processing_started_at=old, processing_interruptions=2)
    _claim(patient, timedelta(minutes=10))
    _claim(document, timedelta(minutes=10))
    queued = _reconcile()
    document.refresh_from_db()
    patient.refresh_from_db()
    assert document.status == Document.Status.FAILED and document.error == PROCESSING_ERRORS["interrupted"]
    assert patient.status == Document.Status.PENDING and (patient.processing_interruptions, patient.processing_failures) == (1, 2)
    assert [call.args[0] for call in queued.call_args_list] == [str(patient.id)]
    assert PROCESSING_ERRORS["interrupted"] in EXACT
    italian = Client(HTTP_ACCEPT_LANGUAGE="it")
    italian.force_login(owner)
    assert italian.get(f"/api/documents/{document.id}").json()["error"] == EXACT[PROCESSING_ERRORS["interrupted"]]
    # A person's Retry starts the count afresh.
    with patch("archive.tasks.process_document.delay"):
        assert client_for(owner).post(f"/api/documents/{document.id}/retry").status_code == 202
    document.refresh_from_db()
    assert document.status == Document.Status.PENDING and document.processing_interruptions == 0


@pytest.mark.django_db
def test_the_owner_can_retry_or_cancel_a_stalled_document_but_not_a_live_one():
    owner = User.objects.create_user("owner", password=PASSWORD)
    now = timezone.now()
    live = _doc(owner, "live", status=Document.Status.PROCESSING, processing_started_at=now)
    stalled = _doc(owner, "stalled", status=Document.Status.PROCESSING, processing_started_at=now - timedelta(minutes=5))
    other = _doc(owner, "other", status=Document.Status.PROCESSING, processing_started_at=now - timedelta(minutes=5))
    _claim(live)
    _claim(stalled, timedelta(minutes=5))
    _claim(other, timedelta(minutes=5))
    client = client_for(owner)
    items = {item["title"]: item for item in client.get("/api/jobs").json()["documents_waiting"]["items"]}
    assert (items["live"]["stalled"], items["live"]["can_cancel"], items["live"]["can_retry"]) == (False, False, False)
    assert (items["stalled"]["stalled"], items["stalled"]["can_cancel"], items["stalled"]["can_retry"]) == (True, True, True)

    assert client.post(f"/api/documents/{live.id}/retry").status_code == 409
    assert client.post(f"/api/documents/{live.id}/reprocess").status_code == 409
    assert client.post(f"/api/documents/{live.id}/cancel-processing").status_code == 409
    with patch("archive.tasks.process_document.delay") as queued:
        assert client.post(f"/api/documents/{stalled.id}/retry").status_code == 202
    queued.assert_called_once_with(str(stalled.id))
    assert Document.objects.get(pk=stalled.pk).status == Document.Status.PENDING
    cancelled = client.post(f"/api/documents/{other.id}/cancel-processing")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == Document.Status.FAILED
    # Both take the document away from the stopped run.
    assert list(ProcessingClaim.objects.values_list("document_id", flat=True)) == [live.id]


@pytest.mark.django_db(transaction=True)
def test_the_worker_heartbeat_is_refreshed_while_processing():
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, status=Document.Status.PROCESSING, processing_started_at=timezone.now() - timedelta(minutes=10))
    claim = _claim(document, timedelta(minutes=10), suspected=True)
    with patch("archive.tasks.HEARTBEAT_SECONDS", 0.05):
        with _Heartbeat(document.id, claim.token):
            time.sleep(0.4)
    after = ProcessingClaim.objects.get(pk=document.pk)
    assert after.beat_at > timezone.now() - timedelta(seconds=5) and not after.suspected
    assert not processing_stalled(document)
    # Another run's heartbeat (an older claim) refreshes nothing.
    _claim(document, timedelta(minutes=10))
    with patch("archive.tasks.HEARTBEAT_SECONDS", 0.05):
        with _Heartbeat(document.id, uuid.uuid4()):
            time.sleep(0.2)
    assert processing_stalled(document)


def _process_with(tmp_path, owner, during):
    """Process a one-page PDF; ``during`` runs while "OCR" is under way. Returns the document and the workflow mock."""
    from archive.ingestion import ingest_document
    from archive.test_barcodes import fake_ocr, page, pdf

    def run(args, **kwargs):
        during(Document.objects.get(owner=owner))
        return fake_ocr(args, **kwargs)

    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False), patch("archive.ingestion.process_document.delay"), \
            patch("archive.tasks.process_document.delay"), patch("archive.tasks.subprocess.run", side_effect=run), \
            patch("archive.workflows.run_for_document") as workflows, patch("archive.tasks.apply_rules") as rules:
        document = ingest_document(owner, SimpleUploadedFile("letter.pdf", pdf(page("A letter"))))
        process_document(str(document.id))
        return Document.objects.get(pk=document.pk), workflows, rules


@pytest.mark.django_db
def test_a_run_that_was_requeued_meanwhile_cannot_finish_over_the_new_attempt(tmp_path):
    """Review M1: the worker was alive after all. Its late result is discarded; the requeued attempt does the work once."""
    owner = User.objects.create_user("owner", password=PASSWORD)

    def declared_gone(document):
        _claim(document, timedelta(minutes=10))  # keeps the run's token; only the heartbeat looks old
        reconcile_pending_documents()
        reconcile_pending_documents()
        assert Document.objects.get(pk=document.pk).status == Document.Status.PENDING

    document, workflows, rules = _process_with(tmp_path, owner, declared_gone)
    assert document.status == Document.Status.PENDING and document.processed_at is None
    assert document.archive_path == "" and document.extracted_text == ""
    assert not list((tmp_path / "archive").rglob("*.pdf"))
    workflows.assert_not_called()
    rules.assert_not_called()
    # The requeued attempt then runs normally: filed and "added" workflows exactly once.
    document, workflows, rules = _process_again(tmp_path, document)
    assert document.status == Document.Status.READY and document.processing_interruptions == 0
    assert workflows.call_count == 1 and rules.call_count == 1
    assert not ProcessingClaim.objects.exists()


def _process_again(tmp_path, document):
    from archive.test_barcodes import fake_ocr

    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False), patch("archive.tasks.subprocess.run", side_effect=fake_ocr), \
            patch("archive.workflows.run_for_document") as workflows, patch("archive.tasks.apply_rules") as rules:
        process_document(str(document.id))
    return Document.objects.get(pk=document.pk), workflows, rules


@pytest.mark.django_db
def test_a_run_cancelled_meanwhile_cannot_mark_the_document_ready(tmp_path):
    from archive.job_views import CANCELLED_PROCESSING

    owner = User.objects.create_user("owner", password=PASSWORD)

    def cancelled(document):
        _claim(document, timedelta(minutes=10))
        assert client_for(owner).post(f"/api/documents/{document.id}/cancel-processing").status_code == 200

    document, workflows, rules = _process_with(tmp_path, owner, cancelled)
    assert document.status == Document.Status.FAILED and document.error == CANCELLED_PROCESSING
    assert document.processed_at is None and document.archive_path == ""
    workflows.assert_not_called()
    rules.assert_not_called()


@pytest.mark.django_db
def test_a_failing_run_that_lost_its_claim_does_not_record_its_failure(tmp_path):
    import subprocess

    from archive.ingestion import ingest_document
    from archive.test_barcodes import page, pdf

    owner = User.objects.create_user("owner", password=PASSWORD)

    def run(args, **kwargs):
        document = Document.objects.get(owner=owner)
        _claim(document, timedelta(minutes=10))
        with patch("archive.tasks.process_document.delay"):
            assert client_for(owner).post(f"/api/documents/{document.id}/retry").status_code == 202
        raise subprocess.CalledProcessError(1, args, stderr="boom")

    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_BARCODES=False), patch("archive.ingestion.process_document.delay"), \
            patch("archive.tasks.subprocess.run", side_effect=run):
        document = ingest_document(owner, SimpleUploadedFile("letter.pdf", pdf(page("A letter"))))
        process_document(str(document.id))
    document.refresh_from_db()
    assert document.status == Document.Status.PENDING and document.error == "" and document.processing_failures == 0


@pytest.mark.django_db
def test_work_directories_and_uncommitted_split_parts_of_killed_runs_are_removed(tmp_path):
    """Review L7: a killed run leaves its work directory and, mid-split, part files that belong to no document."""
    import os

    from archive.tasks import SPLIT_JOURNAL, _note, remove_stale_work_dirs

    owner = User.objects.create_user("owner", password=PASSWORD)
    kept = _doc(owner, "part")
    originals = tmp_path / "originals" / "aa"
    originals.mkdir(parents=True)
    (tmp_path / kept.original_path).write_bytes(b"committed part")
    orphan = originals / "orphan.pdf"
    orphan.write_bytes(b"part of a split that never committed")
    outside = tmp_path / "outside.txt"
    outside.write_text("not an original")
    killed, legacy, running = tmp_path / "work-killed", tmp_path / "tmpab12cd_x", tmp_path / "work-running"
    for folder in (killed, legacy, running):
        folder.mkdir()
        (folder / "input.pdf").write_bytes(b"x")
    (killed / SPLIT_JOURNAL).write_text(f"originals/aa/orphan.pdf\n{kept.original_path}\n../outside.txt\noutside.txt\n")
    long_ago = time.time() - 3 * 3600
    for folder in (killed, legacy, tmp_path / "originals"):
        os.utime(folder, (long_ago, long_ago))
    with override_settings(MEDIA_ROOT=tmp_path):
        assert remove_stale_work_dirs() == 2
    assert not killed.exists() and not legacy.exists()
    assert running.exists() and (tmp_path / "originals").exists()  # a current run and the archive itself are untouched
    assert not orphan.exists() and (tmp_path / kept.original_path).exists() and outside.exists()

    # A rerun says the same thing only once.
    _note(kept, "This scan has an ASN barcode, but only the first 50 pages are checked, so its archive number was not assigned.")
    _note(kept, "This scan has an ASN barcode, but only the first 50 pages are checked, so its archive number was not assigned.")
    assert kept.notes.count() == 1


@pytest.mark.django_db
def test_a_requeued_split_source_is_not_split_again(tmp_path, django_capture_on_commit_callbacks):
    """The worker died after the split committed: the requeued scan is processed again but gets no new parts."""
    from archive.ingestion import ingest_document
    from archive.test_barcodes import HAS_ZBAR, page, pdf, process

    if not HAS_ZBAR:
        pytest.skip("install the zbar library to read barcodes")
    owner = User.objects.create_user("owner", password=PASSWORD)
    scan = pdf(page("Letter one"), page(code="PATCHT"), page("Bill page 1"))
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"), \
            patch("archive.tasks.process_document.delay"):
        source = ingest_document(owner, SimpleUploadedFile("batch.pdf", scan))
        with django_capture_on_commit_callbacks(execute=True):
            process(str(source.id))
        assert Document.objects.filter(split_parent=source).count() == 2
        # As if the worker had been killed right after the split's transaction, before the scan was marked processed.
        old = timezone.now() - timedelta(minutes=10)
        Document.objects.filter(pk=source.pk).update(status=Document.Status.PROCESSING, processed_at=None, processing_started_at=old)
        _claim(source, timedelta(minutes=10))
        reconcile_pending_documents()
        reconcile_pending_documents()
        assert Document.objects.get(pk=source.pk).status == Document.Status.PENDING
        with django_capture_on_commit_callbacks(execute=True):
            process(str(source.id))
    source.refresh_from_db()
    assert source.status == Document.Status.READY and source.is_split_source
    assert Document.objects.filter(split_parent=source).count() == 2


# --- Judge 2 M1: a save from a stale copy cannot silently overwrite a newer change ---------------------------------


def _patch(client, document, body, **headers):
    return client.patch(f"/api/documents/{document.id}", json.dumps(body), content_type="application/json", **headers)


@pytest.mark.django_db
def test_a_stale_edit_is_refused_with_the_current_document_and_what_changed():
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, "Original", status=Document.Status.READY)
    tab1, tab2 = client_for(owner), client_for(owner)
    version = tab1.get(f"/api/documents/{document.id}").json()["edit_version"]
    assert tab2.get(f"/api/documents/{document.id}").json()["edit_version"] == version

    saved = _patch(tab1, document, {"title": "A", "base_version": version})
    assert saved.status_code == 200 and saved.json()["title"] == "A"
    assert saved.json()["edit_version"] != version and saved["ETag"] == f'"{saved.json()["edit_version"]}"'

    stale = _patch(tab2, document, {"title": "B", "base_version": version})
    assert stale.status_code == 409
    body = stale.json()
    assert body["code"] == "edit_conflict" and body["conflicting_fields"] == ["title"] and body["changed_fields"] == ["title"]
    assert body["document"]["title"] == "A" and body["document"]["edit_version"] == saved.json()["edit_version"]
    assert Document.objects.get(pk=document.pk).title == "A"

    # The same through If-Match, and in Italian.
    italian = client_for(owner)
    refused = _patch(italian, document, {"title": "B"}, HTTP_IF_MATCH=f'"{version}"', HTTP_ACCEPT_LANGUAGE="it")
    assert refused.status_code == 409 and refused.json()["error"] == EXACT[body["error"]]

    # A change to a detail nobody else touched still merges; no token keeps the old behaviour (agents, scripts).
    merged = _patch(tab2, document, {"action_note": "Pay by Friday", "base_version": version})
    assert merged.status_code == 200 and merged.json()["title"] == "A" and merged.json()["action_note"] == "Pay by Friday"
    assert _patch(tab2, document, {"title": "B"}).json()["title"] == "B"
    assert _patch(tab2, document, {"title": "C", "base_version": "nonsense"}).status_code == 400


@pytest.mark.django_db
def test_stale_tags_and_filing_conflict_and_shared_editors_get_their_own_token():
    from archive.models import DocumentAccess

    owner = User.objects.create_user("owner", password=PASSWORD)
    anna = User.objects.create_user("anna", password=PASSWORD)
    bills = Tag.objects.create(owner=owner, name="Bills")
    acme = Correspondent.objects.create(owner=owner, name="Acme")
    document = _doc(owner, "Shared", status=Document.Status.READY)
    client = client_for(owner)
    version = client.get(f"/api/documents/{document.id}").json()["edit_version"]
    assert _patch(client, document, {"add_tag_id": str(bills.id)}).status_code == 200
    assert _patch(client, document, {"correspondent_id": str(acme.id)}).status_code == 200
    stale = _patch(client, document, {"tags": [], "correspondent_id": None, "base_version": version})
    assert stale.status_code == 409 and stale.json()["conflicting_fields"] == ["correspondent", "tags"]

    DocumentAccess.objects.create(document=document, user=anna, level="edit")
    shared = client_for(anna)
    shared_version = shared.get(f"/api/documents/{document.id}").json()["edit_version"]
    # Owner-only details (here the ASN) are not part of a shared editor's token: no conflict they could not see.
    assert _patch(client, document, {"asn": 7}).status_code == 200
    assert _patch(shared, document, {"title": "Anna's", "base_version": shared_version}).status_code == 200
    assert _patch(shared, document, {"title": "Again", "base_version": shared_version}).status_code == 409


@pytest.mark.django_db
def test_a_shared_editors_stale_save_keeps_the_owners_newer_changes():
    """Review M2/L10: Anna shares with Luca for editing; Luca's dialog was opened before Anna renamed the document."""
    from archive.models import DocumentAccess

    anna = User.objects.create_user("anna", password=PASSWORD)
    luca = User.objects.create_user("luca", password=PASSWORD)
    document = _doc(anna, "Bolletta gas", status=Document.Status.READY)
    DocumentAccess.objects.create(document=document, user=luca, level="edit")
    owner, editor = client_for(anna), client_for(luca)
    opened = editor.get(f"/api/documents/{document.id}").json()["edit_version"]
    assert _patch(owner, document, {"title": "Bolletta gas marzo", "action_status": "open", "action_due_date": "2026-12-01"}).status_code == 200

    # What the dialog sends now: only what Luca changed, with the version he opened. Anna's changes stay.
    saved = _patch(editor, document, {"action_note": "Pagata da Luca", "base_version": opened})
    assert saved.status_code == 200
    document.refresh_from_db()
    assert (document.title, str(document.action_due_date), document.action_note) == ("Bolletta gas marzo", "2026-12-01", "Pagata da Luca")
    assert document.document_date_origin != Document.FilingOrigin.MANUAL  # a date nobody set is not marked as set by hand

    # A detail both changed is refused, and the answer shows Luca the document as he may see it.
    refused = _patch(editor, document, {"title": "Gas", "base_version": opened})
    assert refused.status_code == 409 and refused.json()["code"] == "edit_conflict"
    assert refused.json()["conflicting_fields"] == ["title"] and refused.json()["document"]["title"] == "Bolletta gas marzo"
    assert refused.json()["document"]["access"] == "edit"
    assert Document.objects.get(pk=document.pk).title == "Bolletta gas marzo"


@pytest.mark.django_db
def test_if_match_accepts_weak_tags_and_ignores_a_star():
    """Review L10: `W/"…"` is compared like a strong tag; `*` means "whatever is there" and never conflicts."""
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, "Original", status=Document.Status.READY)
    client = client_for(owner)
    version = client.get(f"/api/documents/{document.id}").json()["edit_version"]
    assert _patch(client, document, {"title": "A"}).status_code == 200
    assert _patch(client, document, {"title": "B"}, HTTP_IF_MATCH=f'W/"{version}"').status_code == 409
    assert _patch(client, document, {"title": "B"}, HTTP_IF_MATCH="*").status_code == 200
    current = client.get(f"/api/documents/{document.id}").json()["edit_version"]
    assert _patch(client, document, {"title": "C"}, HTTP_IF_MATCH=f'W/"{current}"').status_code == 200
    assert _patch(client, document, {"title": "D"}, HTTP_IF_MATCH='"nonsense"').status_code == 400
