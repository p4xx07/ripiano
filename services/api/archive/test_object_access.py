import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.utils import timezone

from archive.models import Correspondent, Document, DocumentAccess, DocumentTag, DocumentType, ObjectAccess, SavedView, Tag

User = get_user_model()


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def doc(owner, title="Lease", **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path=f"originals/aa/{title}.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10,
                                   status=Document.Status.READY, processed_at=timezone.now(), **values)


@pytest.fixture
def people(db):
    owner = User.objects.create_user("owner", password="secure-password-1")
    editor = User.objects.create_user("editor", password="secure-password-2")
    viewer = User.objects.create_user("viewer", password="secure-password-3")
    return owner, editor, viewer


def share(client, kind, item, **body):
    return client.post(f"/api/object-access/{kind}/{item.pk}", body, content_type="application/json")


@pytest.mark.django_db
def test_owner_shares_objects_and_recipients_see_them(people):
    owner, editor, viewer = people
    house = Tag.objects.create(owner=owner, name="House", color="#112233")
    landlord = Correspondent.objects.create(owner=owner, name="Landlord")
    view = SavedView.objects.create(owner=owner, name="House papers", tag=house)
    family = Group.objects.create(name="Family")
    viewer.groups.add(family)
    owner_client = client_for(owner)
    assert share(owner_client, "tag", house, user_id=editor.pk, level="edit").status_code == 201
    assert share(owner_client, "tag", house, group_id=family.pk).status_code == 201
    assert share(owner_client, "correspondent", landlord, user_id=editor.pk).status_code == 201
    assert share(owner_client, "saved_view", view, group_id=family.pk).status_code == 201
    assert share(owner_client, "tag", house, user_id=owner.pk).status_code == 400
    assert share(owner_client, "tag", house, user_id=editor.pk, group_id=family.pk).status_code == 400
    assert share(owner_client, "folder", house, user_id=editor.pk).status_code == 404
    assert share(client_for(editor), "tag", house, user_id=viewer.pk).status_code == 404  # only the owner shares
    grants = owner_client.get(f"/api/object-access/tag/{house.pk}").json()["grants"]
    assert [(grant["target"]["name"], grant["level"]) for grant in grants] == [("editor", "edit"), ("Family", "view")]

    editor_view = client_for(editor).get("/api/shared-filing").json()
    assert [(item["name"], item["level"], item["owner"]["name"]) for item in editor_view["tags"]] == [("House", "edit", "owner")]
    assert [item["name"] for item in editor_view["correspondents"]] == ["Landlord"] and editor_view["saved_views"] == []
    viewer_view = client_for(viewer).get("/api/shared-filing").json()
    assert [item["level"] for item in viewer_view["tags"]] == ["view"]
    assert viewer_view["saved_views"][0]["tag_id"] == str(house.pk)
    assert client_for(owner).get("/api/shared-filing").json()["tags"] == []  # your own objects are not "shared with you"


@pytest.mark.django_db
def test_edit_recipients_file_shared_documents_with_shared_objects_only(people):
    owner, editor, _ = people
    house, private = Tag.objects.create(owner=owner, name="House"), Tag.objects.create(owner=owner, name="Private")
    landlord = Correspondent.objects.create(owner=owner, name="Landlord")
    lease = DocumentType.objects.create(owner=owner, name="Lease")
    secret_type = DocumentType.objects.create(owner=owner, name="Secret")
    document = doc(owner)
    DocumentTag.objects.create(document=document, tag=private)
    DocumentAccess.objects.create(document=document, user=editor, level=DocumentAccess.Level.EDIT)
    owner_client = client_for(owner)
    for kind, item in (("tag", house), ("correspondent", landlord), ("document_type", lease)):
        share(owner_client, kind, item, user_id=editor.pk)
    editor_client = client_for(editor)
    url = f"/api/documents/{document.pk}"

    def patch(body):
        return editor_client.patch(url, body, content_type="application/json")

    filed = patch({"correspondent_id": str(landlord.pk), "document_type_id": str(lease.pk), "add_tag_id": str(house.pk)})
    assert filed.status_code == 200
    assert filed.json()["correspondent"]["name"] == "Landlord" and sorted(tag["name"] for tag in filed.json()["tags"]) == ["House", "Private"]
    assert patch({"document_type_id": str(secret_type.pk)}).status_code == 403
    assert patch({"add_tag_id": str(private.pk)}).status_code == 403
    assert patch({"storage_path_id": None}).status_code == 403  # archive details stay with the owner
    cleared = patch({"tags": []})
    assert [tag["name"] for tag in cleared.json()["tags"]] == ["Private"]  # only the shared tag was removed

    # A view-only document grant cannot file, even with shared objects.
    DocumentAccess.objects.filter(document=document, user=editor).update(level=DocumentAccess.Level.VIEW)
    assert patch({"add_tag_id": str(house.pk)}).status_code == 403


@pytest.mark.django_db
def test_recipients_with_edit_access_can_rename_but_not_delete(people):
    owner, editor, viewer = people
    house = Tag.objects.create(owner=owner, name="House")
    Tag.objects.create(owner=owner, name="Car")
    view = SavedView.objects.create(owner=owner, name="Bills")
    owner_client = client_for(owner)
    share(owner_client, "tag", house, user_id=editor.pk, level="edit")
    share(owner_client, "tag", house, user_id=viewer.pk)
    share(owner_client, "saved_view", view, user_id=editor.pk, level="edit")
    editor_client = client_for(editor)
    renamed = editor_client.patch(f"/api/shared-filing/tag/{house.pk}", {"name": "Home", "color": "#aabbcc"}, content_type="application/json")
    assert renamed.status_code == 200 and renamed.json()["name"] == "Home"
    assert editor_client.patch(f"/api/shared-filing/tag/{house.pk}", {"name": "car"}, content_type="application/json").status_code == 400
    assert editor_client.patch(f"/api/shared-filing/tag/{house.pk}", {"parent_id": None}, content_type="application/json").status_code == 403
    assert client_for(viewer).patch(f"/api/shared-filing/tag/{house.pk}", {"name": "X"}, content_type="application/json").status_code == 403
    assert editor_client.delete(f"/api/tags/{house.pk}").status_code == 404  # deleting stays with the owner
    edited = editor_client.patch(f"/api/shared-filing/saved_view/{view.pk}", {"query": "enel", "date_from": "2026-01-01"},
                                 content_type="application/json").json()
    assert edited["query"] == "enel" and edited["date_from"] == "2026-01-01"


@pytest.mark.django_db
def test_shared_list_filters_by_shared_objects_and_grants_end_with_the_object(people):
    owner, editor, viewer = people
    house, car = Tag.objects.create(owner=owner, name="House"), Tag.objects.create(owner=owner, name="Car")
    first, second = doc(owner, "Lease"), doc(owner, "Insurance")
    DocumentTag.objects.create(document=first, tag=house)
    DocumentTag.objects.create(document=second, tag=car)
    for item in (first, second):
        DocumentAccess.objects.create(document=item, user=viewer)
    owner_client = client_for(owner)
    share(owner_client, "tag", house, user_id=viewer.pk)
    viewer_client = client_for(viewer)
    filtered = viewer_client.get("/api/documents", {"view": "shared", "tag_id": str(house.pk)}).json()["documents"]
    assert [item["title"] for item in filtered] == ["Lease"]
    assert viewer_client.get("/api/documents", {"view": "shared", "tag_id": str(car.pk)}).status_code == 400  # not shared
    owner_client.delete(f"/api/tags/{house.pk}")
    assert not ObjectAccess.objects.exists()
    assert client_for(editor).get("/api/shared-filing").json()["tags"] == []
