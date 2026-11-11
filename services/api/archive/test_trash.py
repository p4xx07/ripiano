import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from archive.mcp_server import _execute
from archive.models import AgentGrant, Document, DocumentNote, PhysicalCopy, Tag


@pytest.mark.django_db
def test_trash_hides_every_access_path_and_restore_preserves_archive(tmp_path):
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    original = tmp_path / "originals" / "sample.pdf"
    original.parent.mkdir()
    original.write_bytes(b"preserved original")
    archive = tmp_path / "archive" / "sample.pdf"
    archive.parent.mkdir()
    archive.write_bytes(b"preserved archive")
    document = Document.objects.create(
        owner=owner, title="Private invoice", original_name="sample.pdf",
        original_path="originals/sample.pdf", archive_path="archive/sample.pdf",
        original_mime="application/pdf", original_sha256="a" * 64, original_size=18,
        status=Document.Status.READY, extracted_text="account reference 9473",
        action_status=Document.ActionStatus.OPEN,
    )
    note = DocumentNote.objects.create(document=document, author=owner, body="Keep the paper")
    copy = PhysicalCopy.objects.create(document=document, sticker_code="R-TRASH123")
    tag = Tag.objects.create(owner=owner, name="Invoices")
    grant = AgentGrant.objects.create(
        owner=owner, name="local", token_hash="a" * 64,
        scopes=["documents:search", "documents:text", "documents:tag"],
        expires_at="2099-01-01T00:00:00Z",
    )
    client = Client()
    client.force_login(owner)

    with override_settings(MEDIA_ROOT=tmp_path):
        assert client.get(f"/api/documents/{document.id}/original").status_code == 200
        assert client.post(f"/api/documents/{document.id}/trash").status_code == 200
        document.refresh_from_db()
        assert document.trashed_at is not None
        assert client.post(f"/api/documents/{document.id}/trash").status_code == 409
        assert client.get("/api/documents").json()["counts"]["total"] == 0
        assert client.get("/api/documents?q=9473").json()["documents"] == []
        assert client.get("/api/documents?view=actions").json()["documents"] == []
        trash = client.get("/api/documents?view=trash").json()
        assert [item["id"] for item in trash["documents"]] == [str(document.id)]
        assert trash["documents"][0]["trashed_at"] is not None
        assert client.get(f"/api/documents/{document.id}").status_code == 404
        assert client.patch(f"/api/documents/{document.id}", json.dumps({"title": "Changed"}), content_type="application/json").status_code == 404
        assert client.get(f"/api/documents/{document.id}/notes").status_code == 404
        assert client.delete(f"/api/documents/{document.id}/notes/{note.id}").status_code == 404
        assert client.get(f"/api/documents/{document.id}/original").status_code == 404
        assert client.get(f"/api/documents/{document.id}/archive").status_code == 404
        assert client.post(f"/api/documents/{document.id}/reprocess").status_code == 404
        assert client.get(f"/api/documents/{document.id}/copies").status_code == 404
        assert client.patch(f"/api/copies/{copy.id}", json.dumps({"location_id": None}), content_type="application/json").status_code == 404
        assert client.get(f"/api/copies/{copy.id}/label").status_code == 404
        assert client.get(f"/api/stickers/{copy.sticker_code}").status_code == 410
        assert client.get(f"/api/stickers/{copy.sticker_code}").json()["error"].endswith("Restore the document to use it again.")
        assert _execute(grant, "search_documents", {"query": "Private"})[1]["documents"] == []
        assert _execute(grant, "get_document_text", {"document_id": str(document.id)})[1]["error"]
        assert _execute(grant, "change_document_tags", {"document_id": str(document.id), "add": [str(tag.id)]})[1]["error"]

        client.force_login(other)
        assert client.get("/api/documents?view=trash").json()["documents"] == []
        assert client.post(f"/api/documents/{document.id}/restore").status_code == 404
        client.force_login(owner)
        assert client.post(f"/api/documents/{document.id}/restore").status_code == 200
        assert client.post(f"/api/documents/{document.id}/restore").status_code == 404
        assert [item["id"] for item in client.get("/api/documents?q=9473").json()["documents"]] == [str(document.id)]
        assert client.get(f"/api/documents/{document.id}/original").getvalue() == b"preserved original"
        assert client.get(f"/api/documents/{document.id}/archive").getvalue() == b"preserved archive"
        assert client.get(f"/api/documents/{document.id}/notes").json()["notes"][0]["body"] == "Keep the paper"
        assert client.get(f"/api/stickers/{copy.sticker_code}").status_code == 200
        assert _execute(grant, "search_documents", {"query": "Private"})[1]["documents"][0]["id"] == str(document.id)


@pytest.mark.django_db
def test_processing_document_cannot_enter_trash():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)
    document = Document.objects.create(
        owner=owner, title="Processing", original_name="sample.pdf", original_path="originals/sample.pdf",
        original_mime="application/pdf", original_sha256="b" * 64, original_size=1,
        status=Document.Status.PROCESSING,
    )
    assert client.post(f"/api/documents/{document.id}/trash").status_code == 409
    document.refresh_from_db()
    assert document.trashed_at is None


@pytest.mark.django_db
def test_trash_cursor_pages_newest_moves_first():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)
    now = timezone.now()
    documents = []
    for index in range(51):
        documents.append(Document(
            owner=owner, title=f"Archived {index}", original_name=f"{index}.pdf",
            original_path=f"originals/{index}.pdf", original_mime="application/pdf",
            original_sha256=f"{index:064x}", original_size=1,
            trashed_at=now + timedelta(seconds=index), status=Document.Status.READY,
        ))
    Document.objects.bulk_create(documents)
    first = client.get("/api/documents?view=trash").json()
    second = client.get("/api/documents", {"view": "trash", "cursor": first["next_cursor"]}).json()
    assert first["counts"]["total"] == 51
    assert len(first["documents"]) == 50
    assert first["documents"][0]["title"] == "Archived 50"
    assert [item["title"] for item in second["documents"]] == ["Archived 0"]
    assert second["next_cursor"] is None


@pytest.mark.django_db
def test_android_retry_cannot_resurrect_a_trashed_scan():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)
    scan_id = str(uuid4())
    document = Document.objects.create(
        owner=owner, source=Document.Source.ANDROID, source_ref=scan_id,
        title="Phone scan", original_name="scan.pdf", original_path="originals/scan.pdf",
        original_mime="application/pdf", original_sha256="c" * 64, original_size=1,
        status=Document.Status.READY,
    )
    assert client.post(f"/api/documents/{document.id}/trash").status_code == 200
    result = client.post(
        "/api/documents",
        {"document": SimpleUploadedFile("scan.pdf", b"upload retry", content_type="application/pdf")},
        HTTP_X_RIPIANO_SCAN_ID=scan_id,
    )
    assert result.status_code == 409
    assert "Restore it" in result.json()["error"]
    assert Document.objects.filter(owner=owner).count() == 1
    assert client.post(f"/api/documents/{document.id}/restore").status_code == 200
    repeated = client.post(
        "/api/documents",
        {"document": SimpleUploadedFile("scan.pdf", b"upload retry", content_type="application/pdf")},
        HTTP_X_RIPIANO_SCAN_ID=scan_id,
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == str(document.id)
