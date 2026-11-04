import json
from unittest.mock import patch

import segno

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive.models import Document, Movement, PhysicalCopy


@pytest.mark.django_db
def test_sticker_location_move_and_owner_isolation():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    document = Document.objects.create(
        owner=owner, title="Contract <private>", original_name="contract.pdf",
        original_path="originals/contract.pdf", original_mime="application/pdf",
        original_sha256="a" * 64, original_size=10,
    )
    client = Client()
    client.force_login(owner)
    shelf = client.post("/api/locations", json.dumps({"name": "Shelf A"}), content_type="application/json")
    assert shelf.status_code == 201
    box = client.post("/api/locations", json.dumps({"name": "Box 1", "parent_id": shelf.json()["id"]}), content_type="application/json")
    assert box.status_code == 201
    response = client.post(f"/api/documents/{document.id}/copies", json.dumps({"location_id": box.json()["id"]}), content_type="application/json")
    assert response.status_code == 201
    copy = response.json()
    assert copy["sticker_code"].startswith("R-")
    assert copy["location_path"] == ["Shelf A", "Box 1"]
    assert client.get(f"/api/stickers/{copy['sticker_code']}").json()["document"]["id"] == str(document.id)
    with patch("archive.physical_views.segno.make_qr", wraps=segno.make_qr) as make_qr:
        label = client.get(f"/api/copies/{copy['id']}/label")
    assert label.status_code == 200 and b"<svg" in label.content
    assert b"Contract &lt;private&gt;" in label.content
    assert make_qr.call_args.args[0].endswith(f"/?sticker={copy['sticker_code']}")

    moved = client.patch(f"/api/copies/{copy['id']}", json.dumps({"location_id": shelf.json()["id"], "note": "Moved upstairs"}), content_type="application/json")
    assert moved.status_code == 200
    assert moved.json()["location_path"] == ["Shelf A"]
    assert Movement.objects.filter(physical_copy_id=copy["id"]).count() == 2
    assert client.get(f"/api/copies/{copy['id']}/history").json()["movements"][0]["note"] == "Moved upstairs"
    assert client.delete(f"/api/locations/{shelf.json()['id']}").status_code == 409

    client.force_login(other)
    assert client.get(f"/api/stickers/{copy['sticker_code']}").status_code == 404
    assert client.get(f"/api/copies/{copy['id']}/label").status_code == 404
    assert client.get(f"/api/copies/{copy['id']}/history").status_code == 404
    assert client.patch(f"/api/copies/{copy['id']}", json.dumps({"location_id": None}), content_type="application/json").status_code == 404
    assert client.post(f"/api/documents/{document.id}/copies", json.dumps({"location_id": None}), content_type="application/json").status_code == 404
    assert PhysicalCopy.objects.count() == 1
