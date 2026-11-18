"""Round-4 judge fixes: clear upload errors for damaged files and oversized images."""

import struct
import zlib
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from PIL import Image

from archive.storage import DAMAGED_IMAGE, DAMAGED_PDF, MAX_IMAGE_PIXELS, TOO_LARGE_IMAGE, UNSUPPORTED, InvalidDocument, save_original


def png_header(width, height):
    """A PNG whose header declares the given size; enough for Pillow to read its dimensions."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00" * 16)) + chunk(b"IEND", b"")


def small_png():
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(("name", "expected"), [
    ("x.pdf", DAMAGED_PDF),
    ("scan.PNG", DAMAGED_IMAGE),
    ("photo.jpg", DAMAGED_IMAGE),
    ("photo.jpeg", DAMAGED_IMAGE),
    ("notes.txt", UNSUPPORTED),
    ("noextension", UNSUPPORTED),
])
def test_damaged_file_with_a_supported_name_is_called_damaged_not_the_wrong_type(tmp_path, name, expected):
    with override_settings(MEDIA_ROOT=tmp_path), pytest.raises(InvalidDocument) as error:
        save_original(SimpleUploadedFile(name, b"just some text, not a real file"))
    assert str(error.value) == expected


def test_a_real_image_with_the_wrong_name_is_still_accepted_by_content(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        _, mime, _, _ = save_original(SimpleUploadedFile("x.pdf", small_png()))
    assert mime == "image/png"


@pytest.mark.parametrize(("width", "height"), [
    (15000, 15000),  # 225 MP: over Pillow's decompression-bomb error threshold
    (8000, 8000),    # 64 MP: over the cap, inside Pillow's warning range
])
def test_huge_images_are_refused_with_a_clear_message_instead_of_a_server_error(tmp_path, width, height):
    assert width * height > MAX_IMAGE_PIXELS
    with override_settings(MEDIA_ROOT=tmp_path), pytest.raises(InvalidDocument) as error:
        save_original(SimpleUploadedFile("big.png", png_header(width, height)))
    assert str(error.value) == TOO_LARGE_IMAGE
    assert "50 megapixels" in TOO_LARGE_IMAGE and MAX_IMAGE_PIXELS == 50_000_000
    assert not any((tmp_path / "originals").rglob("*.png"))


@pytest.mark.django_db
def test_upload_errors_for_damaged_and_huge_files_are_400_and_translated(tmp_path):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=tmp_path):
        damaged = client.post("/api/documents", {"document": SimpleUploadedFile("x.pdf", b"not a pdf")}, HTTP_ACCEPT_LANGUAGE="it")
        huge = client.post("/api/documents", {"document": SimpleUploadedFile("big.png", png_header(15000, 15000))}, HTTP_ACCEPT_LANGUAGE="it")
        english = client.post("/api/documents", {"document": SimpleUploadedFile("x.pdf", b"not a pdf")}, HTTP_ACCEPT_LANGUAGE="en")
    assert damaged.status_code == 400 and "danneggiato" in damaged.json()["error"]
    assert huge.status_code == 400 and "megapixel" in huge.json()["error"] and "troppo grande" in huge.json()["error"]
    assert english.status_code == 400 and english.json()["error"] == DAMAGED_PDF
