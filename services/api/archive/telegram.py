"""Telegram bot input for storage sources: files sent to the bot in an allowed private chat become documents.

The owner pastes the bot token in Ripiano. Anyone who writes to the bot is listed as "waiting" until the
owner allows that chat. Ripiano asks Telegram for new messages every minute (no inbound port, no extra
process); Telegram keeps undelivered messages for 24 hours.
"""

import hashlib
import logging
import tempfile
from pathlib import PurePosixPath
from urllib.parse import quote

import httpx
from django.conf import settings
from django.core.files import File

from .models import Document
from .storage import InvalidDocument

logger = logging.getLogger(__name__)
TELEGRAM_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # Bot API limit for getFile
MAX_PENDING = 10
UPDATES_PER_PASS = 200


class TelegramError(Exception):
    """A user-presentable problem; never contains the token."""


class TelegramClient:
    def __init__(self, token, transport=None, base="https://api.telegram.org"):
        self.token, self.base = token, base
        self.http = httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False, trust_env=False, transport=transport)

    def close(self):
        self.http.close()

    def call(self, method, data=None):
        try:
            response = self.http.post(f"{self.base}/bot{self.token}/{method}", json=data or {})
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TelegramError("Telegram could not be reached") from exc
        if response.status_code == 401:
            raise TelegramError("Telegram did not accept the bot token")
        if response.status_code != 200 or not payload.get("ok"):
            raise TelegramError(f"Telegram refused the request ({response.status_code})")
        return payload["result"]

    def download(self, file_id, limit):
        info = self.call("getFile", {"file_id": file_id})
        path = info.get("file_path", "")
        if not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise TelegramError("Telegram returned an invalid file path")
        if info.get("file_size", 0) > limit:
            raise InvalidDocument("File exceeds the size limit")
        handle = tempfile.TemporaryFile()
        try:
            with self.http.stream("GET", f"{self.base}/file/bot{self.token}/{quote(path, safe='/')}") as response:
                if response.status_code != 200:
                    raise TelegramError("Telegram file download failed")
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise InvalidDocument("File exceeds the size limit")
                    handle.write(chunk)
            handle.seek(0)
            return handle
        except Exception:
            handle.close()
            raise


def _chat_name(message):
    person = message.get("from") or {}
    name = " ".join(filter(None, [person.get("first_name"), person.get("last_name")])) or person.get("username") or "Telegram user"
    return name[:100]


def _attachment(message, update_id):
    if message.get("document"):
        item = message["document"]
        return item, item.get("file_name") or f"telegram-{message.get('message_id', update_id)}"
    if message.get("photo"):
        return message["photo"][-1], f"telegram-photo-{message.get('message_id', update_id)}.jpg"
    return None, None


def handle_update(source, update, client):
    """Process one update. Returns (chat_id, reply, imported) or None. Updates the source's chat lists in memory."""
    from .storage_sources import Entry, _file, skip_reason
    from .ingestion import ingest_document

    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat.get("type") != "private" or not isinstance(chat_id, int) or (message.get("from") or {}).get("id") != chat_id:
        return None  # groups, channels, and forwarded-on-behalf messages are ignored
    allowed = {item["id"] for item in source.allowed_chats}
    if chat_id not in allowed:
        if not any(item["id"] == chat_id for item in source.pending_chats):
            source.pending_chats = (source.pending_chats + [{"id": chat_id, "name": _chat_name(message)}])[-MAX_PENDING:]
        return chat_id, "Ripiano received your request. The archive owner can allow this chat in Ripiano → Sources.", False
    attachment, filename = _attachment(message, update["update_id"])
    if attachment is None:
        if (message.get("text") or "").startswith("/start"):
            return chat_id, "Ready. Send or forward PDF, image, Office, or email files and Ripiano will file them.", False
        return None
    limit = min(source.max_size_mb * 1024 * 1024, settings.RIPIANO_MAX_UPLOAD_BYTES, TELEGRAM_MAX_DOWNLOAD_BYTES)
    from datetime import datetime, timezone as dt_timezone

    entry = Entry(key=filename, relative=filename, size=attachment.get("file_size", 0),
                  modified=datetime.fromtimestamp(message.get("date", 0), dt_timezone.utc), version=str(update["update_id"]))
    reason = skip_reason(source, entry, "")
    if reason == "too large":
        return chat_id, f"This file is larger than {limit // (1024 * 1024)} MB. Use the Ripiano app instead.", False
    if reason:
        return chat_id, f"Not imported: {reason}.", False
    ref = hashlib.sha256(f"{source.id}\0{update['update_id']}".encode()).hexdigest()
    if Document.objects.filter(owner=source.owner, source=Document.Source.TELEGRAM, source_ref=ref).exists():
        return None
    try:
        handle = client.download(attachment["file_id"], limit)
    except InvalidDocument:
        return chat_id, f"This file is larger than {limit // (1024 * 1024)} MB. Use the Ripiano app instead.", False
    try:
        document = ingest_document(source.owner, File(handle, name=filename), source=Document.Source.TELEGRAM, source_ref=ref)
    except InvalidDocument:
        return chat_id, "Ripiano accepts PDF, image, Office, and email files.", False
    finally:
        handle.close()
    _file(document, source)
    return chat_id, "Saved to Ripiano.", True


def run_telegram(source, client=None):
    """Fetch and handle new updates without waiting (Telegram short poll). Returns how many documents were imported."""
    from .mail import MailError, decrypt_secret
    from .models import StorageSource

    if client is None:
        try:
            client = TelegramClient(decrypt_secret(source.secret))
        except MailError as exc:
            raise TelegramError("The saved bot token can no longer be read. Edit the source and enter it again.") from exc
    imported = 0
    try:
        handled = 0
        while handled < UPDATES_PER_PASS:
            updates = client.call("getUpdates", {"offset": source.cursor, "timeout": 0, "limit": 50, "allowed_updates": ["message"]})
            if not updates:
                break
            for update in updates:
                if update.get("update_id", -1) < source.cursor:
                    continue
                reply = handle_update(source, update, client)
                imported += 1 if reply and reply[2] else 0
                source.cursor = update["update_id"] + 1
                # Saved after every update, so a crash never handles a message twice.
                StorageSource.objects.filter(pk=source.pk).update(cursor=source.cursor, pending_chats=source.pending_chats)
                handled += 1
                if reply:
                    try:
                        client.call("sendMessage", {"chat_id": reply[0], "text": reply[1]})
                    except TelegramError:
                        logger.warning("Telegram reply failed for source %s", source.id)
    finally:
        client.close()
    return imported


def bot_name(source, client=None):
    """Check the token and return the bot's @username."""
    from .mail import MailError, decrypt_secret

    try:
        client = client or TelegramClient(decrypt_secret(source.secret))
    except MailError as exc:
        raise TelegramError("The saved bot token can no longer be read. Edit the source and enter it again.") from exc
    try:
        return client.call("getMe").get("username", "")
    finally:
        client.close()
