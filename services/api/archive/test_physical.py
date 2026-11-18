import json
import re
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


def _json(client, method, url, body):
    return getattr(client, method)(url, json.dumps(body), content_type="application/json")


@pytest.mark.django_db
def test_location_rename_move_and_validation_keep_copy_history():
    owner = get_user_model().objects.create_user("mover", password="secure-password-1")
    other = get_user_model().objects.create_user("intruder", password="secure-password-2")
    document = Document.objects.create(
        owner=owner, title="Lease", original_name="lease.pdf", original_path="originals/lease.pdf",
        original_mime="application/pdf", original_sha256="c" * 64, original_size=10,
    )
    client = Client()
    client.force_login(owner)
    shelf = _json(client, "post", "/api/locations", {"name": "Shelf"}).json()
    box = _json(client, "post", "/api/locations", {"name": "Box", "parent_id": shelf["id"]}).json()
    folder = _json(client, "post", "/api/locations", {"name": "Folder", "parent_id": box["id"]}).json()
    cabinet = _json(client, "post", "/api/locations", {"name": "Cabinet"}).json()
    copy = _json(client, "post", f"/api/documents/{document.id}/copies", {"location_id": folder["id"]}).json()

    renamed = _json(client, "patch", f"/api/locations/{box['id']}", {"name": "  Blue box  "})
    assert renamed.status_code == 200
    assert renamed.json()["path"] == ["Shelf", "Blue box"]
    assert renamed.json()["sticker_code"] == box["sticker_code"]
    assert client.get(f"/api/stickers/{copy['sticker_code']}").json()["copy"]["location_path"] == ["Shelf", "Blue box", "Folder"]

    moved = _json(client, "patch", f"/api/locations/{box['id']}", {"parent_id": cabinet["id"]})
    assert moved.status_code == 200
    assert moved.json()["path"] == ["Cabinet", "Blue box"]
    assert moved.json()["parent_id"] == cabinet["id"]
    history = client.get(f"/api/copies/{copy['id']}/history").json()["movements"]
    assert len(history) == 1 and history[0]["to"] == ["Cabinet", "Blue box", "Folder"]
    assert Movement.objects.filter(physical_copy_id=copy["id"]).count() == 1
    assert PhysicalCopy.objects.get(pk=copy["id"]).location_id.hex == folder["id"].replace("-", "")

    top = _json(client, "patch", f"/api/locations/{box['id']}", {"parent_id": None})
    assert top.status_code == 200 and top.json()["path"] == ["Blue box"]

    # Cycles: into itself and into a descendant.
    assert _json(client, "patch", f"/api/locations/{box['id']}", {"parent_id": box["id"]}).status_code == 400
    cycle = _json(client, "patch", f"/api/locations/{box['id']}", {"parent_id": folder["id"]})
    assert cycle.status_code == 400
    assert "inside itself" in cycle.json()["error"]
    assert Location.objects.get(pk=box["id"]).parent_id is None

    # Duplicate names among siblings are refused, case-insensitively, for rename and move.
    assert _json(client, "patch", f"/api/locations/{box['id']}", {"name": "shelf"}).status_code == 409
    _json(client, "post", "/api/locations", {"name": "Blue Box", "parent_id": shelf["id"]})
    assert _json(client, "patch", f"/api/locations/{box['id']}", {"parent_id": shelf["id"]}).status_code == 409
    assert _json(client, "patch", f"/api/locations/{box['id']}", {"name": "BLUE BOX"}).status_code == 200

    # Bad input.
    assert _json(client, "patch", f"/api/locations/{box['id']}", {}).status_code == 400
    assert _json(client, "patch", f"/api/locations/{box['id']}", {"name": "   "}).status_code == 400
    assert _json(client, "patch", f"/api/locations/{box['id']}", {"name": "x" * 101}).status_code == 400
    assert _json(client, "patch", f"/api/locations/{box['id']}", {"parent_id": "not-a-uuid"}).status_code == 400

    # Another owner can neither see nor move these locations, nor use them as a parent.
    other_client = Client()
    other_client.force_login(other)
    assert _json(other_client, "patch", f"/api/locations/{box['id']}", {"name": "Mine"}).status_code == 404
    assert other_client.delete(f"/api/locations/{cabinet['id']}").status_code == 404
    theirs = _json(other_client, "post", "/api/locations", {"name": "Their shelf"}).json()
    assert _json(client, "patch", f"/api/locations/{box['id']}", {"parent_id": theirs["id"]}).status_code == 400
    assert Location.objects.get(pk=box["id"]).name == "BLUE BOX"


@pytest.mark.django_db
def test_location_delete_only_when_empty():
    owner = get_user_model().objects.create_user("deleter", password="secure-password-1")
    document = Document.objects.create(
        owner=owner, title="Receipt", original_name="r.pdf", original_path="originals/r.pdf",
        original_mime="application/pdf", original_sha256="d" * 64, original_size=10,
    )
    client = Client()
    client.force_login(owner)
    shelf = _json(client, "post", "/api/locations", {"name": "Shelf"}).json()
    box = _json(client, "post", "/api/locations", {"name": "Box", "parent_id": shelf["id"]}).json()
    copy = _json(client, "post", f"/api/documents/{document.id}/copies", {"location_id": box["id"]}).json()

    nested = client.delete(f"/api/locations/{shelf['id']}")
    assert nested.status_code == 409 and "locations inside" in nested.json()["error"]
    stored = client.delete(f"/api/locations/{box['id']}")
    assert stored.status_code == 409 and "paper copies" in stored.json()["error"]

    Document.objects.filter(pk=document.id).update(trashed_at=timezone.now())
    trashed = client.delete(f"/api/locations/{box['id']}")
    assert trashed.status_code == 409 and "Trash" in trashed.json()["error"]
    Document.objects.filter(pk=document.id).update(trashed_at=None)

    _json(client, "patch", f"/api/copies/{copy['id']}", {"location_id": shelf["id"]})
    assert client.delete(f"/api/locations/{box['id']}").json() == {"deleted": True}
    assert not Location.objects.filter(pk=box["id"]).exists()
    # History rows survive; the deleted location just drops out of their path.
    assert Movement.objects.filter(physical_copy_id=copy["id"]).count() == 2
    assert client.delete(f"/api/locations/{shelf['id']}").status_code == 409


def test_label_path_keeps_innermost_locations():
    from archive.physical_views import label_path
    assert label_path(["Shelf", "Box"]) == "Shelf / Box"
    long = ["Studio scaffale grande", "Armadio in fondo al corridoio", "Scatola 2026", "Cartella blu"]
    text = label_path(long)
    assert text.startswith("… / ") and text.endswith("Scatola 2026 / Cartella blu") and len(text) <= 60
    assert label_path(["x" * 80]).startswith("…") and len(label_path(["x" * 80])) == 60
    assert label_path([]) == ""


@pytest.mark.django_db
def test_sticker_label_never_breaks_code_and_clamps_text():
    owner = get_user_model().objects.create_user("printer", password="secure-password-1")
    document = Document.objects.create(
        owner=owner, title="Avviso condominio mirtillo " * 4, original_name="a.pdf", original_path="originals/a.pdf",
        original_mime="application/pdf", original_sha256="e" * 64, original_size=10,
    )
    client = Client()
    client.force_login(owner)
    parent = None
    for name in ["Studio scaffale", "Scatola 2026 con nome lungo", "Cartella condominio"]:
        parent = _json(client, "post", "/api/locations", {"name": name, "parent_id": parent and parent["id"]}).json()
    copy = _json(client, "post", f"/api/documents/{document.id}/copies", {"location_id": parent["id"]}).json()
    html = client.get(f"/api/copies/{copy['id']}/label").content.decode()
    assert "white-space:nowrap" in html and "-webkit-line-clamp:3" in html
    assert re.search(r'<div class="code" style="font-size:(\d+(\.\d)?)pt">' + copy["sticker_code"] + "</div>", html)
    assert "Cartella condominio</div>" in html
    location_html = client.get(f"/api/locations/{parent['id']}/label").content.decode()
    assert f'>{parent["sticker_code"]}</div>' in location_html
    from archive.physical_views import code_font_pt
    assert code_font_pt("R-7JVVQTRH") == 12.0
    assert 9 <= code_font_pt("R-WWWWWWWW") < 10
