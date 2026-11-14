import hashlib
import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from archive.models import CustomField, CustomFieldValue, Document, DocumentLink, DocumentNote, DocumentTag, Location, PhysicalCopy, Tag


@pytest.mark.django_db
def test_document_export_contains_verified_original_and_readable_metadata(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    media = tmp_path / "media"
    (media / "originals" / "ab").mkdir(parents=True)
    (media / "archive" / "ab").mkdir(parents=True)
    original = b"%PDF-1.4\noriginal data"
    derived = b"%PDF-1.4\nsearchable data"
    (media / "originals" / "ab" / "policy.pdf").write_bytes(original)
    (media / "archive" / "ab" / "policy.pdf").write_bytes(derived)
    policy = Document.objects.create(
        owner=owner, title="Insurance policy", original_name="Policy 2026.pdf",
        original_path="originals/ab/policy.pdf", original_mime="application/pdf",
        original_sha256=hashlib.sha256(original).hexdigest(), original_size=len(original),
        archive_path="archive/ab/policy.pdf", extracted_text="Coverage until next year",
        status=Document.Status.READY,
    )
    renewal = Document.objects.create(
        owner=owner, title="Renewal", original_name="renewal.pdf",
        original_path="originals/ab/renewal.pdf", original_mime="application/pdf",
        original_sha256="b" * 64, original_size=1,
    )
    tag = Tag.objects.create(owner=owner, name="Insurance")
    DocumentTag.objects.create(document=policy, tag=tag)
    DocumentNote.objects.create(document=policy, author=owner, body="Keep the paper original")
    shelf = Location.objects.create(owner=owner, name="Home shelf")
    PhysicalCopy.objects.create(document=policy, sticker_code="R-POLICY1", location=shelf)
    left, right = sorted((policy.id, renewal.id))
    DocumentLink.objects.create(left_id=left, right_id=right)
    field = CustomField.objects.create(owner=owner, name="Policy number", kind=CustomField.Kind.TEXT)
    CustomFieldValue.objects.create(document=policy, field=field, value="POL-2026")
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=media):
        response = client.get(f"/api/documents/{policy.id}/export")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"
        assert f"ripiano-{policy.id}.zip" in response["Content-Disposition"]
        data = b"".join(response.streaming_content)
    with ZipFile(BytesIO(data)) as bundle:
        assert set(bundle.namelist()) == {"original.pdf", "searchable.pdf", "ocr.txt", "manifest.json"}
        assert bundle.read("original.pdf") == original
        assert bundle.read("searchable.pdf") == derived
        assert bundle.read("ocr.txt") == b"Coverage until next year"
        manifest = json.loads(bundle.read("manifest.json"))
    assert manifest["format_version"] == 1
    assert manifest["document"]["title"] == "Insurance policy"
    assert manifest["document"]["tags"][0]["name"] == "Insurance"
    assert manifest["document"]["notes"][0]["body"] == "Keep the paper original"
    assert manifest["document"]["physical_copies"][0]["location"] == ["Home shelf"]
    assert manifest["document"]["related_documents"] == [{"id": str(renewal.id), "title": "Renewal"}]
    assert manifest["document"]["custom_fields"] == [{"name": "Policy number", "kind": "text", "value": "POL-2026"}]
    assert manifest["files"]["original"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert manifest["files"]["searchable_pdf"]["sha256"] == hashlib.sha256(derived).hexdigest()
    client.force_login(other)
    assert client.get(f"/api/documents/{policy.id}/export").status_code == 404


@pytest.mark.django_db
def test_document_export_rejects_missing_or_changed_original_and_trash(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    media = tmp_path / "media"
    original_path = media / "originals" / "ab" / "policy.pdf"
    original_path.parent.mkdir(parents=True)
    original_path.write_bytes(b"%PDF-1.4\noriginal data")
    policy = Document.objects.create(
        owner=owner, title="Insurance policy", original_name="policy.pdf",
        original_path="originals/ab/policy.pdf", original_mime="application/pdf",
        original_sha256=hashlib.sha256(original_path.read_bytes()).hexdigest(), original_size=original_path.stat().st_size,
        status=Document.Status.READY,
    )
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=media):
        original_path.write_bytes(b"changed")
        assert client.get(f"/api/documents/{policy.id}/export").status_code == 503
        original_path.unlink()
        assert client.get(f"/api/documents/{policy.id}/export").status_code == 503
        assert client.post(f"/api/documents/{policy.id}/trash").status_code == 200
        assert client.get(f"/api/documents/{policy.id}/export").status_code == 404
