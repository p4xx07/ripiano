from datetime import date, timedelta
import json
from io import BytesIO
from uuid import uuid4
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone
from PIL import Image

from archive.models import Document, DocumentTag, PhysicalCopy, Tag
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
def test_android_scan_retry_is_idempotent_and_owner_scoped(tmp_path):
    first_owner = get_user_model().objects.create_user("first", password="secure-password-1")
    second_owner = get_user_model().objects.create_user("second", password="secure-password-2")
    scan_id = str(uuid4())
    with override_settings(MEDIA_ROOT=tmp_path):
        client = Client()
        client.force_login(first_owner)
        with patch("archive.ingestion.process_document.delay"):
            first = client.post("/api/documents", {"document": image_upload()}, HTTP_X_RIPIANO_SCAN_ID=scan_id)
            again = client.post("/api/documents", {"document": image_upload()}, HTTP_X_RIPIANO_SCAN_ID=scan_id)
            client.force_login(second_owner)
            second = client.post("/api/documents", {"document": image_upload()}, HTTP_X_RIPIANO_SCAN_ID=scan_id)
        assert first.status_code == 202
        assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
        assert second.status_code == 202 and second.json()["id"] != first.json()["id"]
        assert Document.objects.count() == 2
        assert Document.objects.filter(source=Document.Source.ANDROID).count() == 2
        assert client.post("/api/documents", {"document": image_upload()}, HTTP_X_RIPIANO_SCAN_ID="bad").status_code == 400


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


@pytest.mark.django_db
def test_follow_ups_are_optional_owner_scoped_and_due_ordered():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")

    def make_document(user, title):
        return Document.objects.create(
            owner=user, title=title, original_name=f"{title}.pdf", original_path=f"originals/{title}.pdf",
            original_mime="application/pdf", original_sha256="a" * 64, original_size=10,
        )

    later = make_document(owner, "Later")
    sooner = make_document(owner, "Sooner")
    no_due_date = make_document(owner, "No due date")
    foreign = make_document(other, "Foreign")
    client = Client()
    client.force_login(owner)
    assert client.get("/api/documents?view=actions").json()["documents"] == []

    def update(document, body):
        return client.patch(f"/api/documents/{document.id}", json.dumps(body), content_type="application/json")

    assert update(later, {"action_status": "open", "action_due_date": "2027-02-01", "action_note": "Pay this"}).status_code == 200
    assert update(sooner, {"action_status": "open", "action_due_date": "2027-01-01"}).status_code == 200
    assert update(no_due_date, {"action_status": "open"}).status_code == 200
    assert update(foreign, {"action_status": "open"}).status_code == 404
    assert [item["title"] for item in client.get("/api/documents?view=actions").json()["documents"]] == ["Sooner", "Later", "No due date"]
    assert update(sooner, {"action_due_date": "bad"}).status_code == 400
    assert update(sooner, {"action_status": "wrong"}).status_code == 400
    assert update(sooner, {"action_note": "x" * 501}).status_code == 400

    completed = update(sooner, {"action_status": "done"}).json()
    assert completed["action_completed_at"] is not None
    assert [item["title"] for item in client.get("/api/documents?view=actions").json()["documents"]] == ["Later", "No due date"]
    reopened = update(sooner, {"action_status": "open"}).json()
    assert reopened["action_completed_at"] is None


@pytest.mark.django_db
def test_document_and_action_lists_page_without_hiding_older_items():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    for index in range(51):
        Document.objects.create(
            owner=owner, title=f"Document {index:02d}", original_name=f"doc-{index}.pdf",
            original_path=f"originals/doc-{index}.pdf", original_mime="application/pdf",
            original_sha256="a" * 64, original_size=10,
            action_status=Document.ActionStatus.OPEN,
        )
    Document.objects.create(
        owner=other, title="Foreign", original_name="foreign.pdf",
        original_path="originals/foreign.pdf", original_mime="application/pdf",
        original_sha256="b" * 64, original_size=10,
        action_status=Document.ActionStatus.OPEN,
    )
    client = Client()
    client.force_login(owner)
    for suffix in ("", "?view=actions"):
        first = client.get(f"/api/documents{suffix}").json()
        second = client.get("/api/documents", {"cursor": first["next_cursor"], "view": "actions" if suffix else "documents"}).json()
        assert first["counts"]["total"] == 51
        assert len(first["documents"]) == 50 and first["next_cursor"]
        assert len(second["documents"]) == 1 and second["next_cursor"] is None
        assert len({item["id"] for item in first["documents"] + second["documents"]}) == 51
        assert all(item["title"] != "Foreign" for item in first["documents"] + second["documents"])
    assert client.get("/api/documents?offset=50").status_code == 400
    assert client.get("/api/documents?cursor=bad").status_code == 400


@pytest.mark.django_db
def test_page_cursor_survives_new_ingest_and_completed_follow_up():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)

    def create(index):
        return Document.objects.create(
            owner=owner, title=f"Document {index:02d}", original_name=f"doc-{index}.pdf",
            original_path=f"originals/doc-{index}.pdf", original_mime="application/pdf",
            original_sha256="a" * 64, original_size=10, action_status=Document.ActionStatus.OPEN,
        )

    documents = [create(index) for index in range(51)]
    first = client.get("/api/documents").json()
    first_actions = client.get("/api/documents?view=actions").json()
    assert client.get("/api/documents", {"q": "another", "cursor": first["next_cursor"]}).status_code == 400
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    client.force_login(other)
    assert client.get("/api/documents", {"cursor": first["next_cursor"]}).status_code == 400
    client.force_login(owner)
    newest = create(51)
    documents[-1].action_status = Document.ActionStatus.DONE
    documents[-1].save(update_fields=["action_status"])

    second = client.get("/api/documents", {"cursor": first["next_cursor"]}).json()
    second_actions = client.get("/api/documents", {"view": "actions", "cursor": first_actions["next_cursor"]}).json()
    assert [item["id"] for item in second["documents"]] == [str(documents[0].id)]
    assert [item["id"] for item in second_actions["documents"]] == [str(documents[0].id)]
    assert not ({item["id"] for item in first["documents"]} & {item["id"] for item in second["documents"]})
    assert client.get("/api/documents").json()["documents"][0]["id"] == str(newest.id)
    assert client.get("/api/documents", {"view": "actions", "cursor": first["next_cursor"]}).status_code == 400


@pytest.mark.django_db
def test_search_cursor_has_stable_tie_breaker_on_equal_timestamps():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    for index in range(51):
        Document.objects.create(
            owner=owner, title=f"Receipt {index}", original_name=f"receipt-{index}.pdf",
            original_path=f"originals/receipt-{index}.pdf", original_mime="application/pdf",
            original_sha256="a" * 64, original_size=10,
        )
    Document.objects.filter(owner=owner).update(created_at=timezone.now())
    client = Client()
    client.force_login(owner)
    first = client.get("/api/documents", {"q": "Receipt"}).json()
    second = client.get("/api/documents", {"q": "Receipt", "cursor": first["next_cursor"]}).json()
    assert len({item["id"] for item in first["documents"] + second["documents"]}) == 51
    assert second["next_cursor"] is None


@pytest.mark.django_db
def test_action_cursor_keeps_undated_follow_ups_after_dated_ones():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    for index in range(50):
        Document.objects.create(
            owner=owner, title=f"Dated {index}", original_name=f"dated-{index}.pdf",
            original_path=f"originals/dated-{index}.pdf", original_mime="application/pdf",
            original_sha256="a" * 64, original_size=10,
            action_status=Document.ActionStatus.OPEN, action_due_date=date(2027, 1, 1),
        )
    undated = Document.objects.create(
        owner=owner, title="Undated", original_name="undated.pdf",
        original_path="originals/undated.pdf", original_mime="application/pdf",
        original_sha256="b" * 64, original_size=10,
        action_status=Document.ActionStatus.OPEN,
    )
    client = Client()
    client.force_login(owner)
    first = client.get("/api/documents?view=actions").json()
    second = client.get("/api/documents", {"view": "actions", "cursor": first["next_cursor"]}).json()
    assert len(first["documents"]) == 50
    assert [item["id"] for item in second["documents"]] == [str(undated.id)]


@pytest.mark.django_db
def test_search_finds_tags_action_notes_and_sticker_codes_without_crossing_owners():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")

    def make_document(user, name):
        return Document.objects.create(
            owner=user, title=name, original_name=f"{name}.pdf", original_path=f"originals/{name}.pdf",
            original_mime="application/pdf", original_sha256="a" * 64, original_size=10,
        )

    document = make_document(owner, "Untitled")
    private = make_document(other, "Foreign")
    tag = Tag.objects.create(owner=owner, name="Insurance")
    DocumentTag.objects.create(document=document, tag=tag)
    PhysicalCopy.objects.create(document=document, sticker_code="R-ABC23456")
    document.action_note = "Renew before December"
    document.save(update_fields=["action_note"])
    private.action_note = "Private secret"
    private.save(update_fields=["action_note"])

    client = Client()
    client.force_login(owner)
    for query in ("Insurance", "R-ABC23456", "Renew"):
        result = client.get("/api/documents", {"q": query}).json()
        assert [item["id"] for item in result["documents"]] == [str(document.id)]
        assert result["counts"]["total"] == 1
    assert client.get("/api/documents", {"q": "secret"}).json()["documents"] == []
