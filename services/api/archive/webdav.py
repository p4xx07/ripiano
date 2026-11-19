"""WebDAV backend for storage sources (Nextcloud, ownCloud, Synology WebDAV Server, rclone, Apache, …).

Uses only standard WebDAV (RFC 4918): PROPFIND Depth 1 for listing (recursion is done here, with limits),
GET, MOVE (after MKCOL of missing processed folders), and DELETE. Basic authentication over the
connection the owner configured; the password is stored encrypted.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, unquote, urlsplit

import httpx

from .storage_sources import Entry, SourceError

DAV = "{DAV:}"
MAX_ENTRIES = 20000
MAX_DEPTH = 25
PROPFIND_BODY = (b'<?xml version="1.0" encoding="utf-8"?><d:propfind xmlns:d="DAV:"><d:prop>'
                 b"<d:resourcetype/><d:getcontentlength/><d:getlastmodified/><d:getetag/></d:prop></d:propfind>")


def _folder(value):
    value = (value or "").strip().strip("/")
    return f"{value}/" if value else ""


class WebDAVBackend:
    def __init__(self, source, transport=None):
        from .mail import MailError, decrypt_secret

        try:
            password = decrypt_secret(source.secret)
        except MailError as exc:
            raise SourceError("The saved password can no longer be read. Edit the source and enter it again.") from exc
        parts = urlsplit(source.endpoint)
        self.origin = f"{parts.scheme}://{parts.netloc}"
        self.base_path = parts.path.rstrip("/") + "/"  # e.g. /remote.php/dav/files/ada/
        self.root = _folder(source.path)
        self.http = httpx.Client(auth=(source.username, password), timeout=httpx.Timeout(60, connect=10),
                                 follow_redirects=False, trust_env=False, transport=transport)

    def close(self):
        self.http.close()

    def _url(self, key, folder=False):
        return self.origin + quote(self.base_path + key, safe="/-_.~") + ("/" if folder and not key.endswith("/") else "")

    def _send(self, method, key, folder=False, **kwargs):
        try:
            response = self.http.request(method, self._url(key, folder), **kwargs)
        except httpx.HTTPError as exc:
            raise SourceError(f"The WebDAV server could not be reached ({exc.__class__.__name__})") from exc
        if response.status_code == 401:
            raise SourceError("The WebDAV server did not accept the user name or password")
        return response

    def _propfind(self, folder):
        """[(key, is_folder, size, modified, etag)] directly inside a folder key."""
        response = self._send("PROPFIND", folder, folder=True, headers={"Depth": "1", "Content-Type": "application/xml"}, content=PROPFIND_BODY)
        if response.status_code == 404:
            raise SourceError(f"The folder “{folder or '/'}” does not exist on the WebDAV server")
        if response.status_code != 207:
            raise SourceError(f"The WebDAV server refused to list “{folder or '/'}” ({response.status_code})")
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise SourceError("The WebDAV server sent an unreadable folder listing") from exc
        items = []
        own = (self.base_path + folder).rstrip("/")
        for node in root.iter(f"{DAV}response"):
            path = unquote(urlsplit(node.findtext(f"{DAV}href") or "").path)
            if not path.startswith(self.base_path) or path.rstrip("/") == own:
                continue  # the folder itself, or something outside the configured base
            props = ET.Element("prop")  # empty unless the server reports properties with status 200
            for stat in node.iter(f"{DAV}propstat"):
                found = stat.find(f"{DAV}prop")
                if "200" in (stat.findtext(f"{DAV}status") or "") and found is not None:
                    props = found
            is_folder = props.find(f"{DAV}resourcetype/{DAV}collection") is not None or path.endswith("/")
            try:
                modified = parsedate_to_datetime(props.findtext(f"{DAV}getlastmodified") or "")
            except (TypeError, ValueError):
                modified = None
            try:
                size = int(props.findtext(f"{DAV}getcontentlength") or 0)
            except ValueError:
                size = 0
            items.append((path[len(self.base_path):].rstrip("/"), is_folder, size, modified or datetime.now(dt_timezone.utc),
                          (props.findtext(f"{DAV}getetag") or "").strip('"')))
        return items

    def _walk(self, start, recursive):
        pending, seen = [(start, 0)], 0
        while pending:
            folder, depth = pending.pop(0)
            for key, is_folder, size, modified, etag in self._propfind(folder):
                if is_folder:
                    if recursive and depth < MAX_DEPTH:
                        pending.append((key + "/", depth + 1))
                    continue
                seen += 1
                if seen > MAX_ENTRIES:
                    raise SourceError(f"The folder has more than {MAX_ENTRIES} files; choose a smaller folder")
                yield key, size, modified, etag

    def entries(self, recursive):
        for key, size, modified, etag in self._walk(self.root, recursive):
            yield Entry(key=key, relative=key[len(self.root):], size=size, modified=modified, version=etag or f"{size}-{modified.timestamp()}")

    def processed_entries(self, folder):
        try:
            for key, size, modified, etag in self._walk(folder, True):
                yield Entry(key=key, relative=key[len(folder):], size=size, modified=modified, version=etag)
        except SourceError as exc:
            if "does not exist" in str(exc):
                return  # nothing processed yet
            raise

    def download(self, entry, handle, limit):
        try:
            with self.http.stream("GET", self._url(entry.key)) as response:
                if response.status_code != 200:
                    raise SourceError(f"The WebDAV server refused to send “{entry.relative}” ({response.status_code})")
                received = 0
                for chunk in response.iter_bytes(64 * 1024):
                    received += len(chunk)
                    if received > limit:
                        raise SourceError("The file is larger than the upload limit")
                    handle.write(chunk)
        except httpx.HTTPError as exc:
            raise SourceError("The WebDAV server stopped sending the file") from exc

    def _make_folders(self, key):
        parts = key.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            response = self._send("MKCOL", "/".join(parts[:index]), folder=True)
            if response.status_code not in (201, 405, 301):  # 405: it already exists
                raise SourceError(f"The WebDAV server refused to create the folder “{'/'.join(parts[:index])}” ({response.status_code})")

    def move(self, entry, destination):
        self._make_folders(destination)
        response = self._send("MOVE", entry.key, headers={"Destination": self._url(destination), "Overwrite": "F"})
        if response.status_code == 412:  # a file with that name was already moved today; keep both
            destination = destination.rsplit(".", 1)
            destination = f"{destination[0]}-{int(datetime.now().timestamp())}" + (f".{destination[1]}" if len(destination) > 1 else "")
            response = self._send("MOVE", entry.key, headers={"Destination": self._url(destination), "Overwrite": "F"})
        if response.status_code not in (201, 204):
            raise SourceError(f"The WebDAV server refused to move “{entry.relative}” ({response.status_code})")

    def delete(self, entry):
        response = self._send("DELETE", entry.key)
        if response.status_code not in (200, 204, 404):
            raise SourceError(f"The WebDAV server refused to delete “{entry.relative}” ({response.status_code})")
