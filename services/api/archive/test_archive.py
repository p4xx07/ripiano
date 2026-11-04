from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone
from PIL import Image

from archive.models import Document
from archive.tasks import reconcile_pending_documents


def image_upload(name="receipt.png"):
    content = BytesIO()
    Image.new("RGB", (8, 8), "white").save(content, format="PNG")
    return SimpleUploadedFile(name, content.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_setup_requires_key_and_session_csrf(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_SETUP_KEY="known-setup-key"):
        client = Client(enforce_csrf_checks=True)
        csrf = client.get("/api/session").cookies["csrftoken"].value
        body = '{"username":"owner","password":"long-enough-password","setup_key":"known-setup-key"}'
        assert client.post("/api/setup", body, content_type="application/json").status_code == 403
        response = client.post("/api/setup", body, content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
        assert response.status_code == 201
        assert client.get("/api/session").json()["authenticated"]
        rotated_csrf = client.cookies["csrftoken"].value
        assert client.post("/api/setup", body, content_type="application/json", HTTP_X_CSRFTOKEN=rotated_csrf).status_code == 409


@pytest.mark.django_db
def test_upload_search_download_and_owner_isolation(tmp_path):
    user = get_user_model().objects.create_user("alice", password="secure-password-1")
    other = get_user_model().objects.create_user("bob", password="secure-password-2")
    with override_settings(MEDIA_ROOT=tmp_path):
        client = Client()
        client.force_login(user)
        with patch("archive.ingestion.process_document.delay"):
            response = client.post("/api/documents", {"document": image_upload()})
        assert response.status_code == 202
        document = Document.objects.get(pk=response.json()["id"])
        assert (tmp_path / document.original_path).read_bytes().startswith(b"\x89PNG")
        assert list(client.get(f"/api/documents/{document.id}/original").streaming_content)

        document.extracted_text = "A searchable electricity bill"
        document.status = Document.Status.READY
        document.save(update_fields=["extracted_text", "status"])
        assert len(client.get("/api/documents?q=electricity").json()["documents"]) == 1
        assert client.get("/api/documents?q=unrelated").json()["documents"] == []

        client.force_login(other)
        assert client.get("/api/documents").json()["documents"] == []
        assert client.get(f"/api/documents/{document.id}").status_code == 404
        assert client.get(f"/api/documents/{document.id}/original").status_code == 404


@pytest.mark.django_db
def test_invalid_upload_does_not_leave_original(tmp_path):
    user = get_user_model().objects.create_user("alice", password="secure-password-1")
    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_MAX_UPLOAD_BYTES=4):
        client = Client()
        client.force_login(user)
        response = client.post("/api/documents", {"document": image_upload()})
        assert response.status_code == 400
        assert Document.objects.count() == 0
        assert list((tmp_path / "originals").rglob("*.png")) == []


@pytest.mark.django_db
def test_exact_duplicate_is_flagged_without_discarding_either_original(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    with override_settings(MEDIA_ROOT=tmp_path):
        client = Client()
        client.force_login(owner)
        with patch("archive.ingestion.process_document.delay"):
            first = client.post("/api/documents", {"document": image_upload("first.png")}).json()
            second = client.post("/api/documents", {"document": image_upload("again.png")}).json()
            client.force_login(other)
            foreign = client.post("/api/documents", {"document": image_upload("other.png")}).json()
        assert first["duplicate_of"] is None
        assert second["duplicate_of"] == {"id": first["id"], "title": first["title"]}
        assert foreign["duplicate_of"] is None
        assert Document.objects.count() == 3
        assert len({document.original_path for document in Document.objects.all()}) == 3
        assert all((tmp_path / document.original_path).exists() for document in Document.objects.all())


@pytest.mark.django_db
def test_reconciler_recovers_stale_processing(tmp_path):
    user = get_user_model().objects.create_user("alice", password="secure-password-1")
    document = Document.objects.create(
        owner=user, title="Example", original_name="example.pdf", original_path="missing.pdf",
        original_mime="application/pdf", original_sha256="a" * 64, original_size=10,
        status=Document.Status.PROCESSING,
        processing_started_at=timezone.now() - timedelta(hours=2),
    )
    with patch("archive.tasks.process_document.delay") as enqueue:
        reconcile_pending_documents()
    document.refresh_from_db()
    assert document.status == Document.Status.PENDING
    enqueue.assert_called_once_with(str(document.id))


@pytest.mark.django_db
def test_failed_document_can_retry_and_archive_is_owner_only(tmp_path):
    user = get_user_model().objects.create_user("alice", password="secure-password-1")
    other = get_user_model().objects.create_user("bob", password="secure-password-2")
    document = Document.objects.create(
        owner=user, title="Example", original_name="example.pdf", original_path="originals/example.pdf",
        original_mime="application/pdf", original_sha256="a" * 64, original_size=10,
        status=Document.Status.FAILED, error="OCR failed",
    )
    with override_settings(MEDIA_ROOT=tmp_path):
        client = Client()
        client.force_login(other)
        assert client.post(f"/api/documents/{document.id}/retry").status_code == 404
        assert client.get(f"/api/documents/{document.id}/archive").status_code == 404
        client.force_login(user)
        assert client.get(f"/api/documents/{document.id}/archive").status_code == 409
        with patch("archive.tasks.process_document.delay") as enqueue:
            response = client.post(f"/api/documents/{document.id}/retry")
        assert response.status_code == 202
        enqueue.assert_called_once_with(str(document.id))
        document.refresh_from_db()
        assert document.status == Document.Status.PENDING and not document.error

        archive = tmp_path / "archive/example.pdf"
        archive.parent.mkdir()
        archive.write_bytes(b"%PDF-1.4 test")
        document.archive_path = "archive/example.pdf"
        document.status = Document.Status.READY
        document.save(update_fields=["archive_path", "status"])
        assert b"".join(client.get(f"/api/documents/{document.id}/archive").streaming_content).startswith(b"%PDF-")
