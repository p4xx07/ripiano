"""Cloud drive sources: Google Drive, Microsoft OneDrive, and Dropbox, connected with OAuth.

The archive owner registers one OAuth app per provider (client ID and secret, stored in the app; the
existing Gmail/Outlook environment values are a fallback). A person connects a source with "Connect
account"; Ripiano keeps only the encrypted refresh token. Folders are addressed by path from the drive's
root, like S3 prefixes, so the shared engine in storage_sources.py works unchanged.

"Delete" moves files to the provider's trash or recycle bin; nothing is erased permanently.
"""

import json
import secrets
from datetime import datetime, timezone as dt_timezone
from urllib.parse import quote

import httpx
from django.conf import settings
from django.core import signing

from .storage_sources import Entry, SourceError

PROVIDERS = {
    "gdrive": {
        "label": "Google Drive",
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/drive openid email",
        "extra": {"access_type": "offline", "prompt": "consent"},
        "fallback": "gmail",
        "console": "https://console.cloud.google.com/apis/credentials",
    },
    "onedrive": {
        "label": "OneDrive",
        "authorize": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scope": "Files.ReadWrite offline_access openid email",
        "extra": {"prompt": "select_account"},
        "fallback": "outlook",
        "console": "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade",
    },
    "dropbox": {
        "label": "Dropbox",
        "authorize": "https://www.dropbox.com/oauth2/authorize",
        "token": "https://api.dropboxapi.com/oauth2/token",
        "scope": "account_info.read files.metadata.read files.content.read files.content.write",
        "extra": {"token_access_type": "offline"},
        "fallback": None,
        "console": "https://www.dropbox.com/developers/apps",
    },
}
STATE_SALT = "ripiano.sources.oauth"
STATE_MAX_AGE = 15 * 60
GOOGLE_EXPORTS = {
    "application/vnd.google-apps.document": "application/pdf",
    "application/vnd.google-apps.spreadsheet": "application/pdf",
    "application/vnd.google-apps.presentation": "application/pdf",
    "application/vnd.google-apps.drawing": "application/pdf",
}
MAX_ENTRIES = 20000
MAX_DEPTH = 25


# --- OAuth ---------------------------------------------------------------------------------

def client_for(provider):
    """(client_id, client_secret) from the app's settings, else the Gmail/Outlook environment values."""
    from .mail import MailError, decrypt_secret
    from .models import CloudApp

    app = CloudApp.objects.filter(provider=provider).first()
    if app and app.client_id:
        try:
            return app.client_id, decrypt_secret(app.client_secret)
        except MailError:
            return None, None
    fallback = PROVIDERS[provider]["fallback"]
    if fallback and settings.RIPIANO_MAIL_OAUTH.get(fallback):
        return settings.RIPIANO_MAIL_OAUTH[fallback]
    return None, None


def redirect_uri():
    return f"{settings.PUBLIC_ORIGIN.rstrip('/')}/api/sources/oauth/callback"


def authorization_url(user, source):
    client_id, _ = client_for(source.kind)
    if not client_id:
        raise SourceError(f"{PROVIDERS[source.kind]['label']} sign-in is not set up yet. The archive owner can add it under Sources → Sign-in apps.")
    config = PROVIDERS[source.kind]
    state = signing.dumps({"user": user.pk, "source": str(source.id), "nonce": secrets.token_urlsafe(8)}, salt=STATE_SALT)
    query = httpx.QueryParams({"client_id": client_id, "redirect_uri": redirect_uri(), "response_type": "code",
                               "scope": config["scope"], "state": state, **config["extra"]})
    return f"{config['authorize']}?{query}"


def read_state(value):
    try:
        return signing.loads(value, salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.BadSignature as exc:
        raise SourceError("The sign-in link expired. Start again.") from exc


def token_request(provider, data, transport=None):
    client_id, client_secret = client_for(provider)
    if not client_id:
        raise SourceError(f"{PROVIDERS[provider]['label']} sign-in is no longer set up on this server.")
    try:
        with httpx.Client(timeout=20, trust_env=False, transport=transport) as http:
            response = http.post(PROVIDERS[provider]["token"], data={"client_id": client_id, "client_secret": client_secret, **data})
    except httpx.HTTPError as exc:
        raise SourceError("Could not reach the sign-in service") from exc
    if response.status_code != 200:
        raise SourceError(f"{PROVIDERS[provider]['label']} refused the sign-in. Use Connect account again.")
    try:
        return response.json()
    except ValueError as exc:
        raise SourceError("The sign-in service sent an unexpected reply") from exc


def exchange_code(provider, code, transport=None):
    """Return the refresh token for a completed consent."""
    payload = token_request(provider, {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()}, transport)
    refresh = payload.get("refresh_token")
    if not refresh:
        raise SourceError("The provider did not grant offline access. Try again and accept all permissions.")
    return refresh


# --- shared backend plumbing --------------------------------------------------------------------

def _folder(value):
    value = (value or "").strip().strip("/")
    return f"{value}/" if value else ""


def _when(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return datetime.now(dt_timezone.utc)


class CloudBackend:
    api = ""

    def __init__(self, source, transport=None):
        from .mail import MailError, decrypt_secret

        if not source.secret:
            raise SourceError("Connect the account first (Connect account on the source).")
        try:
            refresh = decrypt_secret(source.secret)
        except MailError as exc:
            raise SourceError("The saved sign-in can no longer be read. Use Connect account again.") from exc
        self.source, self.transport = source, transport
        payload = token_request(source.kind, {"grant_type": "refresh_token", "refresh_token": refresh}, transport)
        token = payload.get("access_token")
        if not token:
            raise SourceError(f"{PROVIDERS[source.kind]['label']} refused the sign-in. Use Connect account again.")
        if payload.get("refresh_token") and payload["refresh_token"] != refresh:
            from .mail import encrypt_secret
            from .models import StorageSource

            # Microsoft rotates refresh tokens; keep the newest one.
            StorageSource.objects.filter(pk=source.pk).update(secret=encrypt_secret(payload["refresh_token"]))
        self.http = httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=httpx.Timeout(60, connect=10),
                                 trust_env=False, follow_redirects=False, transport=transport)
        self.root = _folder(source.path)

    def close(self):
        self.http.close()

    def _call(self, method, url, expect=(200,), **kwargs):
        try:
            response = self.http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise SourceError(f"{PROVIDERS[self.source.kind]['label']} could not be reached") from exc
        if response.status_code == 401:
            raise SourceError(f"{PROVIDERS[self.source.kind]['label']} refused the sign-in. Use Connect account again.")
        if response.status_code not in expect:
            raise SourceError(f"{PROVIDERS[self.source.kind]['label']} refused the request ({response.status_code})")
        return response

    def _stream_to(self, response_context, handle, limit, name):
        with response_context as response:
            if response.status_code != 200:
                raise SourceError(f"Could not download “{name}” ({response.status_code})")
            received = 0
            for chunk in response.iter_bytes(64 * 1024):
                received += len(chunk)
                if received > limit:
                    raise SourceError("The file is larger than the upload limit")
                handle.write(chunk)

    def entries(self, recursive):
        for entry in self._walk(self.root, recursive):
            yield entry

    def processed_entries(self, folder):
        try:
            yield from self._walk(_folder(folder), True)
        except SourceError as exc:
            if "does not exist" in str(exc):
                return
            raise


# --- Google Drive ------------------------------------------------------------------------------

class GoogleDriveBackend(CloudBackend):
    api = "https://www.googleapis.com/drive/v3"
    FOLDER = "application/vnd.google-apps.folder"

    def __init__(self, source, transport=None):
        super().__init__(source, transport)
        self.ids = {"": "root"}  # path -> folder id
        self.files = {}  # key -> (file id, parent id, mime type)

    def _children(self, folder_id):
        token = None
        while True:
            params = {"q": f"'{folder_id}' in parents and trashed = false", "pageSize": "1000",
                      "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, md5Checksum, version)"}
            if token:
                params["pageToken"] = token
            payload = self._call("GET", f"{self.api}/files", params=params).json()
            yield from payload.get("files", [])
            token = payload.get("nextPageToken")
            if not token:
                return

    def _folder_id(self, path, create=False):
        path = path.strip("/")
        if path in self.ids:
            return self.ids[path]
        parent_path, _, name = path.rpartition("/")
        parent = self._folder_id(parent_path, create)
        found = next((item["id"] for item in self._children(parent) if item["name"] == name and item["mimeType"] == self.FOLDER), None)
        if found is None:
            if not create:
                raise SourceError(f"The folder “{path}” does not exist in Google Drive")
            found = self._call("POST", f"{self.api}/files", json={"name": name, "mimeType": self.FOLDER, "parents": [parent]}).json()["id"]
        self.ids[path] = found
        return found

    def _walk(self, start, recursive):
        pending, seen = [(start, 0)], 0
        while pending:
            folder, depth = pending.pop(0)
            folder_id = self._folder_id(folder)
            for item in self._children(folder_id):
                key = folder + item["name"]
                if item["mimeType"] == self.FOLDER:
                    self.ids[key] = item["id"]
                    if recursive and depth < MAX_DEPTH:
                        pending.append((key + "/", depth + 1))
                    continue
                if item["mimeType"].startswith("application/vnd.google-apps.") and item["mimeType"] not in GOOGLE_EXPORTS:
                    continue  # forms, sites, shortcuts: nothing to import
                exported = item["mimeType"] in GOOGLE_EXPORTS
                if exported:
                    key += ".pdf"
                seen += 1
                if seen > MAX_ENTRIES:
                    raise SourceError(f"The folder has more than {MAX_ENTRIES} files; choose a smaller folder")
                self.files[key] = (item["id"], folder_id, item["mimeType"])
                yield Entry(key=key, relative=key[len(start):], size=int(item.get("size") or 0), modified=_when(item.get("modifiedTime")),
                            version=item.get("md5Checksum") or str(item.get("version") or item.get("modifiedTime") or ""))

    def download(self, entry, handle, limit):
        file_id, _, mime = self.files[entry.key]
        if mime in GOOGLE_EXPORTS:
            url, params = f"{self.api}/files/{file_id}/export", {"mimeType": GOOGLE_EXPORTS[mime]}
        else:
            url, params = f"{self.api}/files/{file_id}", {"alt": "media"}
        self._stream_to(self.http.stream("GET", url, params=params), handle, limit, entry.relative)

    def move(self, entry, destination):
        file_id, parent, _ = self.files[entry.key]
        folder_path, _, name = destination.rpartition("/")
        target = self._folder_id(folder_path, create=True)
        if name.endswith(".pdf") and entry.key.endswith(".pdf") and self.files[entry.key][2] in GOOGLE_EXPORTS:
            name = name[:-4]  # a Google Doc keeps its own name; ".pdf" was only added for the archive
        self._call("PATCH", f"{self.api}/files/{file_id}", params={"addParents": target, "removeParents": parent}, json={"name": name})

    def delete(self, entry):
        file_id = self.files[entry.key][0] if entry.key in self.files else None
        if file_id:
            self._call("PATCH", f"{self.api}/files/{file_id}", json={"trashed": True})


# --- OneDrive ----------------------------------------------------------------------------------------

class OneDriveBackend(CloudBackend):
    api = "https://graph.microsoft.com/v1.0/me/drive"

    def __init__(self, source, transport=None):
        super().__init__(source, transport)
        self.ids = {}

    def _item_url(self, path):
        path = path.strip("/")
        return f"{self.api}/root" if not path else f"{self.api}/root:/{quote(path, safe='/')}:"

    def _walk(self, start, recursive):
        pending, seen = [(start, 0)], 0
        while pending:
            folder, depth = pending.pop(0)
            url = f"{self._item_url(folder)}/children"
            params = {"$top": "999", "$select": "id,name,size,lastModifiedDateTime,eTag,cTag,file,folder"}
            while url:
                response = self._call("GET", url, expect=(200, 404), params=params)
                if response.status_code == 404:
                    raise SourceError(f"The folder “{folder or '/'}” does not exist in OneDrive")
                payload = response.json()
                for item in payload.get("value", []):
                    key = folder + item["name"]
                    if "folder" in item:
                        if recursive and depth < MAX_DEPTH:
                            pending.append((key + "/", depth + 1))
                        continue
                    if "file" not in item:
                        continue
                    seen += 1
                    if seen > MAX_ENTRIES:
                        raise SourceError(f"The folder has more than {MAX_ENTRIES} files; choose a smaller folder")
                    self.ids[key] = item["id"]
                    yield Entry(key=key, relative=key[len(start):], size=int(item.get("size") or 0),
                                modified=_when(item.get("lastModifiedDateTime")), version=item.get("cTag") or item.get("eTag") or "")
                url, params = payload.get("@odata.nextLink"), None

    def download(self, entry, handle, limit):
        response = self._call("GET", f"{self.api}/items/{self.ids[entry.key]}/content", expect=(200, 302))
        if response.status_code == 302:
            # The file itself comes from a pre-authenticated download address; do not send the token there.
            with httpx.Client(timeout=httpx.Timeout(60, connect=10), trust_env=False, transport=self.transport) as plain:
                self._stream_to(plain.stream("GET", response.headers["Location"]), handle, limit, entry.relative)
        else:
            handle.write(response.content[: limit + 1])
            if len(response.content) > limit:
                raise SourceError("The file is larger than the upload limit")

    def _ensure_folder(self, path):
        parent = ""
        for part in [item for item in path.strip("/").split("/") if item]:
            response = self._call("POST", f"{self._item_url(parent)}/children", expect=(200, 201, 409),
                                  json={"name": part, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"})
            parent = f"{parent}/{part}" if parent else part
            if response.status_code not in (200, 201, 409):
                raise SourceError(f"OneDrive refused to create the folder “{parent}”")
        return self._call("GET", self._item_url(parent)).json()["id"]

    def move(self, entry, destination):
        folder_path, _, name = destination.rpartition("/")
        target = self._ensure_folder(folder_path)
        self._call("PATCH", f"{self.api}/items/{self.ids[entry.key]}?@microsoft.graph.conflictBehavior=rename",
                   json={"parentReference": {"id": target}, "name": name})

    def delete(self, entry):
        if entry.key in self.ids:
            self._call("DELETE", f"{self.api}/items/{self.ids[entry.key]}", expect=(204, 404))


# --- Dropbox ------------------------------------------------------------------------------------------------

class DropboxBackend(CloudBackend):
    api = "https://api.dropboxapi.com/2"
    content = "https://content.dropboxapi.com/2"

    def _walk(self, start, recursive):
        path = "/" + start.strip("/") if start.strip("/") else ""
        response = self._call("POST", f"{self.api}/files/list_folder", expect=(200, 409),
                              json={"path": path, "recursive": recursive, "include_deleted": False, "limit": 2000})
        if response.status_code == 409:
            raise SourceError(f"The folder “{start or '/'}” does not exist in Dropbox")
        payload, seen = response.json(), 0
        prefix = start.strip("/").lower()
        while True:
            for item in payload.get("entries", []):
                if item.get(".tag") != "file":
                    continue
                key = item["path_display"].lstrip("/")
                relative = key[len(prefix) + 1:] if prefix else key
                seen += 1
                if seen > MAX_ENTRIES:
                    raise SourceError(f"The folder has more than {MAX_ENTRIES} files; choose a smaller folder")
                yield Entry(key=key, relative=relative, size=int(item.get("size") or 0), modified=_when(item.get("server_modified")),
                            version=item.get("content_hash") or item.get("rev") or "")
            if not payload.get("has_more"):
                return
            payload = self._call("POST", f"{self.api}/files/list_folder/continue", json={"cursor": payload["cursor"]}).json()

    def download(self, entry, handle, limit):
        argument = json.dumps({"path": "/" + entry.key}, ensure_ascii=True)
        self._stream_to(self.http.stream("POST", f"{self.content}/files/download", headers={"Dropbox-API-Arg": argument}), handle, limit, entry.relative)

    def move(self, entry, destination):
        # Dropbox creates missing parent folders and renames on a clash.
        self._call("POST", f"{self.api}/files/move_v2", json={"from_path": "/" + entry.key, "to_path": "/" + destination, "autorename": True})

    def delete(self, entry):
        # Deleted Dropbox files stay recoverable in the account's deleted files.
        self._call("POST", f"{self.api}/files/delete_v2", expect=(200, 409), json={"path": "/" + entry.key})


BACKENDS = {"gdrive": GoogleDriveBackend, "onedrive": OneDriveBackend, "dropbox": DropboxBackend}
