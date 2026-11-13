import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, override_settings

from archive.models import ApiToken, Correspondent, DocumentNote, Tag
from archive.test_share_links import make_document

User = get_user_model()
PASSWORD = "secure-password-1"


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def send(client, method, url, body):
    return getattr(client, method)(url, json.dumps(body), content_type="application/json")


@pytest.mark.django_db
def test_admin_manages_people_and_groups_and_others_only_see_names():
    admin = User.objects.create_superuser("admin", password=PASSWORD)
    admin_client = client_for(admin)
    family = send(admin_client, "post", "/api/groups", {"name": "Family"})
    assert family.status_code == 201
    assert send(admin_client, "post", "/api/people", {"username": "anna", "password": "anna-long-password-7"}).json()["error"] == "Your password is not correct"
    created = send(admin_client, "post", "/api/people", {"username": "anna", "password": "anna-long-password-7", "groups": [family.json()["id"]], "current_password": PASSWORD})
    assert created.status_code == 201
    anna = User.objects.get(username="anna")
    assert created.json()["groups"] == [family.json()["id"]] and not created.json()["is_admin"]
    assert send(admin_client, "post", "/api/people", {"username": "ANNA", "password": "anna-long-password-7", "current_password": PASSWORD}).status_code == 409
    assert send(admin_client, "post", "/api/people", {"username": "bob", "password": "short", "current_password": PASSWORD}).status_code == 400
    assert send(admin_client, "post", "/api/people", {"username": "bad name!", "password": "anna-long-password-7", "current_password": PASSWORD}).status_code == 400

    anna_client = client_for(anna)
    listing = anna_client.get("/api/people").json()
    assert {"id": anna.pk, "username": "anna", "name": ""} in listing["people"]
    assert "is_active" not in listing["people"][0] and "member_ids" not in listing["groups"][0]
    assert send(anna_client, "post", "/api/people", {"username": "mallory", "password": "mallory-long-pass-9"}).status_code == 403
    assert send(anna_client, "patch", f"/api/people/{admin.pk}", {"is_active": False, "current_password": "anna-long-password-7"}).status_code == 403
    assert send(anna_client, "patch", f"/api/groups/{family.json()['id']}", {"member_ids": [anna.pk]}).status_code == 403
    assert send(anna_client, "post", "/api/groups", {"name": "Mine"}).status_code == 403

    assert send(admin_client, "patch", f"/api/people/{admin.pk}", {"is_active": False, "current_password": PASSWORD}).json()["error"] == "You can't turn off your own account"
    assert send(admin_client, "patch", f"/api/people/{admin.pk}", {"password": "admin-new-password-9", "current_password": PASSWORD}).status_code == 400
    other_admin = User.objects.create_superuser("admin2", password=PASSWORD)
    assert send(admin_client, "patch", f"/api/people/{other_admin.pk}", {"password": "taken-over-password-1", "current_password": PASSWORD}).status_code == 403
    assert send(admin_client, "patch", f"/api/people/{anna.pk}", {"password": "anna-new-password-8"}).status_code == 400
    reset = send(admin_client, "patch", f"/api/people/{anna.pk}", {"password": "anna-new-password-8", "current_password": PASSWORD})
    assert reset.status_code == 200
    assert anna_client.get("/api/session").json()["authenticated"] is False  # the old session ends
    off = send(admin_client, "patch", f"/api/people/{anna.pk}", {"is_active": False, "current_password": PASSWORD})
    assert off.json()["is_active"] is False
    assert Client().post("/api/session", {"username": "anna", "password": "anna-new-password-8"}, content_type="application/json").status_code == 401
    assert "anna" not in [person["username"] for person in client_for(User.objects.create_user("carl", password=PASSWORD)).get("/api/people").json()["people"]]

    renamed = send(admin_client, "patch", f"/api/groups/{family.json()['id']}", {"name": "Household", "member_ids": [admin.pk]})
    assert renamed.json() == {"id": family.json()["id"], "name": "Household", "member_ids": [admin.pk]}
    assert send(admin_client, "post", "/api/groups", {"name": "household"}).status_code == 409
    assert admin_client.delete(f"/api/groups/{family.json()['id']}").status_code == 200
    assert not Group.objects.exists()


@pytest.mark.django_db
def test_api_tokens_cannot_manage_people():
    admin = User.objects.create_superuser("admin", password=PASSWORD)
    raw = client_for(admin).post("/api/account/tokens", {"name": "script", "password": PASSWORD}, content_type="application/json").json()["token"]
    token_client = Client(HTTP_AUTHORIZATION=f"Token {raw}")
    assert token_client.get("/api/people").status_code == 403
    assert token_client.post("/api/account/password", {"current_password": PASSWORD, "new_password": "x-long-password-1"}, content_type="application/json").status_code == 403
    assert token_client.post("/api/people", {"username": "x", "password": "x-long-password-1"}, content_type="application/json").status_code == 403
    assert ApiToken.objects.count() == 1


@pytest.mark.django_db
def test_sharing_a_document_with_a_person_or_group(tmp_path):
    owner = User.objects.create_user("owner", password=PASSWORD)
    viewer = User.objects.create_user("viewer", password=PASSWORD)
    editor = User.objects.create_user("editor", password=PASSWORD)
    stranger = User.objects.create_user("stranger", password=PASSWORD)
    family = Group.objects.create(name="Family")
    editor.groups.add(family)
    media = tmp_path / "media"
    document, original, _ = make_document(owner, media, "lease.pdf")
    private, _, _ = make_document(owner, media, "private.pdf")
    tag = Tag.objects.create(owner=owner, name="House")
    document.tag_links.create(tag=tag)
    owner_client, viewer_client, editor_client, stranger_client = map(client_for, (owner, viewer, editor, stranger))
    url = f"/api/documents/{document.id}"

    with override_settings(MEDIA_ROOT=media):
        assert viewer_client.get(url).status_code == 404
        assert send(viewer_client, "post", f"{url}/access", {"user_id": viewer.pk}).status_code == 404  # only the owner shares
        assert send(owner_client, "post", f"{url}/access", {"user_id": owner.pk}).status_code == 400
        assert send(owner_client, "post", f"{url}/access", {"user_id": viewer.pk, "group_id": family.pk}).status_code == 400
        view_grant = send(owner_client, "post", f"{url}/access", {"user_id": viewer.pk})
        assert view_grant.status_code == 201 and view_grant.json()["level"] == "view"
        assert send(owner_client, "post", f"{url}/access", {"group_id": family.pk, "level": "edit"}).status_code == 201
        assert [grant["target"]["name"] for grant in owner_client.get(f"{url}/access").json()["grants"]] == ["viewer", "Family"]

        # The viewer sees the document, its files, and notes, but not the owner's other documents or controls.
        shared = viewer_client.get("/api/documents?view=shared").json()["documents"]
        assert [item["id"] for item in shared] == [str(document.id)]
        assert shared[0]["access"] == "view" and shared[0]["shared_by"] == "owner" and shared[0]["tags"][0]["name"] == "House"
        assert viewer_client.get("/api/documents").json()["documents"] == []
        assert viewer_client.get(f"/api/documents/{private.id}").status_code == 404
        assert viewer_client.get(url).json()["access"] == "view"
        assert b"".join(viewer_client.get(f"{url}/original").streaming_content) == original
        assert send(viewer_client, "patch", url, {"title": "Mine now"}).status_code == 403
        assert send(viewer_client, "post", f"{url}/notes", {"body": "hello"}).status_code == 403
        for owner_only in (f"{url}/access", f"{url}/shares", f"{url}/versions", f"{url}/custom-fields", f"{url}/copies"):
            assert viewer_client.get(owner_only).status_code == 404, owner_only
        assert viewer_client.post(f"{url}/trash").status_code == 404
        assert viewer_client.get("/api/documents?view=shared&tag_id=" + str(tag.id)).status_code == 400
        for clause in ("asn:7", "sticker:R-", "is:tagged", "field:Amount=1"):
            assert viewer_client.get(f"/api/documents?view=shared&q={clause}").status_code == 400, clause
        document.physical_copies.create(sticker_code="R-SECRET42")
        assert viewer_client.get("/api/documents?view=shared&q=SECRET42").json()["documents"] == []
        for owner_only in ("similar", "links", "export", "filing-suggestions", "pages"):
            assert editor_client.get(f"{url}/{owner_only}").status_code == 404, owner_only

        # The group member may change details and add notes, but not filing.
        assert editor_client.get("/api/documents?view=shared&q=Private").json()["documents"][0]["access"] == "edit"
        changed = send(editor_client, "patch", url, {"title": "Lease 2026", "action_status": "open", "action_due_date": "2026-12-01"})
        assert changed.status_code == 200 and changed.json()["title"] == "Lease 2026"
        sender = Correspondent.objects.create(owner=owner, name="Landlord")
        assert send(editor_client, "patch", url, {"correspondent_id": str(sender.id)}).status_code == 403
        assert send(editor_client, "patch", url, {"tags": []}).status_code == 403
        note = send(editor_client, "post", f"{url}/notes", {"body": "Paid the deposit"})
        assert note.status_code == 201
        owner_note = DocumentNote.objects.create(document=document, author=owner, body="Owner note")
        assert editor_client.delete(f"{url}/notes/{owner_note.id}").status_code == 403
        assert editor_client.delete(f"{url}/notes/{note.json()['id']}").status_code == 200
        assert stranger_client.get(url).status_code == 404
        assert stranger_client.get("/api/documents?view=shared").json()["documents"] == []

        # Removing the grant, leaving the group, or trashing the document ends access.
        assert send(owner_client, "patch", f"{url}/access/{view_grant.json()['id']}", {"level": "edit"}).json()["level"] == "edit"
        assert owner_client.delete(f"{url}/access/{view_grant.json()['id']}").status_code == 200
        assert viewer_client.get(url).status_code == 404
        editor.groups.remove(family)
        assert editor_client.get(url).status_code == 404
        editor.groups.add(family)
        assert owner_client.post(f"{url}/trash").status_code == 200
        assert editor_client.get(url).status_code == 404
        assert editor_client.get("/api/documents?view=shared").json()["documents"] == []


@pytest.mark.django_db
def test_turned_off_people_lose_shared_access(tmp_path):
    owner = User.objects.create_user("owner", password=PASSWORD)
    reader = User.objects.create_user("reader", password=PASSWORD)
    media = tmp_path / "media"
    document, _, _ = make_document(owner, media, "a.pdf")
    document.access_grants.create(user=reader)
    reader_client = client_for(reader)
    with override_settings(MEDIA_ROOT=media):
        assert reader_client.get(f"/api/documents/{document.id}").status_code == 200
        reader.is_active = False
        reader.save()
        assert reader_client.get(f"/api/documents/{document.id}").status_code == 401
        owner_client = client_for(owner)
        assert send(owner_client, "post", f"/api/documents/{document.id}/access", {"user_id": reader.pk}).status_code == 400


@pytest.mark.django_db
def test_editor_changes_do_not_run_owner_workflows_and_tokens_cannot_share(tmp_path):
    from unittest.mock import patch

    owner = User.objects.create_user("owner", password=PASSWORD)
    editor = User.objects.create_user("editor", password=PASSWORD)
    media = tmp_path / "media"
    document, _, _ = make_document(owner, media, "a.pdf")
    document.access_grants.create(user=editor, level="edit")
    with override_settings(MEDIA_ROOT=media), patch("archive.views.run_for_document") as workflows:
        assert send(client_for(editor), "patch", f"/api/documents/{document.id}", {"document_date": "2026-01-02"}).json()["document_date"] == "2026-01-02"
        workflows.assert_not_called()
        send(client_for(owner), "patch", f"/api/documents/{document.id}", {"title": "Owner change"})
        workflows.assert_called_once()
    raw = client_for(owner).post("/api/account/tokens", {"name": "script", "password": PASSWORD}, content_type="application/json").json()["token"]
    token_client = Client(HTTP_AUTHORIZATION=f"Token {raw}")
    assert send(token_client, "post", f"/api/documents/{document.id}/access", {"user_id": editor.pk}).status_code == 403
    assert token_client.get(f"/api/documents/{document.id}/access").status_code == 200


@pytest.mark.django_db
def test_people_change_their_own_password_and_stay_signed_in():
    user = User.objects.create_user("member", password=PASSWORD)
    client, other_device = client_for(user), client_for(user)
    assert send(client, "post", "/api/account/password", {"current_password": "wrong", "new_password": "member-new-password-2"}).status_code == 400
    assert send(client, "post", "/api/account/password", {"current_password": PASSWORD, "new_password": "short"}).status_code == 400
    assert send(client, "post", "/api/account/password", {"current_password": PASSWORD, "new_password": "member-new-password-2"}).json() == {"changed": True}
    assert client.get("/api/session").json()["authenticated"] is True
    assert other_device.get("/api/session").json()["authenticated"] is False


@pytest.mark.django_db
def test_the_last_active_admin_stays_on():
    admin = User.objects.create_superuser("admin", password=PASSWORD)
    other = User.objects.create_superuser("other", password=PASSWORD)
    client = client_for(admin)
    assert send(client, "patch", f"/api/people/{other.pk}", {"is_active": False, "current_password": PASSWORD}).status_code == 200
    other.refresh_from_db()
    assert other.is_active is False
    # admin is now the only active admin; another admin turning them off is impossible, and so is self-deactivation.
    assert send(client, "patch", f"/api/people/{admin.pk}", {"is_active": False, "current_password": PASSWORD}).status_code == 400
