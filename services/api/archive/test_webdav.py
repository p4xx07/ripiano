from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import quote, unquote, urlsplit

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from archive.mail import encrypt_secret
from archive.models import Document, StorageSource
from archive.storage_sources import SourceError, preview, run
from archive.webdav import WebDAVBackend

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
BASE = "/remote.php/dav/files/ada/"


class FakeDav:
    """A small Nextcloud-like WebDAV server: PROPFIND (Depth 1), GET, MKCOL, MOVE, DELETE, with Basic auth."""

    def __init__(self, files):
        now = datetime.now(timezone.utc)
        self.files = {path: (body, now) for path, body in files.items()}
        self.folders = {""}
        for path in self.files:
            parts = path.split("/")[:-1]
            self.folders.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))

    def handler(self, request):
        if request.headers.get("Authorization") != httpx.BasicAuth("ada", "pw")._auth_header:
            return httpx.Response(401)
        path = unquote(urlsplit(str(request.url)).path)
        assert path.startswith(BASE)
        key = path[len(BASE):].rstrip("/")
        if request.method == "PROPFIND":
            if key not in self.folders:
                return httpx.Response(404)
            prefix = f"{key}/" if key else ""
            rows = [self._row(key, True)]
            rows += [self._row(folder, True) for folder in self.folders if folder and folder.startswith(prefix) and "/" not in folder[len(prefix):]]
            rows += [self._row(name, False) for name in self.files if name.startswith(prefix) and "/" not in name[len(prefix):]]
            return httpx.Response(207, content=f'<d:multistatus xmlns:d="DAV:">{"".join(rows)}</d:multistatus>')
        if request.method == "GET":
            return httpx.Response(200, content=self.files[key][0]) if key in self.files else httpx.Response(404)
        if request.method == "MKCOL":
            if key in self.folders:
                return httpx.Response(405)
            self.folders.add(key)
            return httpx.Response(201)
        if request.method == "MOVE":
            target = unquote(urlsplit(request.headers["Destination"]).path)[len(BASE):]
            if target.rsplit("/", 1)[0] not in self.folders:
                return httpx.Response(409)
            if target in self.files and request.headers.get("Overwrite") == "F":
                return httpx.Response(412)
            self.files[target] = (self.files.pop(key)[0], datetime.now(timezone.utc))
            return httpx.Response(201)
        if request.method == "DELETE":
            self.files.pop(key, None)
            return httpx.Response(204)
        return httpx.Response(405)

    def _row(self, key, folder):
        href = quote(BASE + key + ("/" if folder and key else ""))
        if folder:
            return f"<d:response><d:href>{href}</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        body, when = self.files[key]
        return (f"<d:response><d:href>{href}</d:href><d:propstat><d:prop><d:resourcetype/><d:getcontentlength>{len(body)}</d:getcontentlength>"
                f"<d:getlastmodified>{format_datetime(when, usegmt=True)}</d:getlastmodified><d:getetag>\"{hash(body) & 0xffff}\"</d:getetag>"
                f"</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>")


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_superuser("owner", password="secure-password-1")


@pytest.fixture(autouse=True)
def no_queue(monkeypatch):
    monkeypatch.setattr("archive.tasks.process_document.delay", lambda *args: None)


def make_source(owner, **values):
    defaults = dict(owner=owner, name="Cloud", kind=StorageSource.Kind.WEBDAV, endpoint="https://cloud.example.com" + BASE.rstrip("/"),
                    username="ada", secret=encrypt_secret("pw"), path="Scans", processed_path="Processed")
    return StorageSource.objects.create(**{**defaults, **values})


def backend(source, dav):
    return WebDAVBackend(source, transport=httpx.MockTransport(dav.handler))


@pytest.mark.django_db
def test_recursive_import_moves_into_dated_processed_folders(owner, tmp_path):
    dav = FakeDav({"Scans/bill one.pdf": PDF, "Scans/2026/marzo/è+più.pdf": PDF + b"%2", "Scans/drafts/x.pdf": PDF, "Scans/readme.txt": b"x"})
    source = make_source(owner, exclude_patterns="drafts/*")
    result = preview(source, backend(source, dav))
    assert sorted(item["path"] for item in result["matching"]) == ["2026/marzo/è+più.pdf", "bill one.pdf"]
    assert result["skipped"] == {"excluded by a pattern": 1, "unsupported file type": 1}
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(source, backend(source, dav), now=datetime(2026, 11, 17, tzinfo=timezone.utc)) == 2
        assert run(source, backend(source, dav)) == 0
    assert set(dav.files) == {"Scans/drafts/x.pdf", "Scans/readme.txt", "Processed/2026-11-17/bill one.pdf", "Processed/2026-11-17/2026/marzo/è+più.pdf"}
    assert set(Document.objects.values_list("source", flat=True)) == {Document.Source.WEBDAV}


@pytest.mark.django_db
def test_flat_listing_name_clash_and_grace_period(owner, tmp_path):
    dav = FakeDav({"Scans/a.pdf": PDF, "Scans/sub/b.pdf": PDF + b"%b", "Processed/2026-11-17/a.pdf": PDF + b"%old"})
    source = make_source(owner, recursive=False, retention_days=30)
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(source, backend(source, dav), now=datetime(2026, 11, 17, tzinfo=timezone.utc)) == 1
    assert "Scans/sub/b.pdf" in dav.files  # not recursive
    moved = [name for name in dav.files if name.startswith("Processed/2026-11-17/a")]
    assert len(moved) == 2  # the earlier file with the same name was kept
    for name in list(dav.files):
        if name.startswith("Processed/"):
            dav.files[name] = (dav.files[name][0], datetime.now(timezone.utc) - timedelta(days=31))
    with override_settings(MEDIA_ROOT=tmp_path):
        run(source, backend(source, dav))
    assert not any(name.startswith("Processed/") for name in dav.files)


@pytest.mark.django_db
def test_wrong_password_and_missing_folder_are_explained(owner):
    dav = FakeDav({"Scans/a.pdf": PDF})
    with pytest.raises(SourceError, match="user name or password"):
        wrong = make_source(owner, name="Wrong", secret=encrypt_secret("nope"))
        preview(wrong, backend(wrong, dav))
    with pytest.raises(SourceError, match="does not exist"):
        missing = make_source(owner, name="Missing", path="Nope")
        preview(missing, backend(missing, dav))
