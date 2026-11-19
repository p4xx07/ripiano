"""Workflow assignment actions: title template, storage path, custom field values, and sharing."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.utils import timezone

from archive.messages_it import EXACT
from archive.models import (Correspondent, CustomField, CustomFieldValue, Document, DocumentAccess, DocumentEvent, StoragePath, Workflow,
                            WorkflowRun)
from archive.storage_paths import render_title, validate_title_template
from archive.workflows import run_for_document


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1")


def document(owner, title="scan_0001", text="Invoice from Acme Energy", **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path="originals/aa/x.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10,
                                   status=Document.Status.READY, extracted_text=text, processed_at=timezone.now(), **values)


def client_for(user, **headers):
    client = Client(**headers)
    client.force_login(user)
    return client


def workflow_events(target):
    return list(DocumentEvent.objects.filter(document=target, actor_kind=DocumentEvent.ActorKind.WORKFLOW))


@pytest.mark.django_db
def test_title_template_renders_after_sender_is_set_and_is_recorded(owner):
    acme = Correspondent.objects.create(owner=owner, name="Acme")
    Workflow.objects.create(owner=owner, name="Name bills", trigger=Workflow.Trigger.ADDED, set_correspondent=acme,
                            title_template="{correspondent} bill {year}-{month} ({original_filename})")
    target = document(owner, document_date=date(2026, 3, 9))

    run_for_document(target, "added")
    target.refresh_from_db()
    assert target.title == "Acme bill 2026-03 (scan_0001)"
    run = WorkflowRun.objects.get(document=target)
    assert "set sender Acme" in run.detail and "set title Acme bill 2026-03 (scan_0001)" in run.detail
    [event] = workflow_events(target)
    assert event.actor_label == "Name bills"
    assert {"field": "title", "from": "scan_0001", "to": "Acme bill 2026-03 (scan_0001)"} in event.changes


def test_title_templates_are_validated_and_rendered_safely():
    assert validate_title_template("{correspondent} – {date}") == ""
    assert validate_title_template("") and validate_title_template("x" * 201) and validate_title_template("a\nb")
    assert "{nope}" in validate_title_template("{nope} bill")


@pytest.mark.django_db
def test_rendered_titles_are_one_line_capped_and_never_empty(owner):
    target = document(owner, title="Long")
    target.original_name = "a\tb  c.pdf"
    assert render_title("{original_filename}", target) == "a b c"
    assert len(render_title("{title}" * 10, Document(title="y" * 290, original_name="z.pdf", created_at=timezone.now()))) == 300
    assert render_title("   ", target) == ""
    Workflow.objects.create(owner=owner, name="Blank", trigger=Workflow.Trigger.ADDED, title_template="   ")
    run_for_document(target, "added")
    target.refresh_from_db()
    assert target.title == "Long"  # an empty result never replaces the title


@pytest.mark.django_db
def test_a_title_storage_path_or_field_set_by_hand_is_never_overwritten(owner):
    path = StoragePath.objects.create(owner=owner, name="By year", template="{year}")
    mine = StoragePath.objects.create(owner=owner, name="Mine", template="mine")
    amount = CustomField.objects.create(owner=owner, name="Amount", kind=CustomField.Kind.NUMBER)
    Workflow.objects.create(owner=owner, name="Auto", trigger=Workflow.Trigger.UPDATED, title_template="Auto {date}", set_storage_path=path,
                            set_custom_fields=[{"field_id": str(amount.id), "kind": "number", "value": "10"}])
    target = document(owner)
    client = client_for(owner)

    # The person's title edit triggers the "updated" workflow, which keeps that title.
    assert client.patch(f"/api/documents/{target.id}", {"title": "My chosen title"}, content_type="application/json").status_code == 200
    target.refresh_from_db()
    assert target.title == "My chosen title"
    assert target.storage_path == path  # not chosen by hand, so the workflow set it
    assert CustomFieldValue.objects.get(document=target, field=amount).value == "10"

    client.patch(f"/api/documents/{target.id}", {"storage_path_id": str(mine.id)}, content_type="application/json")
    client.put(f"/api/documents/{target.id}/custom-fields/{amount.id}", {"value": 99}, content_type="application/json")
    client.patch(f"/api/documents/{target.id}", {"title": "Still mine"}, content_type="application/json")
    target.refresh_from_db()
    assert (target.title, target.storage_path) == ("Still mine", mine)
    assert CustomFieldValue.objects.get(document=target, field=amount).value == "99"


@pytest.mark.django_db
def test_title_is_applied_when_only_automation_changed_it(owner):
    Workflow.objects.create(owner=owner, name="Rename", trigger=Workflow.Trigger.ADDED, title_template="Bill {added_date}")
    target = document(owner)
    DocumentEvent.objects.create(document=target, actor_kind=DocumentEvent.ActorKind.AGENT, actor_label="Mac worker",
                                 changes=[{"field": "title", "from": "scan_0001", "to": "Agent title"}])
    run_for_document(target, "added")
    target.refresh_from_db()
    assert target.title == f"Bill {target.created_at.date().isoformat()}"


@pytest.mark.django_db
def test_storage_path_and_custom_fields_are_set_and_recorded(owner):
    path = StoragePath.objects.create(owner=owner, name="Bills", template="{correspondent}/{year}")
    paid = CustomField.objects.create(owner=owner, name="Paid", kind=CustomField.Kind.BOOLEAN)
    due = CustomField.objects.create(owner=owner, name="Due", kind=CustomField.Kind.DATE)
    client = client_for(owner)
    created = client.post("/api/workflows", {
        "name": "File bills", "trigger": "added", "set_storage_path_id": str(path.id),
        "set_custom_fields": [{"field_id": str(paid.id), "value": False}, {"field_id": str(due.id), "value": "2026-12-01"}],
    }, content_type="application/json")
    assert created.status_code == 201, created.content
    body = created.json()
    assert body["set_storage_path_id"] == str(path.id)
    assert body["set_custom_fields"] == [{"field_id": str(paid.id), "value": False}, {"field_id": str(due.id), "value": "2026-12-01"}]
    target = document(owner)

    run_for_document(target, "added")
    target.refresh_from_db()
    assert target.storage_path == path
    assert dict(CustomFieldValue.objects.filter(document=target).values_list("field__name", "value")) == {"Paid": "false", "Due": "2026-12-01"}
    detail = WorkflowRun.objects.get(document=target).detail
    assert "set storage path Bills" in detail and "set field Paid to no" in detail and "set field Due to 2026-12-01" in detail
    [event] = workflow_events(target)
    assert {"field": "storage_path", "from": None, "to": "Bills"} in event.changes
    assert {"field": "custom_field", "name": "Paid", "from": None, "to": "false"} in event.changes


@pytest.mark.django_db
def test_a_saved_value_that_no_longer_fits_its_field_is_skipped(owner):
    note = CustomField.objects.create(owner=owner, name="Reference", kind=CustomField.Kind.NUMBER)
    Workflow.objects.create(owner=owner, name="Ref", trigger=Workflow.Trigger.ADDED,
                            set_custom_fields=[{"field_id": str(note.id), "kind": "text", "value": "ABC-1"}])
    target = document(owner)
    run_for_document(target, "added")
    assert not CustomFieldValue.objects.filter(document=target).exists()
    assert "skipped field Reference" in WorkflowRun.objects.get(document=target).detail


@pytest.mark.django_db
def test_sharing_adds_or_raises_grants_and_never_removes_them(owner):
    anna = get_user_model().objects.create_user("anna", password="secure-password-2")
    bruno = get_user_model().objects.create_user("bruno", password="secure-password-3")
    family = Group.objects.create(name="Family")
    target = document(owner)
    DocumentAccess.objects.create(document=target, user=bruno, level=DocumentAccess.Level.EDIT)
    kept = get_user_model().objects.create_user("carla", password="secure-password-4")
    DocumentAccess.objects.create(document=target, user=kept, level=DocumentAccess.Level.VIEW)
    client = client_for(owner)
    created = client.post("/api/workflows", {
        "name": "Share bills", "trigger": "added",
        "share_with": [{"kind": "person", "id": anna.id, "level": "edit"}, {"kind": "person", "id": bruno.id, "level": "view"},
                       {"kind": "group", "id": family.id, "level": "view"}],
    }, content_type="application/json")
    assert created.status_code == 201, created.content
    assert created.json()["share_with"][0] == {"kind": "person", "id": anna.id, "level": "edit"}

    run_for_document(target, "added")
    grants = {(grant.user.username if grant.user_id else grant.group.name): grant.level for grant in target.access_grants.all()}
    assert grants == {"anna": "edit", "bruno": "edit", "carla": "view", "Family": "view"}  # bruno is not lowered, carla stays
    detail = WorkflowRun.objects.get(document=target).detail
    assert "shared with anna (edit)" in detail and "shared with Family (view)" in detail and "bruno" not in detail
    [event] = workflow_events(target)
    assert {"field": "access", "kind": "person", "name": "anna", "from": None, "to": "edit"} in event.changes
    assert {"field": "access", "kind": "group", "name": "Family", "from": None, "to": "view"} in event.changes
    # Who else can see it is owner-only history.
    anna_view = client_for(anna).get(f"/api/documents/{target.id}/history").json()
    assert all(change["field"] != "access" for item in anna_view["events"] for change in item["changes"])

    # "Added" workflows act once per document.
    assert run_for_document(target, "added") == []


@pytest.mark.django_db
def test_assignment_validation_is_owner_scoped_and_translated(owner):
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    theirs_path = StoragePath.objects.create(owner=other, name="Theirs", template="x")
    theirs_field = CustomField.objects.create(owner=other, name="Theirs", kind=CustomField.Kind.TEXT)
    number = CustomField.objects.create(owner=owner, name="Total", kind=CustomField.Kind.NUMBER)
    off = get_user_model().objects.create_user("off", password="secure-password-3", is_active=False)
    client = client_for(owner)
    base = {"name": "Assign", "trigger": "added"}

    def error(extra, **headers):
        response = client.post("/api/workflows", {**base, **extra}, content_type="application/json", **headers)
        assert response.status_code == 400, response.content
        return response.json()["error"]

    assert "unknown placeholder: {nope}" in error({"title_template": "{nope}"})
    assert error({"title_template": "a\nb"}) == "Write a title template of up to 200 characters on one line"
    assert error({"set_storage_path_id": str(theirs_path.id)}) == "Storage path not found"
    assert error({"set_custom_fields": [{"field_id": str(theirs_field.id), "value": "x"}]}) == "Custom field not found"
    assert error({"set_custom_fields": [{"field_id": str(number.id), "value": "lots"}]}) == "Enter a number"
    assert error({"set_custom_fields": [{"field_id": str(number.id), "value": 1}, {"field_id": str(number.id), "value": 2}]}) == "Choose each custom field only once"
    assert error({"set_custom_fields": [{"field_id": str(number.id)}]}) == "Give each custom field a value"
    assert error({"share_with": [{"kind": "group", "id": 999999, "level": "view"}]}) == "Group not found"
    assert error({"share_with": [{"kind": "person", "id": off.id, "level": "view"}]}) == "Person not found"
    assert error({"share_with": [{"kind": "person", "id": owner.id, "level": "view"}]}).startswith("You already own")
    assert error({"share_with": [{"kind": "person", "id": other.id, "level": "admin"}]}).startswith("Choose a person or a group")
    assert Workflow.objects.count() == 0

    italian = error({"title_template": "{nope}"}, HTTP_ACCEPT_LANGUAGE="it")
    assert italian.startswith("Il modello di titolo usa un segnaposto sconosciuto: {nope}")
    assert error({"set_custom_fields": [{"field_id": str(number.id)}]}, HTTP_ACCEPT_LANGUAGE="it") == EXACT["Give each custom field a value"]
    assert error({"set_storage_path_id": str(theirs_path.id)}, HTTP_ACCEPT_LANGUAGE="it") == "Percorso di archiviazione non trovato"

    # The other person's workflow cannot use this owner's items either.
    mine = StoragePath.objects.create(owner=owner, name="Mine", template="x")
    response = client_for(other).post("/api/workflows", {**base, "set_storage_path_id": str(mine.id)}, content_type="application/json")
    assert response.json()["error"] == "Storage path not found"
