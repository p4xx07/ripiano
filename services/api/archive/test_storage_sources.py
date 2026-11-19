from datetime import date, datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from archive.mail import encrypt_secret
from archive.models import Document, DocumentTag, StorageSource, StorageSourceSeen, Tag
from archive.storage_sources import S3Backend, SourceError, check_endpoint, preview, run

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


class FakeBucket:
    """In-memory S3: ListObjectsV2 (with or without delimiter), GetObject, CopyObject, DeleteObject."""

    def __init__(self, objects):
        now = datetime.now(timezone.utc)
        self.objects = {key: (body, now) for key, body in objects.items()}
        self.fail_copy = False

    def handler(self, request):
        assert request.headers["Authorization"].startswith("AWS4-HMAC-SHA256 ")
        path = unquote(urlsplit(str(request.url)).path)
        key = path.split("/", 2)[2] if path.count("/") >= 2 else ""
        if request.method == "GET" and not key:
            prefix = request.url.params.get("prefix", "")
            flat = request.url.params.get("delimiter") == "/"
            rows = ""
            for name, (body, when) in sorted(self.objects.items()):
                if not name.startswith(prefix) or (flat and "/" in name[len(prefix):]):
                    continue
                rows += (f"<Contents><Key>{name}</Key><ETag>\"{len(body)}-{hash(body) & 0xffff}\"</ETag><Size>{len(body)}</Size>"
                         f"<LastModified>{when.strftime('%Y-%m-%dT%H:%M:%S.000Z')}</LastModified></Contents>")
            return httpx.Response(200, content=f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{rows}<IsTruncated>false</IsTruncated></ListBucketResult>')
        if request.method == "GET":
            return httpx.Response(200, content=self.objects[key][0]) if key in self.objects else httpx.Response(404)
        if request.method == "PUT":
            if self.fail_copy:
                return httpx.Response(200, content=b"<Error><Code>InternalError</Code></Error>")
            source = unquote(request.headers["x-amz-copy-source"]).split("/", 2)[2]
            self.objects[key] = (self.objects[source][0], datetime.now(timezone.utc))
            return httpx.Response(200, content=b"<CopyObjectResult/>")
        if request.method == "DELETE":
            self.objects.pop(key, None)
            return httpx.Response(204)
        return httpx.Response(405)


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_superuser("owner", password="secure-password-1")


@pytest.fixture(autouse=True)
def no_queue(monkeypatch):
    monkeypatch.setattr("archive.tasks.process_document.delay", lambda *args: None)


def make_source(owner, **values):
    defaults = dict(owner=owner, name="Scans", endpoint="http://127.0.0.1:9000", bucket="scans", username="key",
                    secret=encrypt_secret("secret"), path="inbox/")
    return StorageSource.objects.create(**{**defaults, **values})


def backend(source, bucket):
    return S3Backend(source, transport=httpx.MockTransport(bucket.handler))


@pytest.mark.django_db
def test_recursive_and_flat_imports_move_files_and_assign_filing(owner, tmp_path):
    bills = Tag.objects.create(owner=owner, name="Bills")
    objects = {"inbox/bill one.pdf": PDF, "inbox/sub/è+più.pdf": PDF + b"%2", "inbox/notes.exe": b"MZ", "inbox/folder/": b"", "other/keep.pdf": PDF}
    with override_settings(MEDIA_ROOT=tmp_path):
        flat_bucket = FakeBucket(objects)
        flat = make_source(owner, name="Flat", recursive=False)
        assert run(flat, backend(flat, flat_bucket), now=datetime(2026, 11, 17, tzinfo=timezone.utc)) == 1
        assert "inbox/sub/è+più.pdf" in flat_bucket.objects and "processed/2026-11-17/bill one.pdf" in flat_bucket.objects

        deep_bucket = FakeBucket(objects)
        deep = make_source(owner, name="Deep")
        deep.tags.add(bills)
        assert run(deep, backend(deep, deep_bucket), now=datetime(2026, 11, 17, tzinfo=timezone.utc)) == 2
        assert run(deep, backend(deep, deep_bucket)) == 0
    assert set(deep_bucket.objects) == {"inbox/notes.exe", "inbox/folder/", "other/keep.pdf",
                                        "processed/2026-11-17/bill one.pdf", "processed/2026-11-17/sub/è+più.pdf"}
    imported = Document.objects.filter(owner=owner, original_name="è+più.pdf").get()
    assert DocumentTag.objects.filter(document=imported, tag=bills, origin=DocumentTag.Origin.SOURCE).exists()


@pytest.mark.django_db
def test_filters_and_preview_change_nothing(owner):
    bucket = FakeBucket({"inbox/fattura-01.pdf": PDF, "inbox/fattura-02.jpg": b"\xff\xd8", "inbox/receipt.pdf": PDF,
                         "inbox/drafts/fattura-03.pdf": PDF, "inbox/huge-fattura.pdf": PDF * 400})
    source = make_source(owner, include_patterns="fattura*, huge*", exclude_patterns="drafts/*", file_types=["pdf"], max_size_mb=1)
    with override_settings(RIPIANO_MAX_UPLOAD_BYTES=50_000):
        result = preview(source, backend(source, bucket))
    assert [item["path"] for item in result["matching"]] == ["fattura-01.pdf"]
    assert result["skipped"] == {"file type not selected": 1, "name does not match": 1, "excluded by a pattern": 1, "too large": 1}
    assert len(bucket.objects) == 5 and Document.objects.count() == 0
    source.modified_after = date.today() + timedelta(days=1)
    with override_settings(RIPIANO_MAX_UPLOAD_BYTES=50_000):
        assert preview(source, backend(source, bucket))["skipped"].get("older than the date filter") == 1


@pytest.mark.django_db
def test_keep_and_delete_modes_never_import_twice_even_after_the_document_is_gone(owner, tmp_path):
    bucket = FakeBucket({"inbox/a.pdf": PDF, "inbox/b.pdf": PDF + b"%b"})
    with override_settings(MEDIA_ROOT=tmp_path):
        keep = make_source(owner, name="Keep", after=StorageSource.After.KEEP)
        assert run(keep, backend(keep, bucket)) == 2 and set(bucket.objects) == {"inbox/a.pdf", "inbox/b.pdf"}
        Document.objects.all().delete()
        assert run(keep, backend(keep, bucket)) == 0  # remembered, not re-imported
        assert preview(keep, backend(keep, bucket))["already_imported"] == 2
        delete = make_source(owner, name="Delete", after=StorageSource.After.DELETE)
        assert run(delete, backend(delete, bucket)) == 2 and bucket.objects == {}


@pytest.mark.django_db
def test_failed_move_is_finished_later_without_a_second_import_and_old_processed_files_expire(owner, tmp_path):
    bucket = FakeBucket({"inbox/bill.pdf": PDF})
    bucket.fail_copy = True
    source = make_source(owner, retention_days=30)
    with override_settings(MEDIA_ROOT=tmp_path):
        with pytest.raises(SourceError):
            run(source, backend(source, bucket))
        bucket.fail_copy = False
        assert run(source, backend(source, bucket)) == 0
    assert Document.objects.count() == 1 and "inbox/bill.pdf" not in bucket.objects
    now = datetime.now(timezone.utc)
    bucket.objects["processed/2026-09-01/old.pdf"] = (PDF, now - timedelta(days=31))
    run(source, backend(source, bucket), now=now)
    assert not any(key.endswith("old.pdf") for key in bucket.objects) and len(bucket.objects) == 1


@pytest.mark.django_db
def test_only_the_archive_owner_may_use_home_network_addresses(owner):
    person = get_user_model().objects.create_user("person", password="secure-password-2")
    check_endpoint(make_source(owner, endpoint="http://127.0.0.1:9000"))
    with pytest.raises(SourceError, match="archive owner"):
        check_endpoint(make_source(person, name="Mine", endpoint="http://127.0.0.1:9000"))
    with pytest.raises(SourceError):
        check_endpoint(make_source(person, name="Ftp", endpoint="ftp://example.com"))


@pytest.mark.django_db
def test_api_keeps_the_secret_write_only_and_validates(owner, monkeypatch):
    client = Client()
    client.force_login(owner)
    body = {"name": "NAS bucket", "endpoint": "http://127.0.0.1:9000/", "bucket": "scans", "username": "key", "secret": "s3cret",
            "path": "/inbox", "file_types": ["pdf"], "after": "move", "processed_path": "processed/"}
    created = client.post("/api/sources", body, content_type="application/json")
    assert created.status_code == 201
    data = created.json()
    assert data["has_secret"] and "secret" not in data and data["endpoint"] == "http://127.0.0.1:9000" and data["path"] == "inbox"
    assert "s3cret" not in client.get("/api/sources").content.decode()
    assert StorageSource.objects.get().secret != "s3cret"
    source_id = data["id"]
    assert client.patch(f"/api/sources/{source_id}", {"poll_minutes": 2}, content_type="application/json").status_code == 400
    assert client.patch(f"/api/sources/{source_id}", {"file_types": ["exe"]}, content_type="application/json").status_code == 400
    assert client.patch(f"/api/sources/{source_id}", {"path": "processed/inbox"}, content_type="application/json").status_code == 400
    assert client.post("/api/sources", {**body}, content_type="application/json").json()["error"] == "You already have a source with this name"
    assert client.post("/api/sources", {**body, "name": "No secret", "secret": ""}, content_type="application/json").status_code == 400
    kept = client.patch(f"/api/sources/{source_id}", {"name": "Renamed"}, content_type="application/json").json()
    assert kept["has_secret"] and kept["name"] == "Renamed"
    queued = []
    monkeypatch.setattr("archive.tasks.poll_storage_source.delay", lambda value: queued.append(value))
    assert client.post(f"/api/sources/{source_id}/run").status_code == 202 and queued == [source_id]
    stranger = get_user_model().objects.create_user("stranger", password="secure-password-3")
    client.force_login(stranger)
    assert client.patch(f"/api/sources/{source_id}", {"name": "x"}, content_type="application/json").status_code == 404
    assert client.post(f"/api/sources/{source_id}/preview").status_code == 404
    assert client.get("/api/sources").json()["sources"] == []


@pytest.mark.django_db
def test_due_sources_and_claims_prevent_overlapping_runs(owner):
    from django.utils import timezone as dj_timezone

    from archive.storage_sources import claim, due_sources

    fresh = make_source(owner, name="Fresh")
    recent = make_source(owner, name="Recent", last_checked_at=dj_timezone.now(), poll_minutes=15)
    make_source(owner, name="Off", enabled=False)
    assert list(due_sources()) == [fresh.id]
    assert claim(fresh.id) is not None and claim(fresh.id) is None  # already running
    StorageSource.objects.filter(pk=fresh.pk).update(running_since=dj_timezone.now() - timedelta(hours=1))
    assert claim(fresh.id) is not None  # a stale claim is taken over
    assert claim(recent.id) is not None
    assert StorageSourceSeen.objects.count() == 0
