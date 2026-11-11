import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.models import CustomField, CustomFieldValue, Document


def doc(owner, title, digest):
    return Document.objects.create(
        owner=owner, title=title, original_name=f"{title}.pdf",
        original_path=f"originals/{title}.pdf", original_mime="application/pdf",
        original_sha256=digest * 64, original_size=1, status=Document.Status.READY,
    )


def send(client, method, path, body):
    return getattr(client, method)(path, json.dumps(body), content_type="application/json")


@pytest.mark.django_db
def test_typed_custom_fields_validate_and_search_values():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    policy = doc(owner, "Policy", "a")
    other = doc(owner, "Other", "b")
    client = Client()
    client.force_login(owner)
    assert send(client, "post", "/api/custom-fields", {"name": "Bad", "kind": "json"}).status_code == 400
    fields = {}
    for name, kind in (("Policy no", "text"), ("Premium", "number"), ("Expires", "date"), ("Paid", "boolean")):
        response = send(client, "post", "/api/custom-fields", {"name": name, "kind": kind})
        assert response.status_code == 201
        fields[name] = response.json()["id"]
    assert send(client, "post", "/api/custom-fields", {"name": "policy NO", "kind": "text"}).status_code == 409
    assert len(client.get("/api/custom-fields").json()["fields"]) == 4
    def path(name):
        return f"/api/documents/{policy.id}/custom-fields/{fields[name]}"
    assert send(client, "put", path("Policy no"), {"value": " A-123 "}).json()["value"] == "A-123"
    assert send(client, "put", path("Premium"), {"value": "125.5000000"}).json()["value"] == "125.5"
    assert send(client, "put", path("Expires"), {"value": "2027-04-03"}).json()["value"] == "2027-04-03"
    assert send(client, "put", path("Paid"), {"value": False}).json()["value"] is False
    values = {item["name"]: item["value"] for item in client.get(f"/api/documents/{policy.id}/custom-fields").json()["fields"]}
    assert values == {"Policy no": "A-123", "Premium": "125.5", "Expires": "2027-04-03", "Paid": False}
    assert send(client, "put", path("Premium"), {"value": "NaN"}).status_code == 400
    assert send(client, "put", path("Premium"), {"value": "1.1234567"}).status_code == 400
    assert send(client, "put", path("Premium"), {"value": True}).status_code == 400
    assert send(client, "put", path("Expires"), {"value": "2027-02-30"}).status_code == 400
    assert send(client, "put", path("Paid"), {"value": "false"}).status_code == 400
    assert send(client, "put", path("Policy no"), {"value": " "}).status_code == 400
    assert CustomFieldValue.objects.count() == 4
    assert [item["id"] for item in client.get("/api/documents", {"q": "A-123"}).json()["documents"]] == [str(policy.id)]
    search = client.get("/api/documents", {"q": 'field:"Policy no=A-123"'}).json()["documents"]
    assert [item["id"] for item in search] == [str(policy.id)]
    assert search[0]["snippet_source"] == "field"
    assert "Policy no: A-123" in search[0]["snippet"]
    for query in ('field:"Premium=125.50"', 'field:"Expires=2027-04-03"', 'field:"Paid=no"'):
        assert [item["id"] for item in client.get("/api/documents", {"q": query}).json()["documents"]] == [str(policy.id)]
    assert client.get("/api/documents", {"custom_field_id": fields["Policy no"], "custom_value": "A-123"}).json()["counts"]["total"] == 1
    assert client.get("/api/documents", {"custom_field_id": fields["Premium"], "custom_value": "125.50"}).json()["counts"]["total"] == 1
    assert client.get("/api/documents", {"custom_field_id": fields["Expires"], "custom_value": "2027-04-03"}).json()["counts"]["total"] == 1
    assert client.get("/api/documents", {"custom_field_id": fields["Paid"], "custom_value": "no"}).json()["counts"]["total"] == 1
    assert client.get("/api/documents", {"custom_field_id": fields["Paid"], "custom_value": "maybe"}).status_code == 400
    assert client.get("/api/documents", {"q": 'field:"Premium=125"'}).json()["documents"] == []
    assert client.get("/api/documents", {"q": 'field:"Policy no"'}).status_code == 400
    assert client.get("/api/documents", {"q": 'field:"Unknown=A-123"'}).json()["documents"] == []
    assert client.get("/api/documents", {"q": 'field:"Policy no=A-123"', "sort": "title_asc"}).json()["counts"]["total"] == 1
    assert send(client, "patch", f"/api/custom-fields/{fields['Policy no']}", {"name": "Policy reference"}).status_code == 200
    assert client.get("/api/documents", {"q": 'field:"Policy reference=A-123"'}).json()["counts"]["total"] == 1
    assert client.delete(f"/api/custom-fields/{fields['Policy no']}").status_code == 409
    assert client.delete(path("Policy no")).status_code == 200
    assert client.delete(f"/api/custom-fields/{fields['Policy no']}").status_code == 200
    assert CustomField.objects.count() == 3
    assert client.get(f"/api/documents/{other.id}/custom-fields").json()["fields"][0]["value"] is None


@pytest.mark.django_db
def test_custom_fields_respect_owner_and_trash():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    foreign = get_user_model().objects.create_user("foreign", password="secure-password-2")
    policy = doc(owner, "Policy", "a")
    other = doc(foreign, "Other", "b")
    client = Client()
    client.force_login(owner)
    field_id = send(client, "post", "/api/custom-fields", {"name": "Secret reference", "kind": "text"}).json()["id"]
    assert send(client, "put", f"/api/documents/{policy.id}/custom-fields/{field_id}", {"value": "private-456"}).status_code == 200
    assert send(client, "put", f"/api/documents/{other.id}/custom-fields/{field_id}", {"value": "leak"}).status_code == 404
    client.force_login(foreign)
    assert client.get("/api/custom-fields").json()["fields"] == []
    assert client.get(f"/api/documents/{policy.id}/custom-fields").status_code == 404
    assert send(client, "put", f"/api/documents/{other.id}/custom-fields/{field_id}", {"value": "leak"}).status_code == 404
    assert client.get("/api/documents", {"q": "private-456"}).json()["documents"] == []
    client.force_login(owner)
    assert client.post(f"/api/documents/{policy.id}/trash").status_code == 200
    assert client.get(f"/api/documents/{policy.id}/custom-fields").status_code == 404
    assert send(client, "put", f"/api/documents/{policy.id}/custom-fields/{field_id}", {"value": "changed"}).status_code == 404
    assert client.get("/api/documents", {"q": "private-456"}).json()["documents"] == []
    assert client.post(f"/api/documents/{policy.id}/restore").status_code == 200
    assert client.get(f"/api/documents/{policy.id}/custom-fields").json()["fields"][0]["value"] == "private-456"
