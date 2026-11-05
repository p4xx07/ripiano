import logging
import os
import tempfile
import time
from pathlib import PurePosixPath
from urllib.parse import quote

import httpx
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from archive.ingestion import ingest_document
from archive.models import Document, InputCursor
from archive.storage import InvalidDocument

logger = logging.getLogger(__name__)
TELEGRAM_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


class TelegramError(Exception):
    pass


class TelegramClient:
    def __init__(self, token):
        self.token = token
        self.http = httpx.Client(timeout=httpx.Timeout(35, connect=10), follow_redirects=False)

    def call(self, method, data):
        try:
            response = self.http.post(f"https://api.telegram.org/bot{self.token}/{method}", json=data)
            payload = response.json()
            if response.status_code != 200 or not payload.get("ok"):
                raise TelegramError(f"Telegram {method} returned an error")
            return payload["result"]
        except (httpx.HTTPError, ValueError) as exc:
            raise TelegramError(f"Telegram {method} request failed") from exc

    def download(self, file_id, filename):
        info = self.call("getFile", {"file_id": file_id})
        path = info.get("file_path", "")
        if not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise TelegramError("Telegram returned an invalid file path")
        if info.get("file_size", 0) > min(settings.RIPIANO_MAX_UPLOAD_BYTES, TELEGRAM_MAX_DOWNLOAD_BYTES):
            raise InvalidDocument("File exceeds the upload limit")
        url = f"https://api.telegram.org/file/bot{self.token}/{quote(path, safe='/')}"
        download = tempfile.TemporaryFile()
        try:
            with self.http.stream("GET", url) as response:
                if response.status_code != 200:
                    raise TelegramError("Telegram file download failed")
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > min(settings.RIPIANO_MAX_UPLOAD_BYTES, TELEGRAM_MAX_DOWNLOAD_BYTES):
                        raise InvalidDocument("File exceeds the upload limit")
                    download.write(chunk)
            download.seek(0)
            return File(download, name=filename)
        except Exception:
            download.close()
            raise


def process_update(update, *, client, owner, allowed_ids):
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat.get("type") != "private" or not isinstance(chat_id, int):
        return None
    text = message.get("text", "")
    if text.startswith("/start") or text.startswith("/id"):
        return chat_id, f"Your Ripiano chat ID is {chat_id}. Add it to RIPIANO_TELEGRAM_ALLOWED_CHAT_IDS to enable uploads."
    if chat_id not in allowed_ids or message.get("from", {}).get("id") != chat_id:
        return None

    attachment = message.get("document")
    if attachment:
        filename = attachment.get("file_name") or f"telegram-{message.get('message_id', update['update_id'])}"
    elif message.get("photo"):
        attachment = message["photo"][-1]
        filename = f"telegram-photo-{message.get('message_id', update['update_id'])}.jpg"
    else:
        return None

    source_ref = str(update["update_id"])
    if Document.objects.filter(source=Document.Source.TELEGRAM, source_ref=source_ref).exists():
        return None
    if attachment.get("file_size", 0) > min(settings.RIPIANO_MAX_UPLOAD_BYTES, TELEGRAM_MAX_DOWNLOAD_BYTES):
        return chat_id, "This file is too large for Ripiano. Use the web app instead."
    try:
        upload = client.download(attachment["file_id"], filename)
        try:
            ingest_document(owner, upload, source=Document.Source.TELEGRAM, source_ref=source_ref)
        finally:
            upload.close()
    except InvalidDocument:
        return chat_id, "Ripiano accepts PDF, JPEG, and PNG files. Use the web app for files over 20 MB."
    return chat_id, "Saved to Ripiano. You can find it in your archive."


class Command(BaseCommand):
    help = "Poll a Telegram bot for private-chat document uploads"

    def handle(self, *args, **options):
        token = os.environ.get("RIPIANO_TELEGRAM_BOT_TOKEN", "")
        username = os.environ.get("RIPIANO_TELEGRAM_OWNER_USERNAME", "")
        if not token or not username:
            raise CommandError("Set RIPIANO_TELEGRAM_BOT_TOKEN and RIPIANO_TELEGRAM_OWNER_USERNAME")
        try:
            allowed_ids = {int(value.strip()) for value in os.environ.get("RIPIANO_TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if value.strip()}
        except ValueError as exc:
            raise CommandError("RIPIANO_TELEGRAM_ALLOWED_CHAT_IDS must contain numeric IDs") from exc
        owner = get_user_model().objects.filter(username=username).first()
        if owner is None:
            raise CommandError("Telegram owner account does not exist")

        client = TelegramClient(token)
        cursor, _ = InputCursor.objects.get_or_create(source="telegram")
        while True:
            try:
                updates = client.call("getUpdates", {
                    "offset": cursor.next_offset,
                    "timeout": 25,
                    "limit": 20,
                    "allowed_updates": ["message"],
                })
                for update in updates:
                    if update["update_id"] < cursor.next_offset:
                        continue
                    reply = process_update(update, client=client, owner=owner, allowed_ids=allowed_ids)
                    cursor.next_offset = update["update_id"] + 1
                    cursor.save(update_fields=["next_offset"])
                    if reply:
                        try:
                            client.call("sendMessage", {"chat_id": reply[0], "text": reply[1]})
                        except TelegramError:
                            logger.warning("Telegram acknowledgement failed")
            except (TelegramError, httpx.HTTPError, KeyError, OSError):
                logger.warning("Telegram input unavailable; retrying in five seconds")
                time.sleep(5)
