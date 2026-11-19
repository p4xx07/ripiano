import hashlib
import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from archive.models import Document, DocumentNote, DocumentTag, Tag


@pytest.mark.django_db
def test_collection_export_is_portable_and_isolated(tmp_path):
    owner = get_user_model().objects.create_user("export-owner", password="secure-password-1")
    other = get_user_model().objects.create_user("export-other", password="secure-password-2")
    media = tmp_path / "media"
    (media / "originals" / "ab").mkdir(parents=True)
    docs = []
    for index in range(2):
        content = f"%PDF-1.4\ndocument {index}".encode()
        relative = f"originals/ab/{index}.pdf"
        (media / relative).write_bytes(content)
        docs.append(Document.objects.create(
            owner=owner, title=f"Policy {index}", original_name=f"policy-{index}.pdf",
            original_path=relative, original_mime="application/pdf",
            original_sha256=hashlib.sha256(content).hexdigest(), original_size=len(content),
            status=Document.Status.READY,
        ))
    tag = Tag.objects.create(owner=owner, name="Policies")
    DocumentTag.objects.create(document=docs[0], tag=tag)
    DocumentNote.objects.create(document=docs[0], author=owner, body="Paper kept in box A")
    client = Client()
    client.force_login(owner)
    query = [("document_ids", str(item.id)) for item in reversed(docs)]
    with override_settings(MEDIA_ROOT=media):
        response = client.get("/api/documents/export", query)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"
        data = b"".join(response.streaming_content)
        with ZipFile(BytesIO(data)) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            assert manifest["kind"] == "document_collection"
            assert [entry["id"] for entry in manifest["documents"]] == [str(item.id) for item in reversed(docs)]
            for entry in manifest["documents"]:
                original = entry["files"]["original"]
                assert original["path"] == f"documents/{entry['id']}/original.pdf"
                assert hashlib.sha256(bundle.read(original["path"])).hexdigest() == original["sha256"]
            assert manifest["documents"][1]["metadata"]["tags"][0]["name"] == "Policies"
            assert manifest["documents"][1]["metadata"]["notes"][0]["body"] == "Paper kept in box A"
        assert client.get("/api/documents/export", [("document_ids", str(docs[0].id))] * 2).status_code == 400
        assert client.get("/api/documents/export", {"document_ids": "bad-id"}).status_code == 400
        assert client.get("/api/documents/export").status_code == 400
        assert client.get("/api/documents/export", [("document_ids", str(docs[0].id))] * 21).status_code == 400
        docs[1].trashed_at = timezone.now()
        docs[1].save(update_fields=["trashed_at"])
        assert client.get("/api/documents/export", query).status_code == 404
        docs[1].trashed_at = None
        docs[1].save(update_fields=["trashed_at"])
        (media / docs[1].original_path).write_bytes(b"changed")
        assert client.get("/api/documents/export", query).status_code == 503
        client.force_login(other)
        assert client.get("/api/documents/export", query).status_code == 404
