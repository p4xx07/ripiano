"""Optional S3 bucket intake, using the same durable ingestion pipeline as other inputs.

New objects under an inbox prefix are imported, then moved to ``<processed prefix><UTC date>/<name>``.
Processed objects are deleted after a grace period (default 30 days). Nothing outside the two prefixes
is ever touched.

The client is a small AWS Signature Version 4 implementation over httpx (already a dependency), so the
NAS image does not grow by the size of boto3/botocore. It covers exactly the calls used here:
ListObjectsV2, GetObject, CopyObject, and DeleteObject.
"""

import hashlib
import hmac
import logging
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import PurePosixPath
from urllib.parse import quote, urlsplit

import httpx
from django.conf import settings
from django.core.files import File
from django.db import IntegrityError

from .ingestion import ingest_document
from .models import Document
from .storage import SUPPORTED_EXTENSIONS, InvalidDocument

logger = logging.getLogger(__name__)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class S3Error(Exception):
    """A storage problem reported without credentials or request signatures."""


def _encode(value, safe="-_.~"):
    return quote(value, safe=safe)


def _hmac(key, message):
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def sign(method, url, headers, *, access_key, secret_key, region, now, payload_hash=EMPTY_SHA256):
    """Return the headers for an AWS SigV4-signed S3 request (service "s3")."""
    parts = urlsplit(url)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    signed = {key.lower(): " ".join(str(value).split()) for key, value in headers.items()}
    signed["host"] = parts.netloc
    signed["x-amz-date"] = amz_date
    signed["x-amz-content-sha256"] = payload_hash
    names = sorted(signed)
    query = []
    for item in filter(None, parts.query.split("&")):
        key, _, value = item.partition("=")
        query.append((key, value))
    canonical_query = "&".join(f"{key}={value}" for key, value in sorted(query))
    canonical = "\n".join([
        method,
        parts.path or "/",
        canonical_query,
        "".join(f"{name}:{signed[name]}\n" for name in names),
        ";".join(names),
        payload_hash,
    ])
    scope = f"{day}/{region}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    key = _hmac(_hmac(_hmac(_hmac(f"AWS4{secret_key}".encode(), day), region), "s3"), "aws4_request")
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    result = {name: signed[name] for name in names if name != "host"}
    result["Authorization"] = f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={';'.join(names)}, Signature={signature}"
    return result


@dataclass
class S3Object:
    key: str
    etag: str
    size: int
    last_modified: datetime


class S3Client:
    def __init__(self, *, endpoint, bucket, access_key, secret_key, region="us-east-1", addressing="path", transport=None):
        parts = urlsplit(endpoint.rstrip("/"))
        if parts.scheme not in ("https", "http") or not parts.netloc or parts.path not in ("", "/"):
            raise S3Error("RIPIANO_S3_ENDPOINT must be an address like https://s3.example.com")
        if addressing not in ("path", "virtual"):
            raise S3Error("RIPIANO_S3_ADDRESSING must be path or virtual")
        self.scheme, self.netloc = parts.scheme, parts.netloc
        self.bucket, self.access_key, self.secret_key, self.region, self.addressing = bucket, access_key, secret_key, region, addressing
        self.http = httpx.Client(timeout=httpx.Timeout(60, connect=10), follow_redirects=False, trust_env=False, transport=transport)

    def close(self):
        self.http.close()

    def _url(self, key="", query=None):
        path = "/" + _encode(key, safe="/-_.~") if key else "/"
        if self.addressing == "path":
            path = f"/{_encode(self.bucket)}" + (path if key else "")
            host = self.netloc
        else:
            host = f"{self.bucket}.{self.netloc}"
        encoded = "&".join(f"{_encode(name)}={_encode(value)}" for name, value in (query or {}).items())
        return f"{self.scheme}://{host}{path}" + (f"?{encoded}" if encoded else "")

    def _request(self, method, key="", query=None, headers=None, stream=False):
        url = self._url(key, query)
        signed = sign(method, url, headers or {}, access_key=self.access_key, secret_key=self.secret_key,
                      region=self.region, now=datetime.now(dt_timezone.utc))
        request = self.http.build_request(method, url, headers=signed)
        try:
            response = self.http.send(request, stream=stream)
        except httpx.HTTPError as exc:
            raise S3Error(f"The bucket could not be reached ({exc.__class__.__name__})") from exc
        if response.status_code >= 300:
            code = ""
            try:
                body = response.read() if stream else response.content
                code = ET.fromstring(body).findtext("Code") or ""
            except ET.ParseError:
                pass
            finally:
                response.close()
            raise S3Error(f"{method} refused by the bucket ({response.status_code}{' ' + code if code else ''})")
        return response

    def list(self, prefix):
        """Every object under a prefix, following continuation tokens."""
        token = None
        while True:
            query = {"list-type": "2", "prefix": prefix}
            if token:
                query["continuation-token"] = token
            root = ET.fromstring(self._request("GET", query=query).content)
            for item in root.iter(f"{S3_NS}Contents"):
                yield S3Object(
                    key=item.findtext(f"{S3_NS}Key"), etag=(item.findtext(f"{S3_NS}ETag") or "").strip('"'),
                    size=int(item.findtext(f"{S3_NS}Size") or 0),
                    last_modified=datetime.fromisoformat((item.findtext(f"{S3_NS}LastModified") or "").replace("Z", "+00:00")),
                )
            if root.findtext(f"{S3_NS}IsTruncated") != "true":
                return
            token = root.findtext(f"{S3_NS}NextContinuationToken")

    def download(self, key, target, limit):
        """Stream an object into an open binary file; refuse anything larger than ``limit`` bytes."""
        response = self._request("GET", key, stream=True)
        try:
            received = 0
            for chunk in response.iter_bytes(64 * 1024):
                received += len(chunk)
                if received > limit:
                    raise S3Error("The object is larger than the upload limit")
                target.write(chunk)
        finally:
            response.close()

    def copy(self, source, destination):
        response = self._request("PUT", destination, headers={"x-amz-copy-source": f"/{_encode(self.bucket)}/{_encode(source, safe='/-_.~')}"})
        # S3 can report a failed copy inside a 200 response.
        if b"<Error>" in response.content:
            raise S3Error("The bucket refused to copy the object")

    def delete(self, key):
        self._request("DELETE", key)


@dataclass
class S3Settings:
    inbox: str
    processed: str
    retention_days: int


def _prefix(value):
    value = value.strip().lstrip("/")
    return value if not value or value.endswith("/") else value + "/"


def settings_from_env(env):
    inbox, processed = _prefix(env.get("RIPIANO_S3_PREFIX", "inbox/")), _prefix(env.get("RIPIANO_S3_PROCESSED_PREFIX", "processed/"))
    if not processed or inbox.startswith(processed) or processed.startswith(inbox):
        raise S3Error("RIPIANO_S3_PREFIX and RIPIANO_S3_PROCESSED_PREFIX must not contain each other, and the processed prefix cannot be empty")
    try:
        days = int(env.get("RIPIANO_S3_PROCESSED_RETENTION_DAYS", "30"))
    except ValueError as exc:
        raise S3Error("RIPIANO_S3_PROCESSED_RETENTION_DAYS must be a whole number") from exc
    if days < 0:
        raise S3Error("RIPIANO_S3_PROCESSED_RETENTION_DAYS cannot be negative")
    return S3Settings(inbox=inbox, processed=processed, retention_days=days)


class BucketImporter:
    def __init__(self, client, owner, config):
        self.client, self.owner, self.config = client, owner, config
        self.skipped = set()  # (key, etag) already reported, so logs do not repeat every pass

    def source_ref(self, item):
        return hashlib.sha256(f"{self.client.bucket}\0{item.key}\0{item.etag}".encode()).hexdigest()

    def processed_key(self, item, now):
        relative = item.key[len(self.config.inbox):]
        return f"{self.config.processed}{now:%Y-%m-%d}/{relative}"

    def _skip(self, item, reason):
        if (item.key, item.etag) not in self.skipped:
            logger.warning("S3 object left in place: %s (%s)", item.key, reason)
            self.skipped.add((item.key, item.etag))

    def import_new(self, now=None):
        """Import every supported object under the inbox prefix, then move it. Returns how many were imported."""
        now = now or datetime.now(dt_timezone.utc)
        imported = 0
        for item in list(self.client.list(self.config.inbox)):
            if item.key.endswith("/"):
                continue  # a folder marker
            name = PurePosixPath(item.key).name
            if PurePosixPath(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                self._skip(item, "unsupported file type")
                continue
            if item.size > settings.RIPIANO_MAX_UPLOAD_BYTES:
                self._skip(item, "larger than the upload limit")
                continue
            reference = self.source_ref(item)
            already = Document.objects.filter(owner=self.owner, source=Document.Source.S3, source_ref=reference).exists()
            if not already:
                try:
                    with tempfile.TemporaryFile() as handle:
                        self.client.download(item.key, handle, settings.RIPIANO_MAX_UPLOAD_BYTES)
                        handle.seek(0)
                        ingest_document(self.owner, File(handle, name=name), source=Document.Source.S3, source_ref=reference)
                except InvalidDocument as error:
                    self._skip(item, str(error))
                    continue
                except IntegrityError:
                    # Another poller imported the same object version after the existence check.
                    if not Document.objects.filter(owner=self.owner, source=Document.Source.S3, source_ref=reference).exists():
                        raise
                else:
                    imported += 1
                    logger.info("Imported S3 object %s", item.key)
            # The original is durable in Ripiano before the object leaves the inbox; a crash here only repeats the move.
            self.client.copy(item.key, self.processed_key(item, now))
            self.client.delete(item.key)
        return imported

    def expire_processed(self, now=None):
        """Delete processed objects older than the grace period. 0 days keeps them forever."""
        if not self.config.retention_days:
            return 0
        cutoff = (now or datetime.now(dt_timezone.utc)) - timedelta(days=self.config.retention_days)
        removed = 0
        for item in list(self.client.list(self.config.processed)):
            if item.last_modified < cutoff and not item.key.endswith("/"):
                self.client.delete(item.key)
                removed += 1
        if removed:
            logger.info("Deleted %d processed S3 object(s) after the grace period", removed)
        return removed
