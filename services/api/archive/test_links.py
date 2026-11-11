import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.models import Document, DocumentLink


def document(owner, title, letter):
    return Document.objects.create(
        owner=owner, title=title, original_name=f"{title}.pdf",
        original_path=f"originals/{title}.pdf", original_mime="application/pdf",
        original_sha256=letter * 64, original_size=1, status=Document.Status.READY,
    )


@pytest.mark.django_db
def test_document_links_are_reciprocal_and_owner_scoped():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    policy = document(owner, "Policy", "a")
    renewal = document(owner, "Renewal", "b")
    foreign = document(other, "Foreign", "c")
    client = Client()
    client.force_login(owner)
    url = f"/api/documents/{policy.id}/links"
    assert client.post(url, json.dumps({"document_id": str(policy.id)}), content_type="application/json").status_code == 400
    assert client.post(url, json.dumps({"document_id": "bad"}), content_type="application/json").status_code == 400
    assert client.post(url, json.dumps({"document_id": str(foreign.id)}), content_type="application/json").status_code == 404
    # A relationship inserted outside the API must not disclose another owner's title.
    left, right = sorted((policy.id, foreign.id))
    injected = DocumentLink.objects.create(left_id=left, right_id=right)
    assert client.get(url).json()["links"] == []
    injected.delete()
    assert client.post(url, json.dumps({"document_id": str(renewal.id)}), content_type="application/json").status_code == 201
    assert DocumentLink.objects.count() == 1
    assert client.post(f"/api/documents/{renewal.id}/links", json.dumps({"document_id": str(policy.id)}), content_type="application/json").status_code == 409
    assert [item["title"] for item in client.get(url).json()["links"]] == ["Renewal"]
    assert [item["title"] for item in client.get(f"/api/documents/{renewal.id}/links").json()["links"]] == ["Policy"]
    client.patch(f"/api/documents/{renewal.id}", json.dumps({"title": "Renewed policy"}), content_type="application/json")
    assert client.get(url).json()["links"][0]["title"] == "Renewed policy"
    client.force_login(other)
    assert client.get(url).status_code == 404
    assert client.post(url, json.dumps({"document_id": str(foreign.id)}), content_type="application/json").status_code == 404
    assert client.delete(f"{url}/{renewal.id}").status_code == 404
    assert client.post(f"/api/documents/{foreign.id}/links", json.dumps({"document_id": str(policy.id)}), content_type="application/json").status_code == 404
    client.force_login(owner)
    assert client.delete(f"/api/documents/{renewal.id}/links/{policy.id}").status_code == 200
    assert client.get(url).json()["links"] == []
    assert client.delete(f"{url}/{renewal.id}").status_code == 404


@pytest.mark.django_db
def test_document_links_hide_trash_and_reappear_after_restore():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    policy = document(owner, "Policy", "a")
    renewal = document(owner, "Renewal", "b")
    client = Client()
    client.force_login(owner)
    url = f"/api/documents/{policy.id}/links"
    assert client.post(url, json.dumps({"document_id": str(renewal.id)}), content_type="application/json").status_code == 201
    assert client.post(f"/api/documents/{renewal.id}/trash").status_code == 200
    assert client.get(url).json()["links"] == []
    assert client.get(f"/api/documents/{renewal.id}/links").status_code == 404
    assert client.post(url, json.dumps({"document_id": str(renewal.id)}), content_type="application/json").status_code == 404
    assert client.delete(f"{url}/{renewal.id}").status_code == 404
    assert DocumentLink.objects.count() == 1
    assert client.post(f"/api/documents/{renewal.id}/restore").status_code == 200
    assert [item["id"] for item in client.get(url).json()["links"]] == [str(renewal.id)]
