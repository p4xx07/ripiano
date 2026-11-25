import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from archive.models import Tag
from archive.starter_tags import STARTER_TAGS

User = get_user_model()
PASSWORD = "secure-password-1"
STARTER_COUNT = sum(1 + len(children) for _, _, children in STARTER_TAGS)


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def tag_tree(user):
    return {tag.name: (tag.parent.name if tag.parent_id else None) for tag in Tag.objects.filter(owner=user).select_related("parent")}


@pytest.mark.django_db
def test_first_owner_starts_with_english_starter_tags_matching_paper_categories(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_SETUP_KEY="known-setup-key"):
        client = Client()
        body = {"username": "owner", "password": "long-enough-password", "setup_key": "known-setup-key"}
        assert client.post("/api/setup", json.dumps(body), content_type="application/json").status_code == 201
    owner = User.objects.get(username="owner")
    tree = tag_tree(owner)
    assert len(tree) == STARTER_COUNT
    assert tree["Home"] is None and tree["Utilities"] == "Home" and tree["Car insurance"] == "Vehicles"
    # The top-level names line up with the default paper category names (plus Health for Medical, via the web alias).
    assert {name for name, parent in tree.items() if parent is None} == {
        "Home", "Finance and taxes", "Health", "Vehicles", "Personal", "Events and travel", "Warranties"}


@pytest.mark.django_db
def test_people_created_by_the_owner_get_their_own_starter_tags():
    admin = User.objects.create_superuser("admin", password=PASSWORD)
    created = client_for(admin).post("/api/people", json.dumps(
        {"username": "anna", "password": "anna-long-password-7", "current_password": PASSWORD}), content_type="application/json")
    assert created.status_code == 201
    anna = User.objects.get(username="anna")
    assert len(tag_tree(anna)) == STARTER_COUNT
    # Seeding one account never touches another.
    assert Tag.objects.filter(owner=admin).count() == 0


@pytest.mark.django_db
def test_existing_accounts_are_untouched_until_they_ask_and_then_only_missing_tags_are_added():
    owner = User.objects.create_user("owner", password=PASSWORD)
    other = User.objects.create_user("other", password=PASSWORD)
    # The owner already renamed or created some tags in their own words.
    home = Tag.objects.create(owner=owner, name="HOME", color="#000000", description="mine")
    Tag.objects.create(owner=owner, name="Bank", color="#111111")  # top level, not under Finance
    client = client_for(owner)
    assert len(client.get("/api/tags").json()["tags"]) == 2

    response = client.post("/api/tags/starter")
    assert response.status_code == 201
    assert response.json()["added"] == STARTER_COUNT - 2
    tree = tag_tree(owner)
    assert len(tree) == STARTER_COUNT
    # Existing tags keep their name, colour, description and place; missing children go under them.
    home.refresh_from_db()
    assert home.name == "HOME" and home.color == "#000000" and home.description == "mine"
    assert tree["Utilities"] == "HOME" and tree["Bank"] is None
    assert len(response.json()["tags"]) == STARTER_COUNT

    again = client.post("/api/tags/starter")
    assert again.status_code == 200 and again.json()["added"] == 0
    assert Tag.objects.filter(owner=other).count() == 0


@pytest.mark.django_db
def test_starter_tags_need_a_signed_in_person_and_post():
    assert Client().post("/api/tags/starter").status_code in (401, 403)
    owner = User.objects.create_user("owner", password=PASSWORD)
    assert client_for(owner).get("/api/tags/starter").status_code == 405
    assert Tag.objects.count() == 0


def test_every_starter_tag_passes_the_same_checks_as_a_tag_made_by_hand():
    from archive.metadata_views import COLOR

    names = [name for name, _, children in STARTER_TAGS for name in (name, *children)]
    assert len({name.lower() for name in names}) == len(names)
    for name, color, children in STARTER_TAGS:
        assert COLOR.fullmatch(color)
        assert all(0 < len(value) <= 100 and value == value.strip() for value in (name, *children))


@pytest.mark.django_db
def test_a_child_name_already_used_in_another_case_or_place_is_skipped():
    owner = User.objects.create_user("owner", password=PASSWORD)
    school = Tag.objects.create(owner=owner, name="school")  # lower case, top level
    added = client_for(owner).post("/api/tags/starter").json()["added"]
    assert added == STARTER_COUNT - 1
    school.refresh_from_db()
    assert school.name == "school" and school.parent_id is None
    assert not Tag.objects.filter(owner=owner, name="School").exists()


@pytest.mark.django_db
def test_setup_leaves_no_owner_behind_when_starter_tags_fail(tmp_path):
    from unittest.mock import patch

    with override_settings(MEDIA_ROOT=tmp_path, RIPIANO_SETUP_KEY="known-setup-key"):
        client = Client(raise_request_exception=False)
        body = json.dumps({"username": "owner", "password": "long-enough-password", "setup_key": "known-setup-key"})
        with patch("archive.starter_tags.Tag.objects.create", side_effect=RuntimeError("database hiccup")):
            assert client.post("/api/setup", body, content_type="application/json").status_code == 500
        assert not User.objects.exists()
        # Setup can simply be retried.
        assert client.post("/api/setup", body, content_type="application/json").status_code == 201
    assert Tag.objects.filter(owner__username="owner").count() == STARTER_COUNT


@pytest.mark.django_db
def test_people_creation_failing_on_starter_tags_is_not_reported_as_a_taken_username():
    from django.db import IntegrityError
    from unittest.mock import patch

    admin = User.objects.create_superuser("admin", password=PASSWORD)
    client = client_for(admin)
    client.raise_request_exception = False
    with patch("archive.starter_tags.Tag.objects.create", side_effect=IntegrityError("boom")):
        response = client.post("/api/people", json.dumps(
            {"username": "anna", "password": "anna-long-password-7", "current_password": PASSWORD}), content_type="application/json")
    assert response.status_code == 500
    assert not User.objects.filter(username="anna").exists()


@pytest.mark.django_db
def test_an_api_token_can_add_its_own_starter_tags_without_csrf():
    owner = User.objects.create_superuser("owner", password=PASSWORD)
    other = User.objects.create_user("other", password=PASSWORD)
    created = client_for(owner).post("/api/account/tokens", json.dumps({"name": "Script", "password": PASSWORD, "expires_in_days": 30}),
                                     content_type="application/json").json()
    api = Client(enforce_csrf_checks=True, HTTP_AUTHORIZATION=f"Token {created['token']}")
    assert api.post("/api/tags/starter").status_code == 201
    assert Tag.objects.filter(owner=owner).count() == STARTER_COUNT
    assert Tag.objects.filter(owner=other).count() == 0
