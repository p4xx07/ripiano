from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from archive.models import Document
from archive.s3_input import BucketImporter, S3Client, S3Error, settings_from_env, sign

# The example credentials from the AWS Signature Version 4 documentation, split so secret scanners
# do not mistake them for real ones.
AWS_DOC_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
AWS_DOC_SECRET = "wJalrXUtnFEMI/K7MDENG/" + "bPxRfiCYEXAMPLEKEY"

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def test_signature_matches_the_aws_documentation_example():
    # "Example: GET Object" from the AWS Signature Version 4 documentation for Amazon S3.
    headers = sign("GET", "https://examplebucket.s3.amazonaws.com/test.txt", {"Range": "bytes=0-9"},
                   access_key=AWS_DOC_KEY, secret_key=AWS_DOC_SECRET,
                   region="us-east-1", now=datetime(2013, 5, 24, tzinfo=timezone.utc))
    assert headers["Authorization"] == (
        f"AWS4-HMAC-SHA256 Credential={AWS_DOC_KEY}/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


class FakeBucket:
    """In-memory S3 that understands the four calls the importer makes."""

    def __init__(self, objects):
        self.objects = {key: (body, datetime.now(timezone.utc)) for key, body in objects.items()}
        self.fail_copy = False

    def handler(self, request):
        assert request.headers["Authorization"].startswith("AWS4-HMAC-SHA256 ")
        path = unquote(urlsplit(str(request.url)).path)
        key = path.split("/", 2)[2] if path.count("/") >= 2 else ""
        if request.method == "GET" and not key:
            prefix = request.url.params.get("prefix", "")
            items = "".join(
                f"<Contents><Key>{name}</Key><ETag>\"{len(body)}-{hash(body) & 0xffff}\"</ETag><Size>{len(body)}</Size>"
                f"<LastModified>{when.strftime('%Y-%m-%dT%H:%M:%S.000Z')}</LastModified></Contents>"
                for name, (body, when) in sorted(self.objects.items()) if name.startswith(prefix))
            return httpx.Response(200, content=f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{items}<IsTruncated>false</IsTruncated></ListBucketResult>')
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


def importer_for(owner, bucket, **env):
    client = S3Client(endpoint="https://s3.example.test", bucket="scans", access_key="key", secret_key="secret",
                      transport=httpx.MockTransport(bucket.handler))
    return BucketImporter(client, owner, settings_from_env(env))


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1")


@pytest.mark.django_db
def test_new_objects_are_imported_once_moved_and_unsupported_ones_left(owner, tmp_path, monkeypatch):
    monkeypatch.setattr("archive.ingestion.process_document.delay", lambda *args: None)
    bucket = FakeBucket({"inbox/bill one.pdf": PDF, "inbox/sub/è+più.pdf": PDF + b"%2", "inbox/notes.exe": b"MZ",
                         "inbox/folder/": b"", "elsewhere/keep.pdf": PDF})
    with override_settings(MEDIA_ROOT=tmp_path):
        importer = importer_for(owner, bucket)
        now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        assert importer.import_new(now) == 2
        assert importer.import_new(now) == 0
    names = set(Document.objects.filter(owner=owner, source=Document.Source.S3).values_list("original_name", flat=True))
    assert names == {"bill one.pdf", "è+più.pdf"}
    assert set(bucket.objects) == {"inbox/notes.exe", "inbox/folder/", "elsewhere/keep.pdf",
                                   "processed/2026-11-17/bill one.pdf", "processed/2026-11-17/sub/è+più.pdf"}


@pytest.mark.django_db
def test_a_failed_move_never_imports_twice(owner, tmp_path, monkeypatch):
    monkeypatch.setattr("archive.ingestion.process_document.delay", lambda *args: None)
    bucket = FakeBucket({"inbox/bill.pdf": PDF})
    bucket.fail_copy = True
    with override_settings(MEDIA_ROOT=tmp_path):
        importer = importer_for(owner, bucket)
        with pytest.raises(S3Error):
            importer.import_new()
        assert "inbox/bill.pdf" in bucket.objects  # still in the inbox, but already safe in Ripiano
        bucket.fail_copy = False
        assert importer.import_new() == 0  # the next pass only finishes the move
    assert Document.objects.filter(owner=owner, source=Document.Source.S3).count() == 1
    assert "inbox/bill.pdf" not in bucket.objects


@pytest.mark.django_db
def test_oversized_objects_stay_and_processed_ones_expire_after_the_grace_period(owner, tmp_path):
    bucket = FakeBucket({"inbox/huge.pdf": PDF * 50, "processed/2026-10-01/old.pdf": PDF, "processed/2026-11-16/new.pdf": PDF})
    now = datetime.now(timezone.utc)
    bucket.objects["processed/2026-10-01/old.pdf"] = (PDF, now - timedelta(days=31))
    bucket.objects["processed/2026-11-16/new.pdf"] = (PDF, now - timedelta(days=1))
    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_MAX_UPLOAD_BYTES=1000):
        importer = importer_for(owner, bucket)
        assert importer.import_new() == 0
        assert importer.expire_processed(now) == 1
        assert importer_for(owner, bucket, RIPIANO_S3_PROCESSED_RETENTION_DAYS="0").expire_processed(now + timedelta(days=999)) == 0
    assert set(bucket.objects) == {"inbox/huge.pdf", "processed/2026-11-16/new.pdf"}


def test_prefixes_and_settings_are_validated():
    assert settings_from_env({}).inbox == "inbox/" and settings_from_env({}).processed == "processed/"
    assert settings_from_env({"RIPIANO_S3_PREFIX": "/scans", "RIPIANO_S3_PROCESSED_PREFIX": "done"}).inbox == "scans/"
    for env in ({"RIPIANO_S3_PREFIX": "", "RIPIANO_S3_PROCESSED_PREFIX": "done/"},  # whole bucket would contain "done/"
                {"RIPIANO_S3_PREFIX": "in/", "RIPIANO_S3_PROCESSED_PREFIX": "in/done/"},
                {"RIPIANO_S3_PROCESSED_PREFIX": ""},
                {"RIPIANO_S3_PROCESSED_RETENTION_DAYS": "-1"},
                {"RIPIANO_S3_PROCESSED_RETENTION_DAYS": "soon"}):
        with pytest.raises(S3Error):
            settings_from_env(env)
    with pytest.raises(S3Error):
        S3Client(endpoint="ftp://x", bucket="b", access_key="a", secret_key="s")
    virtual = S3Client(endpoint="https://s3.eu-west-1.amazonaws.com", bucket="scans", access_key="a", secret_key="s", addressing="virtual")
    assert virtual._url("inbox/a b.pdf") == "https://scans.s3.eu-west-1.amazonaws.com/inbox/a%20b.pdf"
