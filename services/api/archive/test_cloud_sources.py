import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from archive.cloud_sources import DropboxBackend, GoogleDriveBackend, OneDriveBackend
from archive.mail import encrypt_secret
from archive.models import CloudApp, Document, StorageSource
from archive.storage_sources import SourceError, preview, run

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
NOW = "2026-11-17T09:00:00Z"


def token_endpoint(request, rotated=None):
    form = parse_qs(request.content.decode())
    if form.get("client_secret") != ["app-secret"] or form.get("refresh_token") not in (["refresh-1"], ["refresh-2"]):
        return httpx.Response(400, json={"error": "invalid_grant"})
    return httpx.Response(200, json={"access_token": "access-1", **({"refresh_token": rotated} if rotated else {})})


class FakeGoogle:
    def __init__(self):
        self.items = {"root": {"id": "root", "name": "", "mimeType": "application/vnd.google-apps.folder", "parents": []}}
        self.content, self.counter = {}, 0

    def add(self, name, parent="root", mime="application/pdf", body=PDF):
        self.counter += 1
        item_id = f"id{self.counter}"
        self.items[item_id] = {"id": item_id, "name": name, "mimeType": mime, "parents": [parent], "size": str(len(body)),
                               "modifiedTime": NOW, "md5Checksum": f"md5-{item_id}", "trashed": False}
        self.content[item_id] = body
        return item_id

    def handler(self, request):
        url = urlsplit(str(request.url))
        if url.netloc == "oauth2.googleapis.com":
            return token_endpoint(request)
        assert request.headers["Authorization"] == "Bearer access-1"
        params = parse_qs(url.query)
        parts = url.path.split("/")
        if url.path == "/drive/v3/files" and request.method == "GET":
            parent = params["q"][0].split("'")[1]
            found = [dict(item) for item in self.items.values() if parent in item["parents"] and not item.get("trashed")]
            return httpx.Response(200, json={"files": found})
        if url.path == "/drive/v3/files" and request.method == "POST":
            body = json.loads(request.content)
            item_id = self.add(body["name"], body["parents"][0], body["mimeType"], b"")
            return httpx.Response(200, json={"id": item_id})
        item_id = parts[4]
        if request.method == "GET" and len(parts) == 6 and parts[5] == "export":
            return httpx.Response(200, content=PDF + b"%exported")
        if request.method == "GET":
            return httpx.Response(200, content=self.content[item_id])
        if request.method == "PATCH":
            body = json.loads(request.content or b"{}")
            item = self.items[item_id]
            if body.get("trashed"):
                item["trashed"] = True
            if "addParents" in params:
                item["parents"] = [params["addParents"][0]]
            if body.get("name"):
                item["name"] = body["name"]
            return httpx.Response(200, json={"id": item_id})
        return httpx.Response(405)

    def path_of(self, item_id):
        names = []
        while item_id != "root":
            item = self.items[item_id]
            names.append(item["name"])
            item_id = item["parents"][0]
        return "/".join(reversed(names))

    def visible_files(self):
        return sorted(self.path_of(key) for key, item in self.items.items()
                      if key != "root" and item["mimeType"] != "application/vnd.google-apps.folder" and not item.get("trashed"))


@pytest.fixture
def owner(db):
    CloudApp.objects.create(provider="gdrive", client_id="google-app", client_secret=encrypt_secret("app-secret"))
    CloudApp.objects.create(provider="onedrive", client_id="ms-app", client_secret=encrypt_secret("app-secret"))
    CloudApp.objects.create(provider="dropbox", client_id="dbx-app", client_secret=encrypt_secret("app-secret"))
    return get_user_model().objects.create_user("owner", password="secure-password-1")


@pytest.fixture(autouse=True)
def no_queue(monkeypatch):
    monkeypatch.setattr("archive.tasks.process_document.delay", lambda *args: None)


def source_for(owner, kind, **values):
    return StorageSource.objects.create(**{**dict(owner=owner, name=kind, kind=kind, secret=encrypt_secret("refresh-1"), path="Scans",
                                                  processed_path="Processed"), **values})


@pytest.mark.django_db
def test_google_drive_recursive_import_exports_docs_and_moves(owner, tmp_path):
    google = FakeGoogle()
    scans = google.add("Scans", mime="application/vnd.google-apps.folder")
    google.add("bill.pdf", scans)
    sub = google.add("2026", scans, mime="application/vnd.google-apps.folder")
    google.add("Contract", sub, mime="application/vnd.google-apps.document")
    google.add("form", scans, mime="application/vnd.google-apps.form")
    source = source_for(owner, "gdrive")
    transport = httpx.MockTransport(google.handler)
    result = preview(source, GoogleDriveBackend(source, transport))
    assert sorted(item["path"] for item in result["matching"]) == ["2026/Contract.pdf", "bill.pdf"]
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(source, GoogleDriveBackend(source, transport), now=datetime(2026, 11, 17, tzinfo=timezone.utc)) == 2
        assert run(source, GoogleDriveBackend(source, transport)) == 0
    assert google.visible_files() == ["Processed/2026-11-17/2026/Contract", "Processed/2026-11-17/bill.pdf", "Scans/form"]  # the form stays
    assert sorted(Document.objects.values_list("original_name", flat=True)) == ["Contract.pdf", "bill.pdf"]
    assert set(Document.objects.values_list("source", flat=True)) == {Document.Source.GDRIVE}


@pytest.mark.django_db
def test_google_drive_delete_mode_uses_the_trash(owner, tmp_path):
    google = FakeGoogle()
    scans = google.add("Scans", mime="application/vnd.google-apps.folder")
    bill = google.add("bill.pdf", scans)
    source = source_for(owner, "gdrive", after=StorageSource.After.DELETE)
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(source, GoogleDriveBackend(source, httpx.MockTransport(google.handler))) == 1
    assert google.items[bill]["trashed"] is True


class FakeOneDrive:
    def __init__(self, files):
        self.files = dict(files)  # path -> bytes
        self.folders = {"", "Scans"} | {"/".join(path.split("/")[:index]) for path in files for index in range(1, path.count("/") + 1)}
        self.ids = {}

    def _id(self, path):
        return self.ids.setdefault(path, f"item{len(self.ids)}")

    def _path(self, item_id):
        return next(path for path, value in self.ids.items() if value == item_id)

    def handler(self, request):
        url = urlsplit(str(request.url))
        if url.netloc == "login.microsoftonline.com":
            return token_endpoint(request, rotated="refresh-2")
        if url.netloc == "download.example":
            assert "Authorization" not in request.headers  # never sent to the pre-authenticated address
            return httpx.Response(200, content=self.files[unquote(url.path.lstrip("/"))])
        assert request.headers["Authorization"] == "Bearer access-1"
        path = unquote(url.path)
        if path.startswith("/v1.0/me/drive/items/") and path.endswith("/content"):
            return httpx.Response(302, headers={"Location": f"https://download.example/{self._path(path.split('/')[5])}"})
        if request.method == "GET" and path.endswith(":/children") or path == "/v1.0/me/drive/root/children":
            folder = "" if path == "/v1.0/me/drive/root/children" else path[len("/v1.0/me/drive/root:/"):-len(":/children")]
            if request.method == "POST":
                return self._create(folder, request)
            if folder not in self.folders:
                return httpx.Response(404)
            prefix = f"{folder}/" if folder else ""
            values = [{"id": self._id(name), "name": name[len(prefix):], "folder": {}} for name in self.folders if name and name.startswith(prefix) and "/" not in name[len(prefix):]]
            values += [{"id": self._id(name), "name": name[len(prefix):], "file": {}, "size": len(body), "lastModifiedDateTime": NOW, "cTag": f"c{len(body)}"}
                       for name, body in self.files.items() if name.startswith(prefix) and "/" not in name[len(prefix):]]
            return httpx.Response(200, json={"value": values})
        if request.method == "POST" and path.endswith("/children"):
            folder = "" if path == "/v1.0/me/drive/root/children" else path[len("/v1.0/me/drive/root:/"):-len(":/children")]
            return self._create(folder, request)
        if request.method == "GET" and path.startswith("/v1.0/me/drive/root:/"):
            return httpx.Response(200, json={"id": self._id(path[len("/v1.0/me/drive/root:/"):].rstrip(":"))})
        if request.method == "PATCH":
            item = self._path(path.split("/")[5])
            body = json.loads(request.content)
            target = f"{self._path(body['parentReference']['id'])}/{body['name']}"
            self.files[target] = self.files.pop(item)
            return httpx.Response(200, json={})
        if request.method == "DELETE":
            self.files.pop(self._path(path.split("/")[5]), None)
            return httpx.Response(204)
        return httpx.Response(405)

    def _create(self, folder, request):
        name = json.loads(request.content)["name"]
        full = f"{folder}/{name}" if folder else name
        if full in self.folders:
            return httpx.Response(409)
        self.folders.add(full)
        return httpx.Response(201, json={"id": self._id(full)})


@pytest.mark.django_db
def test_onedrive_import_moves_and_keeps_the_rotated_refresh_token(owner, tmp_path):
    onedrive = FakeOneDrive({"Scans/bill.pdf": PDF, "Scans/2026/deep.pdf": PDF + b"%2", "Scans/notes.txt": b"x"})
    source = source_for(owner, "onedrive")
    transport = httpx.MockTransport(onedrive.handler)
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(source, OneDriveBackend(source, transport), now=datetime(2026, 11, 17, tzinfo=timezone.utc)) == 2
    assert set(onedrive.files) == {"Scans/notes.txt", "Processed/2026-11-17/bill.pdf", "Processed/2026-11-17/2026/deep.pdf"}
    source.refresh_from_db()
    from archive.mail import decrypt_secret
    assert decrypt_secret(source.secret) == "refresh-2"
    missing = source_for(owner, "onedrive", name="Missing", path="Nope")
    with pytest.raises(SourceError, match="does not exist"):
        preview(missing, OneDriveBackend(missing, transport))


class FakeDropbox:
    def __init__(self, files):
        self.files = dict(files)

    def handler(self, request):
        url = urlsplit(str(request.url))
        if url.path == "/oauth2/token":
            return token_endpoint(request)
        assert request.headers["Authorization"] == "Bearer access-1"
        if url.path == "/2/files/download":
            return httpx.Response(200, content=self.files[json.loads(request.headers["Dropbox-API-Arg"])["path"].lstrip("/")])
        body = json.loads(request.content)
        if url.path == "/2/files/list_folder":
            prefix = body["path"].lstrip("/")
            if prefix and not any(name.startswith(prefix + "/") for name in self.files):
                return httpx.Response(409, json={"error_summary": "path/not_found/"})
            names = sorted(name for name in self.files if name.startswith(prefix + "/") and (body["recursive"] or "/" not in name[len(prefix) + 1:]))
            entries = [{".tag": "file", "path_display": "/" + name, "size": len(self.files[name]), "server_modified": NOW, "content_hash": f"h{len(self.files[name])}"} for name in names]
            return httpx.Response(200, json={"entries": entries[:1], "has_more": len(entries) > 1, "cursor": json.dumps(entries[1:])})
        if url.path == "/2/files/list_folder/continue":
            entries = json.loads(body["cursor"])
            return httpx.Response(200, json={"entries": entries, "has_more": False, "cursor": "end"})
        if url.path == "/2/files/move_v2":
            self.files[body["to_path"].lstrip("/")] = self.files.pop(body["from_path"].lstrip("/"))
            return httpx.Response(200, json={})
        if url.path == "/2/files/delete_v2":
            self.files.pop(body["path"].lstrip("/"), None)
            return httpx.Response(200, json={})
        return httpx.Response(404)


@pytest.mark.django_db
def test_dropbox_paginated_listing_flat_and_recursive(owner, tmp_path):
    dropbox = FakeDropbox({"Scans/bill.pdf": PDF, "Scans/receipt.pdf": PDF + b"%r", "Scans/2026/deep.pdf": PDF + b"%2"})
    flat = source_for(owner, "dropbox", name="Flat", recursive=False, after=StorageSource.After.KEEP)
    transport = httpx.MockTransport(dropbox.handler)
    assert sorted(item["path"] for item in preview(flat, DropboxBackend(flat, transport))["matching"]) == ["bill.pdf", "receipt.pdf"]
    deep = source_for(owner, "dropbox", name="Deep")
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(deep, DropboxBackend(deep, transport), now=datetime(2026, 11, 17, tzinfo=timezone.utc)) == 3
    assert sorted(dropbox.files) == ["Processed/2026-11-17/2026/deep.pdf", "Processed/2026-11-17/bill.pdf", "Processed/2026-11-17/receipt.pdf"]


@pytest.mark.django_db
def test_connect_account_flow_and_sign_in_app_settings(owner, monkeypatch):
    client = Client()
    client.force_login(owner)
    created = client.post("/api/sources", {"name": "My Drive", "kind": "gdrive", "path": "Scans", "processed_path": "Processed"},
                          content_type="application/json")
    assert created.status_code == 201 and created.json()["connected"] is False
    source_id = created.json()["id"]
    with pytest.raises(SourceError, match="Connect the account first"):
        preview(StorageSource.objects.get(pk=source_id))
    start = client.post(f"/api/sources/{source_id}/connect").json()["url"]
    assert start.startswith("https://accounts.google.com/") and "client_id=google-app" in start and "access_type=offline" in start
    state = parse_qs(urlsplit(start).query)["state"][0]
    monkeypatch.setattr("archive.cloud_sources.exchange_code", lambda provider, code, transport=None: f"refresh-for-{code}")
    done = client.get("/api/sources/oauth/callback", {"state": state, "code": "abc"})
    assert done.status_code == 302 and "source_connected=My+Drive" in done["Location"]
    assert client.get("/api/sources").json()["sources"][0]["connected"] is True
    stranger = get_user_model().objects.create_user("stranger", password="secure-password-2")
    client.force_login(stranger)
    assert "another Ripiano account" in unquote(client.get("/api/sources/oauth/callback", {"state": state, "code": "x"})["Location"]).replace("+", " ")
    # Sign-in apps: only the archive owner changes them; secrets are never returned.
    assert client.put("/api/source-apps", {"provider": "dropbox", "client_id": "x", "client_secret": "y"}, content_type="application/json").status_code == 403
    admin = get_user_model().objects.create_superuser("admin", password="secure-password-3")
    client.force_login(admin)
    listed = client.put("/api/source-apps", {"provider": "dropbox", "client_id": "dbx-2", "client_secret": "s2"}, content_type="application/json").json()
    assert listed["redirect_uri"].endswith("/api/sources/oauth/callback")
    dropbox = next(item for item in listed["providers"] if item["provider"] == "dropbox")
    assert dropbox == {**dropbox, "client_id": "dbx-2", "configured": True} and "s2" not in json.dumps(listed)
    assert client.put("/api/source-apps", {"provider": "dropbox", "client_id": ""}, content_type="application/json").status_code == 200
    assert not CloudApp.objects.filter(provider="dropbox").exists()


@pytest.mark.django_db
def test_gmail_and_outlook_clients_are_the_fallback(owner):
    from archive.cloud_sources import client_for

    CloudApp.objects.all().delete()
    with override_settings(RIPIANO_MAIL_OAUTH={"gmail": ("gmail-id", "gmail-secret")}):
        assert client_for("gdrive") == ("gmail-id", "gmail-secret")
        assert client_for("onedrive") == (None, None) and client_for("dropbox") == (None, None)
