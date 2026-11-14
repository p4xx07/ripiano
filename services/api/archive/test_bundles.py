import hashlib
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.core import mail as outbox
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone

from archive.bundle_views import build_bundle, expire_bundles
from archive.ingestion import ingest_document
from archive.models import DocumentEmailSend, ShareBundle


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1", email="owner@example.test")


def upload(owner, tmp_path, name, content):
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        return ingest_document(owner, SimpleUploadedFile(name, content))


def png(color):
    from PIL import Image
    output = BytesIO()
    Image.new("RGB", (4, 4), color).save(output, format="PNG")
    return output.getvalue()


def create_bundle(client, ids, django_capture_on_commit_callbacks, **extra):
    with patch("archive.tasks.build_share_bundle.delay") as queued:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post("/api/share-bundles", {"document_ids": [str(item) for item in ids], **extra}, content_type="application/json")
    if response.status_code == 201:
        assert len(callbacks) == 1
        build_bundle(queued.call_args[0][0])
    return response


@pytest.mark.django_db
def test_bundle_zip_is_built_once_verified_and_served_until_revoked(owner, tmp_path, django_capture_on_commit_callbacks):
    first = upload(owner, tmp_path, "scan.png", png("red"))
    second = upload(owner, tmp_path, "scan.png", png("blue"))
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    foreign = upload(other, tmp_path, "theirs.png", png("green"))
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=tmp_path, PUBLIC_ORIGIN="https://ripiano.test"):
        assert client.post("/api/share-bundles", {"document_ids": [str(first.id), str(foreign.id)]}, content_type="application/json").status_code == 404
        created = create_bundle(client, [first.id, second.id], django_capture_on_commit_callbacks, title="Tax 2026", expires_in_days=3)
        assert created.status_code == 201
        token = created.json()["url"].rsplit("/", 1)[1]
        bundle = ShareBundle.objects.get()
        assert token not in bundle.token_hash and bundle.zip_status == "ready"
        anonymous = Client()
        download = anonymous.get(f"/api/share-bundles/{token}")
        assert download.status_code == 200 and download["Cache-Control"] == "no-store"
        with ZipFile(BytesIO(b"".join(download.streaming_content))) as archive:
            names = sorted(archive.namelist())
            assert names == ["scan (2).png", "scan.png"]
            assert sorted(hashlib.sha256(archive.read(name)).hexdigest() for name in names) == sorted([first.original_sha256, second.original_sha256])
        anonymous.get(f"/api/share-bundles/{token}")
        bundle.refresh_from_db()
        assert bundle.downloads == 2

        with django_capture_on_commit_callbacks(execute=True):
            assert client.delete(f"/api/share-bundles/{bundle.id}").json()["active"] is False
        assert anonymous.get(f"/api/share-bundles/{token}").status_code == 404
        assert not (tmp_path / "bundles" / f"{bundle.id}.zip").exists()
        assert anonymous.get("/api/share-bundles/not-a-token").status_code == 404
        intruder = Client()
        intruder.force_login(other)
        assert intruder.get("/api/share-bundles").json() == {"bundles": []}


@pytest.mark.django_db
def test_trash_and_new_versions_revoke_bundles_and_tampered_originals_never_ship(owner, tmp_path, django_capture_on_commit_callbacks):
    from archive.versions import add_version

    from archive.models import Document

    first = upload(owner, tmp_path, "a.png", png("red"))
    second = upload(owner, tmp_path, "b.png", png("blue"))
    Document.objects.update(status=Document.Status.READY)
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=tmp_path):
        token = create_bundle(client, [first.id, second.id], django_capture_on_commit_callbacks).json()["url"].rsplit("/", 1)[1]
        with django_capture_on_commit_callbacks(execute=True):
            assert client.post(f"/api/documents/{second.id}/trash").status_code == 200
        client.post(f"/api/documents/{second.id}/restore")
        assert Client().get(f"/api/share-bundles/{token}").status_code == 404  # restoring does not re-share

        token = create_bundle(client, [first.id], django_capture_on_commit_callbacks).json()["url"].rsplit("/", 1)[1]
        with django_capture_on_commit_callbacks(execute=True), patch("archive.tasks.process_document.delay"):
            replaced = add_version(first.id, owner, SimpleUploadedFile("a2.png", png("black")), "Uploaded new version")
        assert replaced.revoked_shares == 1
        assert Client().get(f"/api/share-bundles/{token}").status_code == 404

        Document.objects.filter(pk=first.pk).update(status=Document.Status.READY)
        first.refresh_from_db()
        (tmp_path / first.original_path).write_bytes(b"tampered")
        failed = create_bundle(client, [first.id], django_capture_on_commit_callbacks)
        assert ShareBundle.objects.get(pk=failed.json()["id"]).zip_status == "failed"
        assert Client().get(f"/api/share-bundles/{failed.json()['url'].rsplit('/', 1)[1]}").status_code == 503
        ShareBundle.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        assert expire_bundles() == 0 or not list((tmp_path / "bundles").glob("*.zip"))


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_HOST="smtp.example.test", RIPIANO_DOCUMENT_EMAIL=True)
def test_emailing_a_document_is_opt_in_verified_and_limited_per_recipient(owner, tmp_path, django_capture_on_commit_callbacks):
    from archive.tasks import send_document_email

    document = upload(owner, tmp_path, "letter.png", png("white"))
    client = Client()
    client.force_login(owner)
    endpoint = f"/api/documents/{document.id}/email"
    with override_settings(MEDIA_ROOT=tmp_path):
        assert client.get(endpoint).json()["configured"] is True
        assert client.post(endpoint, {"to": "not-an-address"}, content_type="application/json").status_code == 400
        assert client.post(endpoint, {"to": "a@example.test," * 120}, content_type="application/json").status_code == 400
        assert client.post(endpoint, {"to": "me@example.test", "attachment": "searchable"}, content_type="application/json").status_code == 409
        with django_capture_on_commit_callbacks() as callbacks, patch("archive.tasks.send_document_email.delay"):
            queued = client.post(endpoint, {"to": "me@example.test, partner@example.test, me@example.test", "message": "For the files"}, content_type="application/json")
        assert queued.status_code == 202 and len(callbacks) == 1 and queued.json()["recipients"] == "me@example.test, partner@example.test"
        send_document_email(queued.json()["id"])
    sent = outbox.outbox[0]
    assert sent.to == ["me@example.test", "partner@example.test"] and sent.reply_to == ["owner@example.test"] and "For the files" in sent.body
    assert sent.attachments[0][1] == (tmp_path / document.original_path).read_bytes()
    assert DocumentEmailSend.objects.get().status == "sent"

    with override_settings(MEDIA_ROOT=tmp_path):
        with patch("archive.tasks.send_document_email.delay"):
            tampered = client.post(endpoint, {"to": "x@example.test"}, content_type="application/json").json()["id"]
        (tmp_path / document.original_path).write_bytes(b"tampered")
        send_document_email(tampered)
        assert DocumentEmailSend.objects.get(pk=tampered).status == "failed"
        DocumentEmailSend.objects.filter(pk=tampered).update(status="queued", created_at=timezone.now() - timedelta(hours=2))
        assert client.get(endpoint).json()["sends"][-1]["status"] == "failed"  # stale queued sends are closed
        with patch("archive.tasks.send_document_email.delay"):
            many = ", ".join(f"p{index}@example.test" for index in range(10))
            assert client.post(endpoint, {"to": many}, content_type="application/json").status_code == 202
            assert client.post(endpoint, {"to": many}, content_type="application/json").status_code == 202
            assert client.post(endpoint, {"to": many}, content_type="application/json").status_code == 429
    with override_settings(RIPIANO_DOCUMENT_EMAIL=False):
        assert client.post(endpoint, {"to": "me@example.test"}, content_type="application/json").status_code == 409
