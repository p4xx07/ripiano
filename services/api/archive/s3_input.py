"""S3-compatible storage client used by storage sources (see archive/storage_sources.py).

A small AWS Signature Version 4 implementation over httpx (already a dependency), so the NAS image does
not grow by the size of boto3/botocore. It covers exactly the calls Ripiano needs: ListObjectsV2,
GetObject, CopyObject, and DeleteObject.
"""

import hashlib
import hmac
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone as dt_timezone
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import httpx

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

    def list(self, prefix, recursive=True):
        """Every object under a prefix, following continuation tokens. Not recursive: only objects directly in it."""
        token = None
        while True:
            query = {"list-type": "2", "prefix": prefix}
            if not recursive:
                query["delimiter"] = "/"
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
