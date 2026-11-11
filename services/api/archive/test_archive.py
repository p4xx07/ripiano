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

from archive.models import Correspondent, Document, DocumentTag, DocumentType, PhysicalCopy, SavedView, Tag, TagOverride
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
def test_correspondents_and_document_types_are_owner_scoped_and_searchable():
    alice = get_user_model().objects.create_user("alice", password="secure-password-1")
    bob = get_user_model().objects.create_user("bob", password="secure-password-2")
    document = Document.objects.create(
        owner=alice, title="Envelope", original_name="envelope.pdf", original_path="originals/envelope.pdf",
        original_mime="application/pdf", original_sha256="a" * 64, original_size=10,
        status=Document.Status.READY,
    )
    client = Client()
    client.force_login(alice)
    correspondent = client.post("/api/correspondents", json.dumps({"name": "Comune di Milano"}), content_type="application/json")
    document_type = client.post("/api/document-types", json.dumps({"name": "Tax notice"}), content_type="application/json")
    assert correspondent.status_code == document_type.status_code == 201
    correspondent_id, type_id = correspondent.json()["id"], document_type.json()["id"]
    assert client.post("/api/correspondents", json.dumps({"name": "comune di milano"}), content_type="application/json").status_code == 409
    assert client.post("/api/document-types", json.dumps({"name": "TAX NOTICE"}), content_type="application/json").status_code == 409
    updated = client.patch(f"/api/documents/{document.id}", json.dumps({"correspondent_id": correspondent_id, "document_type_id": type_id}), content_type="application/json")
    assert updated.status_code == 200
    assert updated.json()["correspondent"]["name"] == "Comune di Milano"
    assert updated.json()["document_type"]["name"] == "Tax notice"
    assert [item["id"] for item in client.get("/api/documents?q=Milano").json()["documents"]] == [str(document.id)]
    assert [item["id"] for item in client.get("/api/documents?q=Tax%20notice").json()["documents"]] == [str(document.id)]
    assert client.delete(f"/api/correspondents/{correspondent_id}").status_code == 409
    renamed = client.patch(f"/api/correspondents/{correspondent_id}", json.dumps({"name": "City of Milan"}), content_type="application/json")
    assert renamed.json()["name"] == "City of Milan"
    assert client.get(f"/api/documents/{document.id}").json()["correspondent"]["name"] == "City of Milan"

    client.force_login(bob)
    assert client.get("/api/correspondents").json()["correspondents"] == []
    assert client.get("/api/document-types").json()["document_types"] == []
    own = Document.objects.create(
        owner=bob, title="Private", original_name="private.pdf", original_path="originals/private.pdf",
        original_mime="application/pdf", original_sha256="b" * 64, original_size=10,
    )
    assert client.patch(f"/api/documents/{own.id}", json.dumps({"correspondent_id": correspondent_id}), content_type="application/json").status_code == 400
    assert client.patch(f"/api/documents/{own.id}", json.dumps({"document_type_id": type_id}), content_type="application/json").status_code == 400
    assert client.patch(f"/api/correspondents/{correspondent_id}", json.dumps({"name": "Stolen"}), content_type="application/json").status_code == 404
    assert client.get("/api/documents?q=Milan").json()["documents"] == []
    client.force_login(alice)
    cleared = client.patch(f"/api/documents/{document.id}", json.dumps({"correspondent_id": None, "document_type_id": None}), content_type="application/json")
    assert cleared.json()["correspondent"] is cleared.json()["document_type"] is None
    assert client.delete(f"/api/correspondents/{correspondent_id}").status_code == 200
    assert client.delete(f"/api/document-types/{type_id}").status_code == 200
    assert not Correspondent.objects.filter(owner=alice).exists()
    assert not DocumentType.objects.filter(owner=alice).exists()


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
def test_library_filters_bind_cursor_and_keep_owner_scope():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    tag = Tag.objects.create(owner=owner, name="Tax")
    sender = Correspondent.objects.create(owner=owner, name="City")
    kind = DocumentType.objects.create(owner=owner, name="Notice")
    for index in range(51):
        document = Document.objects.create(
            owner=owner, title=f"Receipt {index:02d}", original_name=f"receipt-{index}.pdf",
            original_path=f"originals/receipt-{index}.pdf", original_mime="application/pdf",
            original_sha256="a" * 64, original_size=10, document_date=date(2026, 4, 15),
            correspondent=sender, document_type=kind,
        )
        DocumentTag.objects.create(document=document, tag=tag)
    Document.objects.create(
        owner=owner, title="Excluded receipt", original_name="excluded.pdf",
        original_path="originals/excluded.pdf", original_mime="application/pdf",
        original_sha256="b" * 64, original_size=10, document_date=date(2026, 5, 1),
    )
    Document.objects.create(
        owner=other, title="Foreign receipt", original_name="foreign.pdf",
        original_path="originals/foreign.pdf", original_mime="application/pdf",
        original_sha256="c" * 64, original_size=10, document_date=date(2026, 4, 15),
    )
    client = Client()
    client.force_login(owner)
    filters = {
        "tag_id": str(tag.id), "correspondent_id": str(sender.id),
        "document_type_id": str(kind.id), "date_from": "2026-04-15", "date_to": "2026-04-15",
    }
    first = client.get("/api/documents", filters).json()
    assert first["counts"]["total"] == 51
    assert len(first["documents"]) == 50 and first["next_cursor"]
    second = client.get("/api/documents", {**filters, "cursor": first["next_cursor"]}).json()
    assert len(second["documents"]) == 1 and second["next_cursor"] is None
    assert len({item["id"] for item in first["documents"] + second["documents"]}) == 51
    for key in filters:
        changed = {**filters, key: str(uuid4()) if key.endswith("_id") else "2026-04-16"}
        assert client.get("/api/documents", {**changed, "cursor": first["next_cursor"]}).status_code == 400
    assert client.get("/api/documents", {"tag_id": str(uuid4())}).json()["counts"]["total"] == 0
    assert client.get("/api/documents", {"tag_id": "not-a-uuid"}).status_code == 400
    assert client.get("/api/documents", {"date_from": "yesterday"}).status_code == 400
    assert client.get("/api/documents", {"date_from": "2026-05-01", "date_to": "2026-04-01"}).status_code == 400


@pytest.mark.django_db
def test_saved_searches_are_owned_validated_and_survive_deleted_metadata():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    tag = Tag.objects.create(owner=owner, name="Tax")
    foreign_tag = Tag.objects.create(owner=other, name="Private")
    sender = Correspondent.objects.create(owner=owner, name="City")
    kind = DocumentType.objects.create(owner=owner, name="Notice")
    client = Client()
    client.force_login(owner)
    payload = {
        "name": "Tax notices", "query": "permit", "tag_id": str(tag.id),
        "correspondent_id": str(sender.id), "document_type_id": str(kind.id),
        "date_from": "2026-01-01", "date_to": "2026-12-31",
    }
    created = client.post("/api/saved-views", json.dumps(payload), content_type="application/json")
    assert created.status_code == 201
    view_id = created.json()["id"]
    assert created.json()["tag_id"] == str(tag.id)
    assert client.get("/api/saved-views").json()["views"][0]["name"] == "Tax notices"
    assert client.post("/api/saved-views", json.dumps({**payload, "name": "tax NOTICES"}), content_type="application/json").status_code == 409
    assert client.post("/api/saved-views", json.dumps({**payload, "tag_id": str(foreign_tag.id), "name": "Foreign"}), content_type="application/json").status_code == 400
    assert client.patch(f"/api/saved-views/{view_id}", json.dumps({"date_from": "2027-01-01"}), content_type="application/json").status_code == 400
    renamed = client.patch(f"/api/saved-views/{view_id}", json.dumps({"name": "City permits", "query": "notice"}), content_type="application/json")
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "City permits" and renamed.json()["query"] == "notice"

    client.force_login(other)
    assert client.get("/api/saved-views").json()["views"] == []
    assert client.patch(f"/api/saved-views/{view_id}", json.dumps({"name": "Taken"}), content_type="application/json").status_code == 404
    assert client.delete(f"/api/saved-views/{view_id}").status_code == 404
    client.force_login(owner)
    tag.delete()
    assert client.get("/api/saved-views").json()["views"][0]["tag_id"] is None
    assert client.delete(f"/api/saved-views/{view_id}").status_code == 200
    assert SavedView.objects.filter(owner=owner).count() == 0


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
    field_first = client.get("/api/documents", {"q": "title:Receipt"}).json()
    field_second = client.get("/api/documents", {"q": "title:Receipt", "cursor": field_first["next_cursor"]}).json()
    assert len({item["id"] for item in field_first["documents"] + field_second["documents"]}) == 51
    assert client.get("/api/documents", {"q": "title:Other", "cursor": field_first["next_cursor"]}).status_code == 400


@pytest.mark.django_db
def test_library_sort_keeps_all_results_across_signed_pages():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    for index in range(51):
        Document.objects.create(
            owner=owner, title=f"Receipt {index % 4}", original_name=f"receipt-{index}.pdf",
            original_path=f"originals/receipt-{index}.pdf", original_mime="application/pdf",
            original_sha256="a" * 64, original_size=10,
            document_date=date(2026, 1, index % 28 + 1) if index % 3 else None,
        )
    Document.objects.filter(owner=owner).update(created_at=timezone.now())
    client = Client()
    client.force_login(owner)
    for sort in ("newest", "oldest", "document_newest", "document_oldest", "title_asc", "title_desc"):
        first = client.get("/api/documents", {"sort": sort}).json()
        second = client.get("/api/documents", {"sort": sort, "cursor": first["next_cursor"]}).json()
        items = first["documents"] + second["documents"]
        assert len(items) == len({item["id"] for item in items}) == 51
        assert first["counts"]["total"] == second["counts"]["total"] == 51
        assert second["next_cursor"] is None
        if sort.startswith("document_"):
            assert items[-1]["document_date"] is None
        if sort == "title_asc":
            assert [item["title"] for item in items] == sorted(item["title"] for item in items)
        if sort == "title_desc":
            assert [item["title"] for item in items] == sorted((item["title"] for item in items), reverse=True)
    first = client.get("/api/documents", {"sort": "title_asc"}).json()
    assert client.get("/api/documents", {"sort": "title_desc", "cursor": first["next_cursor"]}).status_code == 400
    assert client.get("/api/documents", {"sort": "unknown"}).status_code == 400
    assert client.get("/api/documents", {"sort": "relevance"}).status_code == 400


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
def test_exception_inbox_only_shows_failed_and_unreviewed_copies():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")

    def create(user, title, **fields):
        return Document.objects.create(
            owner=user, title=title, original_name=f"{title}.pdf", original_path=f"originals/{title}.pdf",
            original_mime="application/pdf", original_sha256="a" * 64, original_size=10, **fields,
        )

    original = create(owner, "Original", status=Document.Status.READY)
    duplicate = create(owner, "Copy", duplicate_of=original)
    failed = create(owner, "Failed", status=Document.Status.FAILED, error="OCR failed")
    create(other, "Foreign failed", status=Document.Status.FAILED)
    client = Client()
    client.force_login(owner)

    def inbox():
        return {item["id"] for item in client.get("/api/documents?view=exceptions").json()["documents"]}

    assert inbox() == {str(duplicate.id), str(failed.id)}
    assert client.patch(f"/api/documents/{original.id}", json.dumps({"duplicate_reviewed": True}), content_type="application/json").status_code == 400
    assert client.patch(f"/api/documents/{duplicate.id}", json.dumps({"duplicate_reviewed": "yes"}), content_type="application/json").status_code == 400
    reviewed = client.patch(f"/api/documents/{duplicate.id}", json.dumps({"duplicate_reviewed": True}), content_type="application/json").json()
    assert reviewed["duplicate_reviewed_at"] is not None
    assert inbox() == {str(failed.id)}
    reopened = client.patch(f"/api/documents/{duplicate.id}", json.dumps({"duplicate_reviewed": False}), content_type="application/json").json()
    assert reopened["duplicate_reviewed_at"] is None
    assert inbox() == {str(duplicate.id), str(failed.id)}

    with patch("archive.tasks.process_document.delay"):
        assert client.post(f"/api/documents/{failed.id}/retry").status_code == 202
    assert inbox() == {str(duplicate.id)}
    client.force_login(other)
    assert client.get("/api/documents?view=exceptions").json()["counts"]["total"] == 1
    assert client.patch(f"/api/documents/{duplicate.id}", json.dumps({"duplicate_reviewed": True}), content_type="application/json").status_code == 404


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
    document.extracted_text = ("Opening words " * 40) + "hidden renewal total" + (" closing words" * 20)
    document.save(update_fields=["action_note", "extracted_text"])
    private.action_note = "Private secret"
    private.save(update_fields=["action_note"])

    client = Client()
    client.force_login(owner)
    for query in ("Insurance", "R-ABC23456", "Renew"):
        result = client.get("/api/documents", {"q": query}).json()
        assert [item["id"] for item in result["documents"]] == [str(document.id)]
        assert result["counts"]["total"] == 1
    assert client.get("/api/documents").json()["documents"][0]["snippet"] == ""
    sticker = client.get("/api/documents", {"q": "R-ABC23456"}).json()["documents"][0]
    assert (sticker["snippet"], sticker["snippet_source"]) == ("R-ABC23456", "sticker")
    note = client.get("/api/documents", {"q": "December"}).json()["documents"][0]
    assert note["snippet_source"] == "note" and "December" in note["snippet"]
    ocr = client.get("/api/documents", {"q": "hidden renewal"}).json()["documents"][0]
    assert ocr["snippet_source"] == "document"
    assert ocr["snippet"].startswith("…") and "hidden renewal" in ocr["snippet"]
    assert len(ocr["snippet"]) <= 242
    assert client.get("/api/documents", {"q": "secret"}).json()["documents"] == []


@pytest.mark.django_db
def test_field_search_combines_owned_metadata_text_and_dates():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    sender = Correspondent.objects.create(owner=owner, name="City office")
    kind = DocumentType.objects.create(owner=owner, name="Permit notice")
    tax = Tag.objects.create(owner=owner, name="Tax records")
    filing = Tag.objects.create(owner=owner, name="Filing")

    def make_document(user, title):
        return Document.objects.create(
            owner=user, title=title, original_name=f"{title}.pdf",
            original_path=f"originals/{title}.pdf", original_mime="application/pdf",
            original_sha256="a" * 64, original_size=10,
            extracted_text="Permit fee due", action_note="Renew next year",
            document_date=date(2026, 4, 15),
        )

    matching = make_document(owner, "Property tax")
    matching.correspondent = sender
    matching.document_type = kind
    matching.save(update_fields=["correspondent", "document_type"])
    DocumentTag.objects.create(document=matching, tag=tax)
    DocumentTag.objects.create(document=matching, tag=filing)
    PhysicalCopy.objects.create(document=matching, sticker_code="R-ABC23456")
    partial = make_document(owner, "Other tax")
    partial.extracted_text = "Other content"
    partial.action_note = ""
    partial.save(update_fields=["extracted_text", "action_note"])
    DocumentTag.objects.create(document=partial, tag=tax)
    make_document(other, "Property tax")

    client = Client()
    client.force_login(owner)
    for query in (
        'title:"Property tax"',
        'title:"Property tax" sender:"City office"',
        'text:Permit note:Renew',
        'tag:"Tax records" tag:Filing',
        'sender:"City office" type:"Permit notice" sticker:R-ABC date:2026-04-15',
        'sender:"City office" Permit',
    ):
        result = client.get("/api/documents", {"q": query})
        assert result.status_code == 200
        assert [item["id"] for item in result.json()["documents"]] == [str(matching.id)]
        assert result.json()["counts"]["total"] == 1
    assert client.get("/api/documents", {"q": 'sender:"City office" tag:missing'}).json()["documents"] == []
    text_result = client.get("/api/documents", {"q": "text:Permit"}).json()["documents"][0]
    assert text_result["snippet_source"] == "document" and "Permit" in text_result["snippet"]
    note_result = client.get("/api/documents", {"q": "note:Renew"}).json()["documents"][0]
    assert note_result["snippet_source"] == "note" and "Renew" in note_result["snippet"]
    assert client.get("/api/documents", {"q": "date:2026-99-99"}).status_code == 400
    assert client.get("/api/documents", {"q": "date:20260415"}).status_code == 400
    assert client.get("/api/documents", {"q": "sender:City", "date_from": "2026-04-16"}).json()["documents"] == []


@pytest.mark.django_db
def test_bulk_tagging_is_atomic_owner_scoped_and_preserves_manual_corrections():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    tag = Tag.objects.create(owner=owner, name="Taxes")
    foreign_tag = Tag.objects.create(owner=other, name="Private")

    def make_document(user, title):
        return Document.objects.create(
            owner=user, title=title, original_name=f"{title}.pdf",
            original_path=f"originals/{title}.pdf", original_mime="application/pdf",
            original_sha256="a" * 64, original_size=10,
        )

    first = make_document(owner, "First")
    second = make_document(owner, "Second")
    foreign = make_document(other, "Foreign")
    DocumentTag.objects.create(document=first, tag=tag, origin=DocumentTag.Origin.RULE)
    client = Client()
    client.force_login(owner)

    def change(action, ids, tag_id=tag.id):
        return client.post("/api/documents/bulk-tags", json.dumps({
            "action": action, "document_ids": [str(value) for value in ids], "tag_id": str(tag_id),
        }), content_type="application/json")

    assert change("remove", [first.id, second.id]).json()["updated"] == 2
    assert not DocumentTag.objects.filter(document_id__in=[first.id, second.id], tag=tag).exists()
    assert TagOverride.objects.filter(document_id__in=[first.id, second.id], tag=tag).count() == 2
    assert change("add", [first.id, second.id]).json()["updated"] == 2
    assert set(DocumentTag.objects.filter(tag=tag).values_list("document_id", flat=True)) == {first.id, second.id}
    assert set(DocumentTag.objects.filter(tag=tag).values_list("origin", flat=True)) == {DocumentTag.Origin.MANUAL}
    assert not TagOverride.objects.filter(document_id__in=[first.id, second.id], tag=tag).exists()

    assert change("remove", [first.id, foreign.id]).status_code == 404
    assert DocumentTag.objects.filter(document=first, tag=tag).exists()
    assert change("add", [first.id], foreign_tag.id).status_code == 404
    assert change("add", [first.id, first.id]).status_code == 400
    assert change("add", []).status_code == 400
    assert change("add", [first.id], "not-a-uuid").status_code == 400
    client.force_login(other)
    assert change("add", [first.id], foreign_tag.id).status_code == 404
    assert not DocumentTag.objects.filter(document=foreign, tag=foreign_tag).exists()
