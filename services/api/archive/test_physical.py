import json
from unittest.mock import patch

import segno

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.models import Document, Location, Movement, PhysicalCopy


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
    assert shelf.json()["sticker_code"].startswith("L-")
    assert box.json()["sticker_code"].startswith("L-")
    assert shelf.json()["sticker_code"] != box.json()["sticker_code"]
    response = client.post(f"/api/documents/{document.id}/copies", json.dumps({"location_id": box.json()["id"]}), content_type="application/json")
    assert response.status_code == 201
    copy = response.json()
    assert copy["sticker_code"].startswith("R-")
    assert copy["location_path"] == ["Shelf A", "Box 1"]
    assert copy["missing_at"] is None
    container = client.get(f"/api/locations/lookup/{shelf.json()['sticker_code']}")
    assert container.status_code == 200
    assert container.json()["total"] == 1
    assert container.json()["missing_count"] == 0
    assert container.json()["copies"][0]["copy"]["sticker_code"] == copy["sticker_code"]
    with patch("archive.physical_views.segno.make_qr", wraps=segno.make_qr) as make_location_qr:
        location_label = client.get(f"/api/locations/{box.json()['id']}/label")
    assert location_label.status_code == 200 and b"<svg" in location_label.content
    assert make_location_qr.call_args.args[0].endswith(f"/?location={box.json()['sticker_code']}")
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
    assert client.patch(f"/api/copies/{copy['id']}/status", json.dumps({"missing": "yes"}), content_type="application/json").status_code == 400
    missing = client.patch(f"/api/copies/{copy['id']}/status", json.dumps({"missing": True}), content_type="application/json")
    assert missing.status_code == 200
    assert missing.json()["missing_at"] is not None
    assert missing.json()["location_path"] == ["Shelf A"]
    assert client.patch(f"/api/copies/{copy['id']}/status", json.dumps({"missing": True}), content_type="application/json").status_code == 409
    assert client.patch(f"/api/copies/{copy['id']}", json.dumps({"location_id": box.json()["id"]}), content_type="application/json").status_code == 409
    assert client.get(f"/api/stickers/{copy['sticker_code']}").json()["copy"]["missing_at"] is not None
    missing_container = client.get(f"/api/locations/lookup/{shelf.json()['sticker_code']}").json()
    assert missing_container["total"] == 0
    assert missing_container["missing_count"] == 1
    assert missing_container["copies"] == []
    assert [item["document"]["title"] for item in missing_container["missing_copies"]] == ["Contract <private>"]
    assert client.get(f"/api/copies/{copy['id']}/history").json()["movements"][0]["kind"] == "missing"
    found = client.patch(f"/api/copies/{copy['id']}/status", json.dumps({"missing": False}), content_type="application/json")
    assert found.status_code == 200
    assert found.json()["missing_at"] is None
    assert found.json()["location_path"] == ["Shelf A"]
    found_container = client.get(f"/api/locations/lookup/{shelf.json()['sticker_code']}").json()
    assert found_container["total"] == 1 and found_container["missing_count"] == 0
    assert found_container["missing_copies"] == []
    assert client.get(f"/api/copies/{copy['id']}/history").json()["movements"][0]["kind"] == "found"
    assert Movement.objects.filter(physical_copy_id=copy["id"]).count() == 4
    assert client.delete(f"/api/locations/{shelf.json()['id']}").status_code == 409

    client.force_login(other)
    assert client.get(f"/api/stickers/{copy['sticker_code']}").status_code == 404
    assert client.get(f"/api/locations/lookup/{shelf.json()['sticker_code']}").status_code == 404
    assert client.get(f"/api/locations/{box.json()['id']}/label").status_code == 404
    assert client.get(f"/api/copies/{copy['id']}/label").status_code == 404
    assert client.get(f"/api/copies/{copy['id']}/history").status_code == 404
    assert client.patch(f"/api/copies/{copy['id']}", json.dumps({"location_id": None}), content_type="application/json").status_code == 404
    assert client.patch(f"/api/copies/{copy['id']}/status", json.dumps({"missing": True}), content_type="application/json").status_code == 404
    assert client.post(f"/api/documents/{document.id}/copies", json.dumps({"location_id": None}), content_type="application/json").status_code == 404
    assert PhysicalCopy.objects.count() == 1


@pytest.mark.django_db
def test_location_label_escapes_name_and_lookup_hides_trashed_documents():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    location = Location.objects.create(owner=owner, name="Box <private>")
    active = Document.objects.create(owner=owner, title="Kept", original_name="kept.pdf", original_path="originals/kept.pdf", original_mime="application/pdf", original_sha256="a" * 64, original_size=1, status=Document.Status.READY)
    trashed = Document.objects.create(owner=owner, title="Moved aside", original_name="aside.pdf", original_path="originals/aside.pdf", original_mime="application/pdf", original_sha256="b" * 64, original_size=1, status=Document.Status.READY)
    PhysicalCopy.objects.create(document=active, location=location, sticker_code="R-KEEP1234")
    PhysicalCopy.objects.create(document=trashed, location=location, sticker_code="R-TRASH123")
    client = Client()
    client.force_login(owner)
    assert client.post(f"/api/documents/{trashed.id}/trash").status_code == 200
    label = client.get(f"/api/locations/{location.id}/label")
    assert label.status_code == 200
    assert b"Box &lt;private&gt;" in label.content
    assert b"<private>" not in label.content
    result = client.get(f"/api/locations/lookup/{location.sticker_code}").json()
    assert result["total"] == 1
    assert result["missing_count"] == 0
    assert [item["document"]["title"] for item in result["copies"]] == ["Kept"]


@pytest.mark.django_db
def test_location_lookup_pages_more_than_fifty_copies():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    location = Location.objects.create(owner=owner, name="Full shelf")
    documents = [Document(
        owner=owner, title=f"Paper {index}", original_name=f"paper-{index}.pdf",
        original_path=f"originals/paper-{index}.pdf", original_mime="application/pdf",
        original_sha256=f"{index:064x}", original_size=1, status=Document.Status.READY,
    ) for index in range(102)]
    Document.objects.bulk_create(documents)
    PhysicalCopy.objects.bulk_create([
        PhysicalCopy(document=document, location=location, sticker_code=f"R-{index:08d}",
                     missing_at=timezone.now() if index >= 51 else None)
        for index, document in enumerate(documents)
    ])
    client = Client()
    client.force_login(owner)
    first = client.get(f"/api/locations/lookup/{location.sticker_code}").json()
    assert first["total"] == 51 and len(first["copies"]) == 50
    assert first["missing_count"] == 51 and len(first["missing_copies"]) == 50
    assert first["next_cursor"] == "R-00000049"
    assert first["missing_next_cursor"] == "R-00000100"
    second = client.get(f"/api/locations/lookup/{location.sticker_code}", {"cursor": first["next_cursor"]}).json()
    assert second["total"] == 51 and len(second["copies"]) == 1
    assert second["next_cursor"] is None
    missing_second = client.get(f"/api/locations/lookup/{location.sticker_code}", {"missing_cursor": first["missing_next_cursor"]}).json()
    assert missing_second["missing_count"] == 51 and len(missing_second["missing_copies"]) == 1
    assert missing_second["missing_copies"][0]["copy"]["sticker_code"] == "R-00000101"
    assert missing_second["missing_next_cursor"] is None
    assert client.get(f"/api/locations/lookup/{location.sticker_code}", {"cursor": "../../outside"}).status_code == 400
    assert client.get(f"/api/locations/lookup/{location.sticker_code}", {"missing_cursor": "../../outside"}).status_code == 400
