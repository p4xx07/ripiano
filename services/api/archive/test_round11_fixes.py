"""Round-11 judge findings (API): the owner is told when no OCR worker is running (judge 2, M1), waiting documents are
not queued again every minute (judge 2, M2), and the Overview and Background jobs count and describe waiting documents
the same way (judge 3, L3 and L7)."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive import backup, processing_status
from archive.models import Document, ProcessingClaim, WorkerHeartbeat
from archive.processing_status import WAITING_GRACE, WORKER_STALE_AFTER, record_worker_beat, worker_state
from archive.tasks import LOST_AFTER, PASSED_MARGIN, STALE_AFTER, process_document, queue_document, reconcile_pending_documents

User = get_user_model()
PASSWORD = "secure-password-1"


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def _doc(owner, title="Scan", age=timedelta(0), **values):
    document = Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path=f"originals/aa/{title}.pdf",
                                       original_mime="application/pdf", original_sha256="0" * 64, original_size=10, **values)
    if age:
        Document.objects.filter(pk=document.pk).update(created_at=timezone.now() - age)
    return Document.objects.get(pk=document.pk)


class FakeBroker:
    """The OCR queue as a list: what was sent and is still waiting, as the scheduler sees it."""

    def __init__(self, reachable=True):
        self.messages = []
        self.reachable = reachable

    def delay(self, document_id):
        if not self.reachable:
            raise ConnectionError("Queue server unavailable")
        self.messages.append(document_id)

    def depths(self):
        return {"celery": len(self.messages), "maintenance": 0} if self.reachable else None

    def run(self, passes=1):
        with patch("archive.tasks.process_document.delay", side_effect=self.delay), \
                patch("archive.processing_status.queue_depths", side_effect=self.depths):
            for _ in range(passes):
                reconcile_pending_documents()


def _age_queue_marks(by):
    Document.objects.filter(queued_at__isnull=False).update(queued_at=timezone.now() - by)


def _beat(queue="celery", age=timedelta(0)):
    record_worker_beat([queue], "worker@test")
    WorkerHeartbeat.objects.filter(queue=queue).update(beat_at=timezone.now() - age)


# --- M2: one message per waiting document, however long the worker is stopped ----------------------------------------


@pytest.mark.django_db
def test_waiting_documents_are_sent_once_while_the_worker_is_stopped():
    owner = User.objects.create_user("owner", password=PASSWORD)
    documents = [_doc(owner, f"scan-{n}") for n in range(5)]
    broker = FakeBroker()
    broker.run()
    assert sorted(broker.messages) == sorted(str(d.id) for d in documents)
    # Six minutes, and then hours, with nobody consuming the queue: nothing is added.
    for minutes in (1, 2, 6, 60, 600):
        _age_queue_marks(timedelta(minutes=minutes))
        broker.run()
    assert len(broker.messages) == 5
    assert all(Document.objects.get(pk=d.pk).queued_at for d in documents)


@pytest.mark.django_db
def test_an_upload_marks_its_document_as_queued_so_the_scheduler_does_not_send_it_again():
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner)
    broker = FakeBroker()
    with patch("archive.tasks.process_document.delay", side_effect=broker.delay):
        queue_document(document.id)
    assert Document.objects.get(pk=document.pk).queued_at is not None
    broker.run(passes=3)
    assert broker.messages == [str(document.id)]


@pytest.mark.django_db
def test_documents_the_queue_server_lost_are_sent_again_once():
    owner = User.objects.create_user("owner", password=PASSWORD)
    documents = [_doc(owner, f"scan-{n}") for n in range(3)]
    broker = FakeBroker()
    broker.run()
    broker.messages.clear()  # The queue server's data was reset.
    # Not right away: a worker may be about to take a message that just left the queue.
    _age_queue_marks(LOST_AFTER - timedelta(minutes=1))
    broker.run()
    assert broker.messages == []
    _age_queue_marks(LOST_AFTER + timedelta(seconds=10))
    broker.run(passes=3)
    assert sorted(broker.messages) == sorted(str(d.id) for d in documents)


@pytest.mark.django_db
def test_lost_documents_are_not_sent_again_while_the_queue_still_holds_messages():
    owner = User.objects.create_user("owner", password=PASSWORD)
    lost = _doc(owner, "lost")
    broker = FakeBroker()
    broker.run()
    broker.messages[:] = ["another-document"]  # A large import is still being worked through.
    _age_queue_marks(timedelta(hours=3))
    broker.run(passes=3)
    assert broker.messages == ["another-document"]
    broker.messages.clear()
    broker.run()
    assert broker.messages == [str(lost.id)]


@pytest.mark.django_db
def test_a_lost_message_the_worker_has_passed_is_sent_again_while_the_queue_is_busy():
    """Round-11 review, L1: one lost message must not wait hours for a large import to drain."""
    owner = User.objects.create_user("owner", password=PASSWORD)
    lost = _doc(owner, "lost")
    broker = FakeBroker()
    broker.run()
    broker.messages.clear()  # Its claim failed during a short database outage: the message is gone.
    # A large import added after it: queued behind it, still mostly waiting.
    later = [_doc(owner, f"import-{n}") for n in range(3)]
    broker.run()
    assert broker.messages == [str(d.id) for d in later]
    Document.objects.filter(pk=lost.pk).update(queued_at=timezone.now() - LOST_AFTER - timedelta(minutes=1))
    broker.run()
    assert str(lost.id) not in broker.messages  # Nothing started since: it may simply be next in line.
    # The worker starts the first import document, but only just: it may still be about to claim the lost one.
    Document.objects.filter(pk=later[0].pk).update(status=Document.Status.READY, processing_started_at=timezone.now())
    broker.messages.pop(0)
    broker.run()
    assert str(lost.id) not in broker.messages
    # A minute later the worker has evidently passed it: sent again once, although the queue is not empty.
    Document.objects.filter(pk=later[0].pk).update(processing_started_at=timezone.now() - PASSED_MARGIN - timedelta(seconds=5))
    broker.run(passes=3)
    assert broker.messages.count(str(lost.id)) == 1 and len(broker.messages) == 3
    assert Document.objects.get(pk=lost.pk).queued_at is not None


@pytest.mark.django_db
def test_documents_queued_before_the_one_being_worked_on_are_not_sent_again():
    """Waiting behind a document the worker took is normal, and a stopped worker passes nobody: no queue flood."""
    owner = User.objects.create_user("owner", password=PASSWORD)
    # Added before the waiting documents, started half an hour ago (a slow scan), or ten hours ago (then the worker stopped).
    earlier = _doc(owner, "earlier", status=Document.Status.READY, age=timedelta(hours=11),
                   processing_started_at=timezone.now() - timedelta(minutes=30))
    waiting = [_doc(owner, f"scan-{n}") for n in range(4)]
    broker = FakeBroker()
    broker.run()
    broker.messages.insert(0, "another-document")
    for hours in (1, 3, 10):
        Document.objects.filter(pk__in=[d.pk for d in waiting]).update(created_at=timezone.now() - timedelta(hours=hours, minutes=1),
                                                                      queued_at=timezone.now() - timedelta(hours=hours))
        broker.run(passes=2)
        Document.objects.filter(pk=earlier.pk).update(processing_started_at=timezone.now() - timedelta(hours=10, minutes=30))
    assert sorted(broker.messages) == sorted(["another-document"] + [str(d.id) for d in waiting])


@pytest.mark.django_db
def test_documents_are_sent_when_the_queue_server_returns():
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner)
    broker = FakeBroker(reachable=False)
    broker.run(passes=3)
    assert Document.objects.get(pk=document.pk).queued_at is None
    broker.reachable = True
    broker.run(passes=2)
    assert broker.messages == [str(document.id)]


@pytest.mark.django_db
def test_a_stopped_run_is_still_requeued_within_minutes_and_sent_once():
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, status=Document.Status.PROCESSING, processing_started_at=timezone.now() - timedelta(minutes=5),
                    queued_at=timezone.now() - timedelta(minutes=6))
    ProcessingClaim.objects.create(document=document)
    ProcessingClaim.objects.filter(document=document).update(beat_at=timezone.now() - STALE_AFTER - timedelta(seconds=5))
    broker = FakeBroker()
    broker.messages.append("waiting-behind-it")  # Not empty: a stalled document is sent anyway.
    broker.run(passes=2)
    document.refresh_from_db()
    assert document.status == Document.Status.PENDING and document.queued_at is not None
    assert broker.messages == ["waiting-behind-it", str(document.id)]
    broker.run(passes=3)
    assert broker.messages.count(str(document.id)) == 1


@pytest.mark.django_db
def test_a_worker_taking_a_document_clears_its_queue_mark_and_only_pending_documents_are_marked():
    owner = User.objects.create_user("owner", password=PASSWORD)
    document = _doc(owner, queued_at=timezone.now())
    with patch("archive.tasks._process_claimed"):
        process_document(str(document.id))
    document.refresh_from_db()
    assert document.status == Document.Status.PROCESSING and document.queued_at is None
    with patch("archive.tasks.process_document.delay"):
        queue_document(document.id)  # The worker took it before the sender noted it.
    assert Document.objects.get(pk=document.pk).queued_at is None


@pytest.mark.django_db
def test_retry_and_restore_send_waiting_documents_again():
    owner = User.objects.create_user("owner", password=PASSWORD)
    failed = _doc(owner, "failed", status=Document.Status.FAILED, queued_at=timezone.now() - timedelta(hours=1))
    with patch("archive.tasks.process_document.delay", side_effect=ConnectionError("down")):
        assert client_for(owner).post(f"/api/documents/{failed.id}/retry").status_code == 202
    failed.refresh_from_db()
    assert failed.status == Document.Status.PENDING and failed.queued_at is None  # Not in the queue: sent next minute.

    waiting = _doc(owner, "waiting", queued_at=timezone.now())
    interrupted = _doc(owner, "interrupted", status=Document.Status.PROCESSING, processing_started_at=timezone.now())
    assert backup._requeue_interrupted_processing() == 1
    assert set(Document.objects.filter(status=Document.Status.PENDING, queued_at__isnull=True).values_list("title", flat=True)) == {
        "failed", "waiting", "interrupted"}
    broker = FakeBroker()
    broker.run(passes=2)
    assert sorted(broker.messages) == sorted(str(d.id) for d in (failed, waiting, interrupted))


# --- M1: the owner is told when no OCR worker is running ---------------------------------------------------------------


@pytest.mark.django_db
def test_worker_heartbeat_is_judged_by_the_database_clock(tmp_path):
    assert worker_state() == {"running": False, "last_seen": None}
    with patch.object(processing_status, "ALIVE_FILE", tmp_path / "alive"):
        beat = processing_status.WorkerBeat(["celery", "maintenance"], "worker@nas")
        beat.beat_once()
        beat.beat_once()
        assert (tmp_path / "alive").exists()
    assert WorkerHeartbeat.objects.count() == 2
    assert worker_state()["running"] and worker_state("maintenance")["running"]
    WorkerHeartbeat.objects.filter(queue="celery").update(beat_at=timezone.now() - WORKER_STALE_AFTER - timedelta(seconds=5))
    state = worker_state()
    assert state["running"] is False and state["last_seen"]
    # A beat far in the future (the clock was set back) is not proof of life either.
    WorkerHeartbeat.objects.filter(queue="celery").update(beat_at=timezone.now() + timedelta(hours=1))
    assert worker_state()["running"] is False


def test_each_worker_reports_for_the_queues_it_consumes():
    from ripiano.celery import _start_worker_heartbeat

    sender = SimpleNamespace(hostname="celery@worker", task_consumer=SimpleNamespace(queues=[SimpleNamespace(name="celery")]))
    with patch("archive.processing_status.WorkerBeat") as beat:
        _start_worker_heartbeat(sender=sender)
    beat.assert_called_once_with(["celery"], "celery@worker")
    beat.return_value.start.assert_called_once_with()


@pytest.mark.django_db
def test_background_jobs_and_overview_say_documents_wait_because_no_worker_is_running():
    owner = User.objects.create_user("owner", password=PASSWORD, is_superuser=True)
    old = _doc(owner, "old", age=WAITING_GRACE + timedelta(minutes=3), queued_at=timezone.now() - timedelta(minutes=5))
    client = client_for(owner)

    jobs = client.get("/api/jobs").json()
    assert jobs["processing"]["problem"] == "worker_not_running"
    assert jobs["processing"]["worker"] == {"running": False, "last_seen": None}
    assert jobs["processing"]["waiting_since"] and jobs["processing"]["pending"] == 1
    assert jobs["documents_waiting"]["items"][0]["state"] == "waiting_for_worker"
    with patch("archive.stats_views.queue_depths", return_value={"celery": 1, "maintenance": 0}):
        overview = client.get("/api/overview").json()
    assert overview["health"]["processing"] == jobs["processing"]
    assert overview["health"]["maintenance_worker"] == {"running": False, "last_seen": None}

    _beat(age=timedelta(minutes=10))  # It stopped ten minutes ago.
    jobs = client.get("/api/jobs").json()
    assert jobs["processing"]["problem"] == "worker_not_running" and jobs["processing"]["worker"]["last_seen"]

    _beat()
    jobs = client.get("/api/jobs").json()
    assert jobs["processing"]["problem"] is None and jobs["processing"]["worker"]["running"] is True
    item = jobs["documents_waiting"]["items"][0]
    assert (item["id"], item["state"]) == (str(old.id), "queued")  # still waiting; the worker just has not reached it
    old.refresh_from_db()
    assert old.status == Document.Status.PENDING and old.queued_at is not None


@pytest.mark.django_db
def test_a_document_just_uploaded_is_not_reported_as_a_problem_in_the_header_or_its_row():
    """Round-11 review, L7: the row waits out the same grace as the header, so they never disagree."""
    owner = User.objects.create_user("owner", password=PASSWORD)
    new = _doc(owner, "new", queued_at=timezone.now())
    unsent = _doc(owner, "unsent")  # A Retry the queue server has not taken yet, a second ago.
    client = client_for(owner)
    jobs = client.get("/api/jobs").json()
    assert jobs["processing"]["problem"] is None
    assert {item["title"]: item["state"] for item in jobs["documents_waiting"]["items"]} == {"new": "queued", "unsent": "queued"}

    Document.objects.filter(pk=new.pk).update(queued_at=timezone.now() - WAITING_GRACE - timedelta(seconds=5))
    jobs = client.get("/api/jobs").json()
    assert jobs["processing"]["problem"] == "worker_not_running"
    assert {item["title"]: item["state"] for item in jobs["documents_waiting"]["items"]} == {"new": "waiting_for_worker", "unsent": "queued"}

    Document.objects.filter(pk=unsent.pk).update(created_at=timezone.now() - WAITING_GRACE - timedelta(seconds=5))
    jobs = client.get("/api/jobs").json()
    assert jobs["processing"]["problem"] == "queue_unavailable"
    assert {item["title"]: item["state"] for item in jobs["documents_waiting"]["items"]} == {"new": "waiting_for_worker", "unsent": "waiting_for_queue"}


@pytest.mark.django_db
def test_the_grace_is_measured_with_the_database_clock():
    """Round-11 review, L6: a container clock ahead of the database must not raise an alarm for a fresh document."""
    owner = User.objects.create_user("owner", password=PASSWORD)
    _doc(owner, "new", queued_at=timezone.now())
    ahead = timezone.now() + WAITING_GRACE + timedelta(minutes=5)
    with patch("django.utils.timezone.now", return_value=ahead):
        summary = processing_status.processing_summary(Document.objects.filter(owner=owner))
    assert summary["problem"] is None and summary["pending"] == 1


@pytest.mark.django_db
def test_documents_the_queue_server_did_not_take_are_reported_as_waiting_for_it():
    owner = User.objects.create_user("owner", password=PASSWORD)
    _beat()
    _doc(owner, "unsent", age=WAITING_GRACE + timedelta(minutes=1))
    jobs = client_for(owner).get("/api/jobs").json()
    assert jobs["processing"]["problem"] == "queue_unavailable"
    assert jobs["documents_waiting"]["items"][0]["state"] == "waiting_for_queue"


# --- L3 / L7: the same counts everywhere, and "waiting" is not "processing" ---------------------------------------------


@pytest.mark.django_db
def test_overview_and_background_jobs_count_waiting_documents_the_same_way():
    owner = User.objects.create_user("owner", password=PASSWORD)
    _beat()
    now = timezone.now()
    source = _doc(owner, "batch", status=Document.Status.PROCESSING, processing_started_at=now, is_split_source=True)
    ProcessingClaim.objects.create(document=source)
    part = _doc(owner, "part", status=Document.Status.PROCESSING, processing_started_at=now)
    ProcessingClaim.objects.create(document=part)
    _doc(owner, "next part", queued_at=now)
    _doc(owner, "trashed", trashed_at=now)
    client = client_for(owner)
    jobs = client.get("/api/jobs").json()
    overview = client.get("/api/overview").json()
    assert jobs["documents_waiting"]["total"] == overview["documents"]["waiting"] == 2
    assert (overview["documents"]["pending"], overview["documents"]["processing"]) == (1, 1)
    assert (jobs["processing"]["pending"], jobs["processing"]["processing"]) == (1, 1)
    assert {item["title"]: item["state"] for item in jobs["documents_waiting"]["items"]} == {"part": "processing", "next part": "queued"}


def test_only_text_recognition_uses_the_ocr_queue():
    """Every other task runs on the maintenance worker, so the OCR queue count is the number of documents sent to it."""
    from django.conf import settings

    import archive.tasks  # noqa: F401 - registers every task
    from ripiano.celery import app

    registered = {name for name in app.tasks if name.startswith("archive.tasks.")}
    scheduled = {entry["task"] for entry in app.conf.beat_schedule.values()}
    assert "archive.tasks.process_document" in registered and scheduled <= registered and len(registered) > 20
    assert {task for task in registered if settings.CELERY_TASK_ROUTES.get(task, {}).get("queue") != "maintenance"} == {
        "archive.tasks.process_document"}


@pytest.mark.django_db
def test_every_way_a_document_is_queued_marks_it(tmp_path, django_capture_on_commit_callbacks):
    """Upload, Retry, new version, split and mail import all go through queue_document (round-11 review, L9)."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.test import override_settings

    from archive import mail
    from archive.models import MailAccount, MailRule
    from archive.test_mail import message
    from archive.test_versions import pdf

    owner = User.objects.create_user("owner", password=PASSWORD)
    client = client_for(owner)
    sent = []

    def marked(document_id):
        return Document.objects.filter(pk=document_id, status=Document.Status.PENDING, queued_at__isnull=False).exists()

    def reset(document_id):
        Document.objects.filter(pk=document_id).update(status=Document.Status.READY, queued_at=None)

    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.tasks.process_document.delay", side_effect=sent.append):
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post("/api/documents", {"document": SimpleUploadedFile("upload.pdf", pdf(300, 400, 500))})
        assert response.status_code in (200, 201, 202), response.content
        uploaded = Document.objects.get(owner=owner, original_name="upload.pdf")
        assert sent == [str(uploaded.id)] and marked(uploaded.id), "upload"

        Document.objects.filter(pk=uploaded.pk).update(status=Document.Status.FAILED, queued_at=None)
        with django_capture_on_commit_callbacks(execute=True):
            assert client.post(f"/api/documents/{uploaded.id}/retry").status_code == 202
        assert sent[-1] == str(uploaded.id) and marked(uploaded.id), "retry"

        reset(uploaded.id)
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(f"/api/documents/{uploaded.id}/versions", {"file": SimpleUploadedFile("v2.pdf", pdf(310, 320, 330))})
        assert response.status_code == 202
        assert sent[-1] == str(uploaded.id) and marked(uploaded.id), "new version"

        reset(uploaded.id)
        before = len(sent)
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(f"/api/documents/{uploaded.id}/split", {"groups": [[0], [2, 1]]}, content_type="application/json")
        assert response.status_code == 201
        parts = [item["id"] for item in response.json()["documents"]]
        assert sorted(sent[before:]) == sorted(parts) and all(marked(part) for part in parts), "split"

        account = MailAccount.objects.create(owner=owner, name="Home", host="imap.example.test", port=993, username="me@example.test",
                                             secret=mail.encrypt_secret("app-password"))
        rule = MailRule.objects.create(owner=owner, account=account, name="Bills")
        before = len(sent)
        with django_capture_on_commit_callbacks(execute=True):
            assert mail.import_message(rule, message(message_id="<bill@x>"), uid_validity=1, uid=1, folder="INBOX") == 1
        imported = Document.objects.get(owner=owner, source=Document.Source.EMAIL)
        assert sent[before:] == [str(imported.id)] and marked(imported.id), "mail import"
