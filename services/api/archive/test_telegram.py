import json
from io import BytesIO

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from PIL import Image

from archive.mail import encrypt_secret
from archive.models import Document, DocumentTag, StorageSource, Tag
from archive.storage_sources import SourceError, due_sources, preview, run
from archive.telegram import TelegramClient

# A made-up token in Telegram's format, split so secret scanners do not mistake it for a real one.
TOKEN = "123456789:" + "AAH4b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q"


def png():
    content = BytesIO()
    Image.new("RGB", (8, 8), "white").save(content, "PNG")
    return content.getvalue()


class FakeTelegram:
    """The Bot API calls Ripiano makes: getMe, getUpdates, getFile, file download, sendMessage."""

    def __init__(self, updates):
        self.updates, self.sent, self.downloads = updates, [], 0

    def handler(self, request):
        path = request.url.path
        if f"/bot{TOKEN}/" not in path and f"/file/bot{TOKEN}/" not in path:
            return httpx.Response(401, json={"ok": False})
        method = path.rsplit("/", 1)[-1]
        if path.startswith(f"/file/bot{TOKEN}/"):
            self.downloads += 1
            return httpx.Response(200, content=png())
        body = json.loads(request.content or b"{}")
        if method == "getMe":
            return httpx.Response(200, json={"ok": True, "result": {"username": "ripiano_test_bot"}})
        if method == "getUpdates":
            assert body["timeout"] == 0  # never blocks a worker
            return httpx.Response(200, json={"ok": True, "result": [item for item in self.updates if item["update_id"] >= body["offset"]][:body["limit"]]})
        if method == "getFile":
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "documents/file_1.png", "file_size": 100}})
        if method == "sendMessage":
            self.sent.append((body["chat_id"], body["text"]))
            return httpx.Response(200, json={"ok": True, "result": {}})
        return httpx.Response(404, json={"ok": False})

    def client(self):
        return TelegramClient(TOKEN, transport=httpx.MockTransport(self.handler))


def message(update_id, chat_id=42, kind="private", sender=None, **content):
    return {"update_id": update_id, "message": {"message_id": update_id, "date": 1763370000, "chat": {"id": chat_id, "type": kind},
                                                "from": {"id": sender or chat_id, "first_name": "Ada"}, **content}}


def document(update_id, chat_id=42, name="invoice.png", size=100, **extra):
    return message(update_id, chat_id, document={"file_id": f"f{update_id}", "file_name": name, "file_size": size}, **extra)


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1")


@pytest.fixture(autouse=True)
def no_queue(monkeypatch):
    monkeypatch.setattr("archive.ingestion.process_document.delay", lambda *args: None)


def source_for(owner, **values):
    return StorageSource.objects.create(owner=owner, name="Bot", kind=StorageSource.Kind.TELEGRAM, secret=encrypt_secret(TOKEN),
                                        after=StorageSource.After.KEEP, **values)


@pytest.mark.django_db
def test_unknown_chats_wait_for_approval_and_allowed_chats_import_once(owner, tmp_path):
    bills = Tag.objects.create(owner=owner, name="Bills")
    source = source_for(owner)
    source.tags.add(bills)
    telegram = FakeTelegram([message(1, text="/start"), document(2)])
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(source, telegram.client()) == 0
    source.refresh_from_db()
    assert source.pending_chats == [{"id": 42, "name": "Ada"}] and source.cursor == 3 and Document.objects.count() == 0
    assert all("archive owner can allow" in text for _, text in telegram.sent)

    client = Client()
    client.force_login(owner)
    allowed = client.post(f"/api/sources/{source.id}/chats", {"allow": 42}, content_type="application/json").json()
    assert allowed["allowed_chats"] == [{"id": 42, "name": "Ada"}] and allowed["pending_chats"] == []

    telegram.updates += [document(3), document(3)]  # Telegram may repeat an update after a timeout
    source.refresh_from_db()
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(source, telegram.client()) == 1
        source.refresh_from_db()
        assert run(source, telegram.client()) == 0
    imported = Document.objects.get()
    assert imported.source == Document.Source.TELEGRAM and imported.original_name == "invoice.png" and telegram.downloads == 1
    assert DocumentTag.objects.filter(document=imported, tag=bills).exists()
    assert telegram.sent[-1] == (42, "Saved to Ripiano.")

    removed = client.post(f"/api/sources/{source.id}/chats", {"remove": 42}, content_type="application/json").json()
    assert removed["allowed_chats"] == []


@pytest.mark.django_db
def test_groups_impersonation_filters_and_size_limits(owner, tmp_path):
    source = source_for(owner, allowed_chats=[{"id": 42, "name": "Ada"}], file_types=["pdf", "image"], max_size_mb=1)
    telegram = FakeTelegram([
        document(1, chat_id=-100, kind="group"),
        document(2, sender=7),  # someone else's message in the chat
        document(3, name="notes.docx"),
        document(4, name="huge.png", size=5 * 1024 * 1024),
        message(5, text="hello"),
    ])
    with override_settings(MEDIA_ROOT=tmp_path):
        assert run(source, telegram.client()) == 0
    source.refresh_from_db()
    assert telegram.downloads == 0 and Document.objects.count() == 0 and source.pending_chats == [] and source.cursor == 6
    assert telegram.sent == [(42, "Not imported: file type not selected."), (42, "This file is larger than 1 MB. Use the Ripiano app instead.")]


@pytest.mark.django_db
def test_token_is_checked_validated_and_never_returned(owner, monkeypatch):
    client = Client()
    client.force_login(owner)
    assert client.post("/api/sources", {"name": "Bot", "kind": "telegram", "secret": "not-a-token"}, content_type="application/json").status_code == 400
    created = client.post("/api/sources", {"name": "Bot", "kind": "telegram", "secret": TOKEN, "after": "move", "recursive": True},
                          content_type="application/json")
    assert created.status_code == 201
    data = created.json()
    assert data["kind"] == "telegram" and data["has_secret"] and data["after"] == "keep" and data["recursive"] is False
    assert data["max_size_mb"] == 20
    assert TOKEN not in client.get("/api/sources").content.decode()
    source = StorageSource.objects.get()
    assert preview(source, FakeTelegram([]).client())["bot"] == "ripiano_test_bot"
    wrong = TelegramClient("999:wrong", transport=httpx.MockTransport(FakeTelegram([]).handler))
    with pytest.raises(SourceError, match="did not accept the bot token"):
        preview(source, wrong)
    assert client.post(f"/api/sources/{source.id}/chats", {"allow": 5}, content_type="application/json").status_code == 404


@pytest.mark.django_db
def test_telegram_sources_are_due_every_minute(owner):
    from datetime import timedelta

    from django.utils import timezone

    bot = source_for(owner, last_checked_at=timezone.now() - timedelta(seconds=61))
    storage = StorageSource.objects.create(owner=owner, name="Bucket", endpoint="http://127.0.0.1:9000", bucket="b", username="k",
                                           secret=encrypt_secret("s"), last_checked_at=timezone.now() - timedelta(seconds=61))
    assert list(due_sources()) == [bot.id] and storage.id not in list(due_sources())
