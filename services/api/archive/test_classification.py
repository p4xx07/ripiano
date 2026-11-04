import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.classification import apply_rules
from archive.models import ClassificationRule, Document, DocumentTag, Tag
from archive.tasks import reclassify_owner


def ready_document(owner, text="Invoice for electricity"):
    return Document.objects.create(
        owner=owner, title="April bill", original_name="bill.pdf", original_path="originals/bill.pdf",
        original_mime="application/pdf", original_sha256="a" * 64, original_size=10,
        status=Document.Status.READY, extracted_text=text,
    )


@pytest.mark.django_db
def test_tag_keywords_file_existing_documents_and_correction_sticks():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    document = ready_document(owner)
    client = Client()
    client.force_login(owner)
    with patch("archive.metadata_views.reclassify_owner.delay"):
        response = client.post("/api/tags", json.dumps({"name": "Bills", "keywords": ["electricity"]}), content_type="application/json")
    assert response.status_code == 201
    tag_id = response.json()["id"]
    assert ClassificationRule.objects.filter(owner=owner, pattern="electricity").count() == 1

    reclassify_owner(owner.id)
    assert DocumentTag.objects.get(document=document).origin == DocumentTag.Origin.RULE
    assert client.get(f"/api/documents/{document.id}").json()["tags"][0]["name"] == "Bills"

    response = client.patch(f"/api/documents/{document.id}", json.dumps({"tags": []}), content_type="application/json")
    assert response.status_code == 200 and response.json()["tags"] == []
    apply_rules(document)
    assert not DocumentTag.objects.filter(document=document).exists()

    response = client.patch(f"/api/documents/{document.id}", json.dumps({"tags": [tag_id], "title": "New title", "document_date": "2026-04-01"}), content_type="application/json")
    assert response.status_code == 200
    assert response.json()["tags"][0]["origin"] == "manual"
    assert response.json()["document_date"] == "2026-04-01"
    apply_rules(document)
    assert DocumentTag.objects.get(document=document).origin == DocumentTag.Origin.MANUAL


@pytest.mark.django_db
def test_tags_and_rules_are_owner_isolated():
    alice = get_user_model().objects.create_user("alice", password="secure-password-1")
    bob = get_user_model().objects.create_user("bob", password="secure-password-2")
    tag = Tag.objects.create(owner=alice, name="Private")
    document = ready_document(alice)
    client = Client()
    client.force_login(bob)
    assert client.get("/api/tags").json()["tags"] == []
    assert client.patch(f"/api/documents/{document.id}", json.dumps({"tags": [str(tag.id)]}), content_type="application/json").status_code == 404
    assert client.post("/api/rules", json.dumps({"tag_id": str(tag.id), "pattern": "bill"}), content_type="application/json").status_code == 400

    own_document = ready_document(bob)
    assert client.patch(f"/api/documents/{own_document.id}", json.dumps({"tags": [str(tag.id)]}), content_type="application/json").status_code == 400
    assert not DocumentTag.objects.filter(document=own_document).exists()
