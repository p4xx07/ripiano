"""API version 1 compatibility suite.

Drives a realistic scenario through the public API and compares every request/response shape with the
recorded contract (archive/api_contract_v1.json): fields may be added, but never removed or retyped, and
recorded routes never disappear. Regenerate after an intended, compatible change:

    RIPIANO_WRITE_CONTRACT=1 RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_api_contract.py
"""

import json
import os
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import URLPattern, get_resolver
from django.utils import timezone

from archive.api_contract import API_VERSION, CONTRACT_FILE, breaking_changes, load, merge, shape
from archive.models import Document

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


class Recorder:
    def __init__(self, client):
        self.client, self.operations = client, {}

    def call(self, method, template, path=None, body=None, files=None, status=200, **params):
        path = path or template
        if files:
            response = self.client.post(path, files)
        elif method == "get":
            response = self.client.get(path, params)
        else:
            response = getattr(self.client, method)(path, json.dumps(body or {}), content_type="application/json")
        assert response.status_code == status, (method, path, response.status_code, response.content[:300])
        data = response.json()
        key = f"{method.upper()} {template}"
        entry = self.operations.setdefault(key, {"status": status})
        entry["response"] = merge(entry["response"], shape(data)) if "response" in entry else shape(data)
        if body:
            entry["request"] = merge(entry["request"], shape(body)) if "request" in entry else shape(body)
        if files:
            entry["multipart"] = sorted(name for name, value in files.items() if hasattr(value, "read"))
        return data


def scenario(tmp_path, monkeypatch):
    monkeypatch.setattr("archive.ingestion.process_document.delay", lambda *args: None)
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    reader = get_user_model().objects.create_user("reader", password="secure-password-2")
    client = Client()
    client.force_login(owner)
    api = Recorder(client)
    with override_settings(MEDIA_ROOT=tmp_path):
        api.call("get", "/api/session")
        uploaded = api.call("post", "/api/documents", files={"document": SimpleUploadedFile("lease.pdf", PDF, "application/pdf")}, status=202)
        document_id = uploaded["id"]
        Document.objects.filter(pk=document_id).update(status=Document.Status.READY, extracted_text="Lease contract", processed_at=timezone.now())
        tag = api.call("post", "/api/tags", body={"name": "House", "color": "#3b7a57"}, status=201)
        api.call("patch", "/api/tags/{tag_id}", f"/api/tags/{tag['id']}", body={"description": "Home papers"})
        api.call("get", "/api/tags")
        sender = api.call("post", "/api/correspondents", body={"name": "Landlord"}, status=201)
        kind = api.call("post", "/api/document-types", body={"name": "Lease"}, status=201)
        api.call("get", "/api/correspondents")
        api.call("get", "/api/document-types")
        detail = f"/api/documents/{document_id}"
        api.call("patch", "/api/documents/{document_id}", detail, body={
            "title": "Lease 2026", "document_date": "2026-03-01", "tags": [tag["id"]], "correspondent_id": sender["id"], "document_type_id": kind["id"]})
        api.call("get", "/api/documents/{document_id}", detail)
        api.call("get", "/api/documents", q="lease")
        api.call("get", "/api/documents", tag_id=tag["id"])
        api.call("post", "/api/documents/{document_id}/notes", f"{detail}/notes", body={"body": "Signed copy is in the blue folder"}, status=201)
        api.call("get", "/api/documents/{document_id}/notes", f"{detail}/notes")
        api.call("get", "/api/documents/{document_id}/similar", f"{detail}/similar")
        api.call("post", "/api/documents/{document_id}/access", f"{detail}/access", body={"user_id": reader.pk, "level": "edit"}, status=201)
        api.call("get", "/api/documents/{document_id}/access", f"{detail}/access")
        view = api.call("post", "/api/saved-views", body={"name": "House papers", "query": "lease", "tag_id": tag["id"]}, status=201)
        api.call("get", "/api/saved-views")
        api.call("post", "/api/object-access/{kind}/{object_id}", f"/api/object-access/saved_view/{view['id']}",
                 body={"user_id": reader.pk, "level": "view"}, status=201)
        api.call("get", "/api/object-access/{kind}/{object_id}", f"/api/object-access/saved_view/{view['id']}")
        api.call("post", "/api/workflows", body={"name": "Tag leases", "trigger": "added", "filter_text": "lease", "add_tag_ids": [tag["id"]]}, status=201)
        api.call("get", "/api/workflows")
        api.call("get", "/api/overview")
        api.call("get", "/api/jobs")
        api.call("get", "/api/custom-fields")
        api.call("get", "/api/storage-paths")
        api.call("get", "/api/filing-model")
        api.call("get", "/api/mail")
        api.call("get", "/api/sources")
        api.call("get", "/api/semantic-search/available")
        api.call("get", "/api/people")
        api.call("get", "/api/agents")
        api.call("get", "/api/locations")
        api.call("get", "/api/trash-retention")
        token = api.call("post", "/api/account/tokens", body={"name": "Scanner script", "expires_in_days": 30, "password": "secure-password-1"}, status=201)
        api.call("get", "/api/account/tokens")
        api.call("post", "/api/documents/{document_id}/trash", f"{detail}/trash")
        api.call("post", "/api/documents/{document_id}/restore", f"{detail}/restore")
        api.call("get", "/api/documents/{document_id}/history", f"{detail}/history")

        # The recipient's side of sharing.
        client.force_login(reader)
        api.call("get", "/api/shared-filing")
        api.call("get", "/api/documents", view="shared")

        # A personal API token works on the same contract.
        token_client = Client(HTTP_AUTHORIZATION=f"Token {token['token']}")
        assert token_client.get("/api/documents").status_code == 200
    return api.operations


def _routes():
    routes = set()
    for pattern in get_resolver().url_patterns:
        if isinstance(pattern, URLPattern) and str(pattern.pattern).startswith("api/"):
            from archive.api_tokens import _methods

            path = "/" + re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", str(pattern.pattern))
            routes.update(f"{method.upper()} {path}" for method in _methods(pattern.callback))
    return routes


@pytest.mark.django_db
def test_api_v1_contract_is_kept(tmp_path, monkeypatch):
    operations = scenario(tmp_path, monkeypatch)
    if os.environ.get("RIPIANO_WRITE_CONTRACT") == "1":
        CONTRACT_FILE.write_text(json.dumps({"version": API_VERSION, "operations": dict(sorted(operations.items()))}, indent=1, sort_keys=False) + "\n")
        pytest.skip("Contract written")
    contract = load()
    assert contract["version"] == API_VERSION
    routes = _routes()
    problems = []
    for key, expected in contract["operations"].items():
        if key not in routes:
            problems.append(f"{key}: route removed")
            continue
        if key not in operations:
            problems.append(f"{key}: no longer exercised by the scenario")
            continue
        if operations[key]["status"] != expected["status"]:
            problems.append(f"{key}: status changed from {expected['status']} to {operations[key]['status']}")
        problems += [f"{key} response {item}" for item in breaking_changes(expected["response"], operations[key]["response"])]
        if expected.get("request") and operations[key].get("request"):
            # Request fields the contract documents must still be accepted.
            problems += [f"{key} request {item}" for item in breaking_changes(expected["request"], operations[key]["request"])]
    assert not problems, "Breaking API changes (bump the API version or restore compatibility):\n" + "\n".join(problems)


def test_breaking_change_rules():
    old = shape({"id": "x", "tags": [{"name": "a"}], "date": None, "count": 1})
    assert breaking_changes(old, shape({"id": "x", "tags": [{"name": "a", "color": "#fff"}], "date": "2026-01-01", "count": 1, "new": True})) == []
    assert breaking_changes(old, shape({"id": "x", "tags": [{"name": "a"}], "date": None})) == ["$.count: field removed"]
    assert breaking_changes(old, shape({"id": 5, "tags": [], "date": None, "count": 1})) == ["$.id: type changed from ['string'] to ['integer']"]
    assert breaking_changes(old, shape({"id": "x", "tags": [{"label": "a"}], "date": None, "count": 1})) == ["$.tags[].name: field removed"]
    assert merge(shape(None), shape("2026-01-01")) == {"type": ["null", "string"]}
    assert breaking_changes(shape({"id": "x"}), shape({"id": 1})) == ["$.id: type changed from ['string'] to ['integer']"]
    assert breaking_changes(shape({"id": "x"}), merge(shape({"id": "x"}), shape({"id": 1}))) == ["$.id: type changed from ['string'] to ['integer', 'string']"]
    assert breaking_changes(shape({"id": "x"}), shape({"id": None})) == ["$.id: type changed from ['string'] to ['null']"]


@pytest.mark.django_db
def test_schema_publishes_recorded_bodies():
    client = Client()
    client.force_login(get_user_model().objects.create_user("reader", password="secure-password-1"))
    schema = client.get("/api/schema.json").json()
    assert schema["info"]["version"] == API_VERSION
    patch = schema["paths"]["/api/documents/{document_id}"]["patch"]
    assert "title" in patch["requestBody"]["content"]["application/json"]["schema"]["properties"]
    response = patch["responses"]["200"]["content"]["application/json"]["schema"]
    assert {"id", "title", "tags", "correspondent"} <= set(response["properties"])
    upload = schema["paths"]["/api/documents"]["post"]
    assert "document" in upload["requestBody"]["content"]["multipart/form-data"]["schema"]["properties"]
    assert "202" in upload["responses"]
