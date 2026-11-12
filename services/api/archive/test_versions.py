import shutil
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone
from pypdf import PdfReader, PdfWriter

from archive.ingestion import ingest_document
from archive.models import Document, DocumentVersion
from archive.purge import record_purge, remove_job_media


def pdf(*sizes, signed=False):
    writer = PdfWriter()
    for width in sizes:
        writer.add_blank_page(width=width, height=800)
    if signed:
        writer.add_metadata({"/Producer": "signer"})
    output = BytesIO()
    writer.write(output)
    data = output.getvalue()
    return data + b"\n% /Type /Sig /ByteRange [0 1 2 3]\n" if signed else data


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1")


def ready(owner, tmp_path, content, name="scan.pdf"):
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        document = ingest_document(owner, SimpleUploadedFile(name, content))
    Document.objects.filter(pk=document.pk).update(status=Document.Status.READY, processed_at=timezone.now())
    document.refresh_from_db()
    return document


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_page_edits_create_a_new_version_and_keep_the_previous_file(owner, tmp_path, django_capture_on_commit_callbacks):
    original = pdf(300, 400, 500)
    document = ready(owner, tmp_path, original)
    client = client_for(owner)
    with override_settings(MEDIA_ROOT=tmp_path):
        info = client.get(f"/api/documents/{document.id}/pages").json()
        assert info == {"count": 3, "source": "original", "signed": False, "version_number": 1}
        assert client.post(f"/api/documents/{document.id}/pages", {"order": [0, 1, 2]}, content_type="application/json").json()["error"] == "Nothing changed."
        with django_capture_on_commit_callbacks() as callbacks:
            response = client.post(f"/api/documents/{document.id}/pages", {"order": [2, 0], "rotate": {"0": 90}}, content_type="application/json")
        assert response.status_code == 202 and len(callbacks) == 1
        document.refresh_from_db()
        assert (document.version_number, document.status) == (2, Document.Status.PENDING)
        assert document.version_note == "Edited pages: removed 1 page, rotated 1 page, reordered pages"
        pages = PdfReader(tmp_path / document.original_path).pages
        assert [float(item.mediabox.width) for item in pages] == [500, 300] and pages[1].rotation == 90
        kept = DocumentVersion.objects.get(document=document)
        assert kept.number == 1 and (tmp_path / kept.original_path).read_bytes() == original
        assert client.post(f"/api/documents/{document.id}/pages", {"order": [0]}, content_type="application/json").status_code == 409  # still processing

        Document.objects.filter(pk=document.pk).update(status=Document.Status.READY)
        listing = client.get(f"/api/documents/{document.id}/versions").json()
        assert listing["current"]["number"] == 2 and [item["number"] for item in listing["versions"]] == [1]
        download = client.get(f"/api/documents/{document.id}/versions/{kept.id}/download")
        assert b"".join(download.streaming_content) == original
        with django_capture_on_commit_callbacks():
            assert client.post(f"/api/documents/{document.id}/versions/{kept.id}/restore").status_code == 202
        document.refresh_from_db()
        assert document.version_number == 3 and (tmp_path / document.original_path).read_bytes() == original
        assert document.version_note == "Restored version 1"
        assert DocumentVersion.objects.filter(document=document).count() == 2
        Document.objects.filter(pk=document.pk).update(status=Document.Status.READY)
        exported = client.get(f"/api/documents/{document.id}/export")
        with __import__("zipfile").ZipFile(BytesIO(b"".join(exported.streaming_content))) as bundle:
            assert bundle.read("versions/v1.pdf") == original
            manifest = __import__("json").loads(bundle.read("manifest.json"))
        assert [item["number"] for item in manifest["files"]["previous_versions"]] == [2, 1]
        assert manifest["document"]["version"] == {"number": 3, "note": "Restored version 1"}


@pytest.mark.django_db
def test_signed_pdfs_need_explicit_consent_and_the_signed_file_is_kept(owner, tmp_path, django_capture_on_commit_callbacks):
    signed = pdf(300, 400, signed=True)
    document = ready(owner, tmp_path, signed)
    client = client_for(owner)
    with override_settings(MEDIA_ROOT=tmp_path):
        assert client.get(f"/api/documents/{document.id}/pages").json()["signed"] is True
        refused = client.post(f"/api/documents/{document.id}/pages", {"order": [1]}, content_type="application/json")
        assert refused.status_code == 409 and refused.json()["signed"] is True
        with django_capture_on_commit_callbacks():
            accepted = client.post(f"/api/documents/{document.id}/pages", {"order": [1], "accept_signature_loss": True}, content_type="application/json")
    assert accepted.status_code == 202
    assert (tmp_path / DocumentVersion.objects.get(document=document).original_path).read_bytes() == signed


@pytest.mark.django_db
def test_uploading_a_new_version_validates_the_file(owner, tmp_path, django_capture_on_commit_callbacks):
    document = ready(owner, tmp_path, pdf(300))
    client = client_for(owner)
    with override_settings(MEDIA_ROOT=tmp_path):
        assert client.post(f"/api/documents/{document.id}/versions", {"file": SimpleUploadedFile("x.pdf", b"nope")}).status_code == 400
        with django_capture_on_commit_callbacks():
            response = client.post(f"/api/documents/{document.id}/versions", {"file": SimpleUploadedFile("corrected.pdf", pdf(310, 320))})
    assert response.status_code == 202
    document.refresh_from_db()
    assert (document.version_number, document.original_name, document.version_note) == (2, "corrected.pdf", "Uploaded new version")


@pytest.mark.django_db
def test_split_and_merge_create_new_documents_and_leave_sources_alone(owner, tmp_path, django_capture_on_commit_callbacks):
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    first = ready(owner, tmp_path, pdf(300, 400, 500), "first.pdf")
    second = ready(owner, tmp_path, pdf(600), "second.pdf")
    foreign = ready(other, tmp_path, pdf(700), "foreign.pdf")
    client = client_for(owner)
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        with django_capture_on_commit_callbacks() as callbacks:
            split = client.post(f"/api/documents/{first.id}/split", {"groups": [[0], [2, 1]]}, content_type="application/json")
        assert split.status_code == 201 and len(callbacks) == 2
        parts = [Document.objects.get(pk=item["id"]) for item in split.json()["documents"]]
        assert [part.title for part in parts] == ["first (1/2)", "first (2/2)"]
        assert [float(item.mediabox.width) for item in PdfReader(tmp_path / parts[1].original_path).pages] == [500, 400]
        assert client.post(f"/api/documents/{first.id}/split", {"groups": [[0, 1, 2]]}, content_type="application/json").status_code == 400

        merged = client.post("/api/documents/merge", {"document_ids": [str(second.id), str(first.id)]}, content_type="application/json")
        assert merged.status_code == 201
        result = Document.objects.get(pk=merged.json()["id"])
        assert result.title == "Merged: second + first"
        assert [float(item.mediabox.width) for item in PdfReader(tmp_path / result.original_path).pages] == [600, 300, 400, 500]
        assert client.post("/api/documents/merge", {"document_ids": [str(first.id), str(foreign.id)]}, content_type="application/json").status_code == 404
        assert client.get(f"/api/documents/{foreign.id}/pages").status_code == 404
    first.refresh_from_db()
    assert first.version_number == 1 and len(PdfReader(tmp_path / first.original_path).pages) == 3


@pytest.mark.django_db
def test_page_previews_render_and_purge_removes_every_version_file(owner, tmp_path, django_capture_on_commit_callbacks):
    document = ready(owner, tmp_path, pdf(300, 400))
    client = client_for(owner)
    with override_settings(MEDIA_ROOT=tmp_path):
        if shutil.which("gs"):  # Ghostscript is in the app image; plain CI runners may lack it
            preview = client.get(f"/api/documents/{document.id}/pages/2.png")
            assert preview.status_code == 200 and b"".join(preview.streaming_content).startswith(b"\x89PNG")
        assert client.get(f"/api/documents/{document.id}/pages/3.png").status_code == 404
        with django_capture_on_commit_callbacks():
            client.post(f"/api/documents/{document.id}/pages", {"order": [1]}, content_type="application/json")
        document.refresh_from_db()
        old = tmp_path / DocumentVersion.objects.get(document=document).original_path
        current = tmp_path / document.original_path
        assert old.exists() and current.exists()
        Document.objects.filter(pk=document.pk).update(trashed_at=timezone.now())
        document.refresh_from_db()
        job = record_purge(document)
        remove_job_media(job)
    assert not old.exists() and not current.exists()
    assert not (tmp_path / "previews" / str(document.id)[:2] / str(document.id)).exists()
    assert not DocumentVersion.objects.exists()


@pytest.mark.django_db
def test_backups_include_version_files_and_skip_page_previews(owner, tmp_path, django_capture_on_commit_callbacks):
    import shutil as shell

    from archive.backup import _copy_media

    document = ready(owner, tmp_path, pdf(300, 400))
    with override_settings(MEDIA_ROOT=tmp_path):
        with django_capture_on_commit_callbacks():
            client_for(owner).post(f"/api/documents/{document.id}/pages", {"order": [1]}, content_type="application/json")
        preview = tmp_path / "previews" / "ab" / "cached.png"
        preview.parent.mkdir(parents=True)
        preview.write_bytes(b"png")
        stage = tmp_path.parent / "stage"
        shell.rmtree(stage, ignore_errors=True)
        with patch("archive.backup._previous_files", return_value=(None, {})):
            copied = {item["path"] for item in _copy_media(stage)}
    version = DocumentVersion.objects.get(document=document)
    assert version.original_path in copied
    assert not any(path.startswith("previews/") for path in copied)


@pytest.mark.django_db
def test_failed_versions_can_be_recovered_and_stale_edits_are_refused(owner, tmp_path, django_capture_on_commit_callbacks):
    from datetime import timedelta

    from archive.models import ShareLink

    document = ready(owner, tmp_path, pdf(300, 400))
    ShareLink.objects.create(document=document, owner=owner, token_hash="x" * 64, expires_at=timezone.now() + timedelta(days=3))
    client = client_for(owner)
    with override_settings(MEDIA_ROOT=tmp_path):
        with django_capture_on_commit_callbacks():
            edited = client.post(f"/api/documents/{document.id}/pages", {"order": [1], "version_number": 1}, content_type="application/json")
        assert edited.json()["revoked_shares"] == 1
        assert not ShareLink.objects.filter(document=document, revoked_at__isnull=True).exists()
        Document.objects.filter(pk=document.pk).update(status=Document.Status.FAILED)  # the new version failed processing
        stale = client.post(f"/api/documents/{document.id}/pages", {"order": [0], "rotate": {"0": 90}, "version_number": 1}, content_type="application/json")
        assert stale.status_code == 409 and stale.json()["code"] == "stale"
        first = DocumentVersion.objects.get(document=document, number=1)
        with django_capture_on_commit_callbacks():
            restored = client.post(f"/api/documents/{document.id}/versions/{first.id}/restore", {"version_number": 2}, content_type="application/json")
        assert restored.status_code == 202
        Document.objects.filter(pk=document.pk).update(status=Document.Status.READY)
        (tmp_path / first.original_path).unlink()
        assert client.post(f"/api/documents/{document.id}/versions/{first.id}/restore").status_code == 503
        locked = ready(owner, tmp_path, pdf(300), "plain.pdf")
        (tmp_path / locked.original_path).write_bytes(b"%PDF-1.4 broken")
        assert client.post("/api/documents/merge", {"document_ids": [str(locked.id), str(document.id)]}, content_type="application/json").status_code == 400
