"""Safe conversion of existing custom-field values when their type changes."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.models import CustomField, CustomFieldValue, Document


def send(client, method, path, body):
    return getattr(client, method)(path, json.dumps(body), content_type="application/json")


def document(owner, name):
    return Document.objects.create(
        owner=owner, title=name, original_name=f"{name}.pdf",
        original_path=f"originals/{name}.pdf", original_mime="application/pdf",
        original_sha256="a" * 64, original_size=1, status=Document.Status.READY,
    )


@pytest.mark.django_db
def test_type_change_previews_invalid_values_and_saved_searches_before_atomic_conversion():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    first, second = document(owner, "First"), document(owner, "Second")
    client = Client()
    client.force_login(owner)
    field_id = send(client, "post", "/api/custom-fields", {"name": "Amount", "kind": "text"}).json()["id"]
    path = f"/api/custom-fields/{field_id}/change-type"
    def set_value(doc, value):
        return send(client, "put", f"/api/documents/{doc.id}/custom-fields/{field_id}", {"value": value})
    assert set_value(first, "001.20").status_code == 200
    assert set_value(second, "bad").status_code == 200
    assert client.get(path, {"kind": "wat"}).status_code == 400
    assert client.get(path, {"kind": "text"}).status_code == 400
    preview = client.get(path, {"kind": "number"}).json()
    assert (preview["value_count"], preview["changed_count"], preview["invalid_count"], preview["can_change"]) == (2, 1, 1, False)
    assert preview["invalid_examples"] == [{"document": "Second", "value": "bad"}]
    assert send(client, "post", path, {"kind": "number"}).status_code == 409
    assert CustomField.objects.get(pk=field_id).kind == "text"
    assert list(CustomFieldValue.objects.order_by("document__title").values_list("value", flat=True)) == ["001.20", "bad"]
    assert set_value(second, "3").status_code == 200
    query = send(client, "post", "/api/saved-views", {"name": "Amount query", "query": 'field:"Amount=001.20"'})
    assert query.status_code == 201
    preview = client.get(path, {"kind": "number"}).json()
    assert preview["saved_searches"] == ["Amount query"] and not preview["can_change"]
    assert send(client, "post", path, {"kind": "number"}).status_code == 409
    assert client.delete(f"/api/saved-views/{query.json()['id']}").status_code == 200
    client.force_login(other)
    assert client.get(path, {"kind": "number"}).status_code == 404
    assert send(client, "post", path, {"kind": "number"}).status_code == 404
    client.force_login(owner)
    result = send(client, "post", path, {"kind": "number"})
    assert result.status_code == 200
    assert result.json()["converted"] == 2 and result.json()["changed"] == 1
    assert CustomField.objects.get(pk=field_id).kind == "number"
    assert list(CustomFieldValue.objects.order_by("document__title").values_list("value", flat=True)) == ["1.2", "3"]
    assert client.get("/api/documents", {"custom_field_id": field_id, "custom_min": "1", "custom_max": "2"}).json()["counts"]["total"] == 1
    saved = send(client, "post", "/api/saved-views", {"name": "Amount range", "custom_field_id": field_id, "custom_min": "1", "custom_max": "4"})
    assert saved.status_code == 201
    assert client.get(path, {"kind": "text"}).json()["saved_searches"] == ["Amount range"]
    assert client.delete(f"/api/saved-views/{saved.json()['id']}").status_code == 200
    assert send(client, "post", path, {"kind": "text"}).status_code == 200
    assert CustomField.objects.get(pk=field_id).kind == "text"


@pytest.mark.django_db
def test_type_change_handles_boolean_and_trashed_values_without_partial_update():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    first, second = document(owner, "First"), document(owner, "Second")
    client = Client()
    client.force_login(owner)
    field_id = send(client, "post", "/api/custom-fields", {"name": "Approved", "kind": "text"}).json()["id"]
    first_path = f"/api/documents/{first.id}/custom-fields/{field_id}"
    second_path = f"/api/documents/{second.id}/custom-fields/{field_id}"
    path = f"/api/custom-fields/{field_id}/change-type"
    assert send(client, "put", first_path, {"value": "yes"}).status_code == 200
    assert send(client, "put", second_path, {"value": "maybe"}).status_code == 200
    assert client.post(f"/api/documents/{second.id}/trash").status_code == 200
    assert send(client, "post", path, {"kind": "boolean"}).status_code == 409
    assert list(CustomFieldValue.objects.order_by("document__title").values_list("value", flat=True)) == ["yes", "maybe"]
    assert client.post(f"/api/documents/{second.id}/restore").status_code == 200
    assert send(client, "put", second_path, {"value": "no"}).status_code == 200
    assert client.post(f"/api/documents/{second.id}/trash").status_code == 200
    result = send(client, "post", path, {"kind": "boolean"})
    assert result.status_code == 200 and result.json()["changed"] == 2
    assert client.get(f"/api/documents/{first.id}/custom-fields").json()["fields"][0]["value"] is True
    assert client.post(f"/api/documents/{second.id}/restore").status_code == 200
    assert client.get(f"/api/documents/{second.id}/custom-fields").json()["fields"][0]["value"] is False
    assert client.get("/api/documents", {"q": 'field:"Approved=yes"'}).json()["counts"]["total"] == 1
    assert client.get(path, {"kind": "date"}).json()["invalid_count"] == 2
    due_id = send(client, "post", "/api/custom-fields", {"name": "Due date", "kind": "text"}).json()["id"]
    assert send(client, "put", f"/api/documents/{first.id}/custom-fields/{due_id}", {"value": "2027-03-05"}).status_code == 200
    due_path = f"/api/custom-fields/{due_id}/change-type"
    assert client.get(due_path, {"kind": "date"}).json()["can_change"]
    assert send(client, "post", due_path, {"kind": "date"}).status_code == 200
    assert client.get("/api/documents", {"custom_field_id": due_id, "custom_min": "2027-03-01", "custom_max": "2027-03-31"}).json()["counts"]["total"] == 1
