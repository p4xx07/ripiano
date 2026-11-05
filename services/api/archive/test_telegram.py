from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files import File
from django.test import override_settings
from PIL import Image

from archive.management.commands.telegram_input import process_update
from archive.models import Document


def update(chat_id=42, update_id=99, filename="invoice.png"):
    return {"update_id": update_id, "message": {
        "message_id": 12, "chat": {"id": chat_id, "type": "private"},
        "from": {"id": chat_id},
        "document": {"file_id": "file-1", "file_name": filename, "file_size": 100},
    }}


class FakeTelegram:
    def __init__(self):
        self.download_count = 0

    def download(self, file_id, filename):
        self.download_count += 1
        content = BytesIO()
        Image.new("RGB", (8, 8), "white").save(content, "PNG")
        return File(BytesIO(content.getvalue()), name=filename)


@pytest.mark.django_db
def test_telegram_allowed_private_chat_is_ingested_once(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    telegram = FakeTelegram()
    with override_settings(MEDIA_ROOT=tmp_path), patch("archive.ingestion.process_document.delay"):
        assert process_update(update(chat_id=90), client=telegram, owner=owner, allowed_ids={42}) is None
        assert Document.objects.count() == 0
        answer = process_update(update(), client=telegram, owner=owner, allowed_ids={42})
        assert answer[0] == 42
        document = Document.objects.get()
        assert document.source == Document.Source.TELEGRAM
        assert document.source_ref == "99"
        assert (tmp_path / document.original_path).exists()
        assert process_update(update(), client=telegram, owner=owner, allowed_ids={42}) is None
        assert telegram.download_count == 1


@pytest.mark.django_db
def test_telegram_rejects_groups_and_oversize(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    telegram = FakeTelegram()
    group_update = update()
    group_update["message"]["chat"]["type"] = "group"
    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_MAX_UPLOAD_BYTES=50):
        assert process_update(group_update, client=telegram, owner=owner, allowed_ids={42}) is None
        assert process_update(update(), client=telegram, owner=owner, allowed_ids={42})[0] == 42
        assert telegram.download_count == 0
        assert Document.objects.count() == 0
