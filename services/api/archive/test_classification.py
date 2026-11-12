import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.classification import apply_rules
from archive.models import ClassificationRule, Correspondent, Document, DocumentTag, DocumentType, FilingRule, Tag, TagOverride
from archive.tasks import reclassify_filing_candidates, reclassify_owner, reclassify_tag_candidates
from ripiano.celery import app as celery_app


def test_reclassification_and_backups_do_not_block_document_processing_queue():
    route = celery_app.amqp.router.route
    assert route({}, "archive.tasks.process_document")["queue"].name == "celery"
    for name in (
        "archive.tasks.reclassify_owner",
        "archive.tasks.reclassify_filing_candidates",
        "archive.tasks.reclassify_tag_candidates",
        "archive.tasks.backup_archive",
    ):
        assert route({}, name)["queue"].name == "maintenance"


def ready_document(owner, text="Invoice for electricity"):
    return Document.objects.create(
        owner=owner, title="April bill", original_name="bill.pdf", original_path="originals/bill.pdf",
        original_mime="application/pdf", original_sha256="a" * 64, original_size=10,
        status=Document.Status.READY, extracted_text=text,
    )


@pytest.mark.django_db
def test_manual_examples_suggest_filing_without_changing_document():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    source = ready_document(owner, "Electricity invoice from Acme Energy for May")
    target = ready_document(owner, "Acme Energy electricity invoice for June")
    source.title = "Acme electricity May"
    target.title = "Acme electricity June"
    source.save(update_fields=["title"])
    target.save(update_fields=["title"])
    tag = Tag.objects.create(owner=owner, name="Utilities")
    sender = Correspondent.objects.create(owner=owner, name="Acme Energy")
    kind = DocumentType.objects.create(owner=owner, name="Invoice")
    DocumentTag.objects.create(document=source, tag=tag, origin=DocumentTag.Origin.MANUAL)
    source.correspondent = sender
    source.correspondent_origin = Document.FilingOrigin.MANUAL
    source.document_type = kind
    source.document_type_origin = Document.FilingOrigin.MANUAL
    source.save(update_fields=["correspondent", "correspondent_origin", "document_type", "document_type_origin"])
    client = Client()
    client.force_login(owner)
    result = client.get(f"/api/documents/{target.id}/filing-suggestions")
    assert result.status_code == 200
    suggestions = result.json()
    assert [item["name"] for item in suggestions["tags"]] == ["Utilities"]
    assert [item["name"] for item in suggestions["correspondents"]] == ["Acme Energy"]
    assert [item["name"] for item in suggestions["document_types"]] == ["Invoice"]
    assert suggestions["tags"][0]["example"]["id"] == str(source.id)
    assert {"acme", "electricity"}.issubset(set(suggestions["tags"][0]["shared_terms"]))
    assert not DocumentTag.objects.filter(document=target).exists()
    target.refresh_from_db()
    assert target.correspondent is None and target.document_type is None

    TagOverride.objects.create(document=target, tag=tag)
    target.correspondent_origin = Document.FilingOrigin.MANUAL
    target.save(update_fields=["correspondent_origin"])
    suppressed = client.get(f"/api/documents/{target.id}/filing-suggestions").json()
    assert suppressed["tags"] == [] and suppressed["correspondents"] == []
    assert len(suppressed["document_types"]) == 1


@pytest.mark.django_db
def test_filing_suggestions_require_owner_ready_and_manual_example():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    target = ready_document(owner, "Acme Energy electricity invoice")
    foreign = ready_document(other, "Acme Energy electricity invoice")
    rule_source = ready_document(owner, "Acme Energy electricity invoice")
    tag = Tag.objects.create(owner=owner, name="Private")
    other_tag = Tag.objects.create(owner=other, name="Other")
    DocumentTag.objects.create(document=foreign, tag=other_tag, origin=DocumentTag.Origin.MANUAL)
    DocumentTag.objects.create(document=rule_source, tag=tag, origin=DocumentTag.Origin.RULE)
    client = Client()
    client.force_login(owner)
    endpoint = f"/api/documents/{target.id}/filing-suggestions"
    assert client.get(endpoint).json() == {"tags": [], "correspondents": [], "document_types": []}
    assert client.get(f"/api/documents/{foreign.id}/filing-suggestions").status_code == 404
    DocumentTag.objects.filter(document=rule_source).update(origin=DocumentTag.Origin.MANUAL)
    assert len(client.get(endpoint).json()["tags"]) == 1
    rule_source.trashed_at = timezone.now()
    rule_source.save(update_fields=["trashed_at"])
    assert client.get(endpoint).json()["tags"] == []
    target.status = Document.Status.PENDING
    target.save(update_fields=["status"])
    assert client.get(endpoint).json()["tags"] == []


@pytest.mark.django_db
def test_filing_suggestions_skip_existing_tags_cleared_types_and_foreign_or_trashed_examples(django_assert_max_num_queries):
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    text = "Acme Energy electricity invoice meter reading"
    target = ready_document(owner, text)
    source = ready_document(owner, text)
    trashed = ready_document(owner, text)
    foreign = ready_document(other, text)
    kept = Tag.objects.create(owner=owner, name="Already here")
    DocumentTag.objects.create(document=source, tag=kept, origin=DocumentTag.Origin.MANUAL)
    DocumentTag.objects.create(document=target, tag=kept, origin=DocumentTag.Origin.MANUAL)
    kind = DocumentType.objects.create(owner=owner, name="Invoice")
    source.document_type = kind
    source.document_type_origin = Document.FilingOrigin.MANUAL
    source.save(update_fields=["document_type", "document_type_origin"])
    trashed_sender = Correspondent.objects.create(owner=owner, name="Trashed sender")
    trashed.correspondent = trashed_sender
    trashed.correspondent_origin = Document.FilingOrigin.MANUAL
    trashed.trashed_at = timezone.now()
    trashed.save(update_fields=["correspondent", "correspondent_origin", "trashed_at"])
    foreign_sender = Correspondent.objects.create(owner=other, name="Foreign sender")
    foreign.correspondent = foreign_sender
    foreign.correspondent_origin = Document.FilingOrigin.MANUAL
    foreign.save(update_fields=["correspondent", "correspondent_origin"])
    client = Client()
    client.force_login(owner)
    endpoint = f"/api/documents/{target.id}/filing-suggestions"
    with django_assert_max_num_queries(8):
        result = client.get(endpoint).json()
    assert result["tags"] == [] and result["correspondents"] == []
    assert [item["name"] for item in result["document_types"]] == ["Invoice"]
    target.document_type_origin = Document.FilingOrigin.MANUAL
    target.save(update_fields=["document_type_origin"])
    assert client.get(endpoint).json()["document_types"] == []


@pytest.mark.django_db
def test_filing_suggestions_ignore_common_filler_words():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    source = ready_document(owner, "Please read this with your doctor")
    target = ready_document(owner, "Please read this with your bank")
    source.title = "Clinic"
    target.title = "Bank"
    source.save(update_fields=["title"])
    target.save(update_fields=["title"])
    tag = Tag.objects.create(owner=owner, name="Health")
    DocumentTag.objects.create(document=source, tag=tag, origin=DocumentTag.Origin.MANUAL)
    client = Client()
    client.force_login(owner)
    assert client.get(f"/api/documents/{target.id}/filing-suggestions").json()["tags"] == []


@pytest.mark.django_db
def test_filing_suggestions_ignore_words_common_to_many_examples():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    target = ready_document(owner, "Scanner header archive copy stamp target notice")
    for index in range(6):
        example = ready_document(owner, f"Scanner header archive copy stamp example{index}")
        tag = Tag.objects.create(owner=owner, name=f"Topic {index}")
        DocumentTag.objects.create(document=example, tag=tag, origin=DocumentTag.Origin.MANUAL)
    client = Client()
    client.force_login(owner)
    assert client.get(f"/api/documents/{target.id}/filing-suggestions").json()["tags"] == []


@pytest.mark.django_db
def test_filing_suggestions_reject_weak_shared_scan_words():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    source = ready_document(owner, "Ripiano judge solar meter")
    target = ready_document(owner, "Ripiano judge insurance policy")
    source.title = "Solar meter"
    target.title = "Insurance policy"
    source.save(update_fields=["title"])
    target.save(update_fields=["title"])
    tag = Tag.objects.create(owner=owner, name="Solar")
    DocumentTag.objects.create(document=source, tag=tag, origin=DocumentTag.Origin.MANUAL)
    client = Client()
    client.force_login(owner)
    assert client.get(f"/api/documents/{target.id}/filing-suggestions").json()["tags"] == []


@pytest.mark.django_db
def test_filing_suggestions_prefer_whole_document_similarity():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    target = ready_document(owner, "Acme electricity nordkind lucekind billkind private notice")
    close = ready_document(owner, "Acme electricity nordkind lucekind billkind annual notice")
    weak = ready_document(owner, "Acme electricity notice")
    close_tag = Tag.objects.create(owner=owner, name="Utilities")
    weak_tag = Tag.objects.create(owner=owner, name="Old generic filing")
    DocumentTag.objects.create(document=close, tag=close_tag, origin=DocumentTag.Origin.MANUAL)
    DocumentTag.objects.create(document=weak, tag=weak_tag, origin=DocumentTag.Origin.MANUAL)
    client = Client()
    client.force_login(owner)
    result = client.get(f"/api/documents/{target.id}/filing-suggestions").json()
    assert [item["name"] for item in result["tags"]] == ["Utilities"]


@pytest.mark.django_db
def test_tag_keywords_file_existing_documents_and_correction_sticks():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    document = ready_document(owner)
    client = Client()
    client.force_login(owner)
    with patch("archive.metadata_views.reclassify_tag_candidates.delay"):
        response = client.post("/api/tags", json.dumps({"name": "Bills", "keywords": ["electricity"]}), content_type="application/json")
    assert response.status_code == 201
    tag_id = response.json()["id"]
    assert ClassificationRule.objects.filter(owner=owner, pattern="electricity").count() == 1

    reclassify_owner(owner.id)
    assert DocumentTag.objects.get(document=document).origin == DocumentTag.Origin.RULE
    assert client.get(f"/api/documents/{document.id}").json()["tags"][0]["name"] == "Bills"

    response = client.patch(f"/api/documents/{document.id}", json.dumps({"tags": []}), content_type="application/json")
    assert response.status_code == 200 and response.json()["tags"] == []
    apply_rules(document)
    assert not DocumentTag.objects.filter(document=document).exists()

    response = client.patch(f"/api/documents/{document.id}", json.dumps({"tags": [tag_id], "title": "New title", "document_date": "2026-04-01"}), content_type="application/json")
    assert response.status_code == 200
    assert response.json()["tags"][0]["origin"] == "manual"
    assert response.json()["document_date"] == "2026-04-01"
    apply_rules(document)
    assert DocumentTag.objects.get(document=document).origin == DocumentTag.Origin.MANUAL


@pytest.mark.django_db
def test_tag_phrase_rechecks_only_matching_field_and_rule_origin():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    text_match = ready_document(owner, text="Annual tax notice")
    title_only = ready_document(owner, text="No notice here")
    title_only.title = "Tax notice"
    title_only.save(update_fields=["title"])
    tag = Tag.objects.create(owner=owner, name="Tax")
    rule = ClassificationRule.objects.create(owner=owner, tag=tag, pattern="tax", field=ClassificationRule.Field.TEXT)
    DocumentTag.objects.create(document=title_only, tag=tag, origin=DocumentTag.Origin.MANUAL)

    with patch("archive.tasks.apply_rules", wraps=apply_rules) as classify:
        reclassify_tag_candidates(owner.id, tag.id, [{"pattern": rule.pattern, "field": rule.field}])
        assert classify.call_count == 1
    assert DocumentTag.objects.get(document=text_match, tag=tag).origin == DocumentTag.Origin.RULE
    assert DocumentTag.objects.get(document=title_only, tag=tag).origin == DocumentTag.Origin.MANUAL

    rule.delete()
    with patch("archive.tasks.apply_rules", wraps=apply_rules) as classify:
        reclassify_tag_candidates(owner.id, tag.id, [], deleted=True)
        assert classify.call_count == 1
    assert not DocumentTag.objects.filter(document=text_match, tag=tag).exists()
    assert DocumentTag.objects.get(document=title_only, tag=tag).origin == DocumentTag.Origin.MANUAL


@pytest.mark.django_db
def test_tags_and_rules_are_owner_isolated():
    alice = get_user_model().objects.create_user("alice", password="secure-password-1")
    bob = get_user_model().objects.create_user("bob", password="secure-password-2")
    tag = Tag.objects.create(owner=alice, name="Private")
    document = ready_document(alice)
    client = Client()
    client.force_login(bob)
    assert client.get("/api/tags").json()["tags"] == []
    assert client.patch(f"/api/documents/{document.id}", json.dumps({"tags": [str(tag.id)]}), content_type="application/json").status_code == 404
    assert client.post("/api/rules", json.dumps({"tag_id": str(tag.id), "pattern": "bill"}), content_type="application/json").status_code == 400

    own_document = ready_document(bob)
    assert client.patch(f"/api/documents/{own_document.id}", json.dumps({"tags": [str(tag.id)]}), content_type="application/json").status_code == 400
    assert not DocumentTag.objects.filter(document=own_document).exists()


@pytest.mark.django_db
def test_nested_tags_can_be_moved_without_cycles_and_parent_filter_finds_children():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    foreign = Tag.objects.create(owner=other, name="Foreign")
    document = ready_document(owner)
    client = Client()
    client.force_login(owner)

    def create(name, parent_id=None):
        return client.post("/api/tags", json.dumps({"name": name, "parent_id": parent_id}), content_type="application/json")

    root = create("Home")
    assert root.status_code == 201
    child = create("Insurance", root.json()["id"])
    assert child.status_code == 201
    grandchild = create("Policies", child.json()["id"])
    assert grandchild.status_code == 201
    assert grandchild.json()["parent_id"] == child.json()["id"]
    assert create("Wrong", str(foreign.id)).status_code == 400
    assert client.patch(f"/api/tags/{root.json()['id']}", json.dumps({"parent_id": str(foreign.id)}), content_type="application/json").status_code == 400
    assert client.patch(f"/api/tags/{root.json()['id']}", json.dumps({"parent_id": grandchild.json()["id"]}), content_type="application/json").status_code == 400
    assert client.patch(f"/api/tags/{child.json()['id']}", json.dumps({"parent_id": child.json()["id"]}), content_type="application/json").status_code == 400
    assert client.delete(f"/api/tags/{root.json()['id']}").status_code == 409

    DocumentTag.objects.create(document=document, tag_id=grandchild.json()["id"], origin=DocumentTag.Origin.MANUAL)
    for tag in (root, child, grandchild):
        result = client.get("/api/documents", {"tag_id": tag.json()["id"]}).json()
        assert result["counts"]["total"] == 1
        assert [item["id"] for item in result["documents"]] == [str(document.id)]
    DocumentTag.objects.create(document=document, tag_id=root.json()["id"], origin=DocumentTag.Origin.MANUAL)
    assert client.get("/api/documents", {"tag_id": root.json()["id"]}).json()["counts"]["total"] == 1
    moved = client.patch(f"/api/tags/{grandchild.json()['id']}", json.dumps({"parent_id": None}), content_type="application/json")
    assert moved.status_code == 200 and moved.json()["parent_id"] is None
    assert client.get("/api/documents", {"tag_id": child.json()["id"]}).json()["counts"]["total"] == 0
    assert client.get("/api/documents", {"tag_id": root.json()["id"]}).json()["counts"]["total"] == 1


@pytest.mark.django_db
def test_filing_phrases_choose_specific_match_and_preserve_manual_corrections():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    document = ready_document(owner, text="Permit notice from City of Milan")
    untouched = ready_document(owner, text="Permit notice from City of Milan")
    generic = Correspondent.objects.create(owner=owner, name="City")
    specific = Correspondent.objects.create(owner=owner, name="City of Milan")
    notice = DocumentType.objects.create(owner=owner, name="Permit notice")
    corrected_type = DocumentType.objects.create(owner=owner, name="Correspondence")
    foreign = Correspondent.objects.create(owner=other, name="Foreign")
    client = Client()
    client.force_login(owner)

    def create(kind, target, pattern, field="either"):
        return client.post("/api/filing-rules", json.dumps({
            "kind": kind, "target_id": str(target.id), "pattern": pattern, "field": field,
        }), content_type="application/json")

    with patch("archive.metadata_views.reclassify_filing_candidates.delay"):
        assert create("correspondent", generic, "City").status_code == 201
        specific_rule = create("correspondent", specific, "City of Milan")
        assert specific_rule.status_code == 201
        conflicting = create("correspondent", generic, "city of milan", "title")
        assert conflicting.status_code == 409
        assert create("document_type", notice, "Permit notice", "text").status_code == 201
        assert create("correspondent", specific, "City of Milan").status_code == 409
        assert create("correspondent", foreign, "secret").status_code == 400
    reclassify_owner(owner.id)
    document.refresh_from_db()
    assert document.correspondent == specific
    assert document.document_type == notice
    assert document.correspondent_origin == document.document_type_origin == Document.FilingOrigin.RULE
    untouched.refresh_from_db()
    assert untouched.document_type == notice
    assert len(client.get("/api/filing-rules?kind=correspondent").json()["rules"]) == 2

    cleared = client.patch(f"/api/documents/{document.id}", json.dumps({"correspondent_id": None}), content_type="application/json")
    assert cleared.json()["correspondent"] is None
    assert cleared.json()["correspondent_origin"] == Document.FilingOrigin.MANUAL
    corrected = client.patch(f"/api/documents/{document.id}", json.dumps({"document_type_id": str(corrected_type.id)}), content_type="application/json")
    assert corrected.json()["document_type_origin"] == Document.FilingOrigin.MANUAL
    reclassify_owner(owner.id)
    document.refresh_from_db()
    assert document.correspondent is None
    assert document.document_type == corrected_type

    with patch("archive.metadata_views.reclassify_filing_candidates.delay"):
        assert client.delete(f"/api/filing-rules/{specific_rule.json()['id']}").status_code == 200
        for rule in client.get("/api/filing-rules?kind=document_type").json()["rules"]:
            assert client.delete(f"/api/filing-rules/{rule['id']}").status_code == 200
    reclassify_owner(owner.id)
    document.refresh_from_db()
    untouched.refresh_from_db()
    assert document.correspondent is None
    assert document.document_type == corrected_type
    assert document.document_type_origin == Document.FilingOrigin.MANUAL
    assert untouched.document_type is None
    assert untouched.document_type_origin == Document.FilingOrigin.NONE

    client.force_login(other)
    assert client.get("/api/filing-rules").json()["rules"] == []
    assert client.delete(f"/api/filing-rules/{specific_rule.json()['id']}").status_code == 404
    assert FilingRule.objects.filter(owner=owner).count() == 1


@pytest.mark.django_db
def test_phrase_edit_only_rechecks_affected_documents():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    matching = ready_document(owner, text="A permit from Milan")
    unrelated = ready_document(owner, text="An electricity invoice")
    sender = Correspondent.objects.create(owner=owner, name="City of Milan")
    rule = FilingRule.objects.create(owner=owner, kind=FilingRule.Kind.CORRESPONDENT, correspondent=sender, pattern="Milan")

    with patch("archive.tasks.apply_rules", wraps=apply_rules) as classify:
        reclassify_filing_candidates(owner.id, rule.kind, sender.id, rule.pattern)
        assert classify.call_count == 1
    matching.refresh_from_db()
    assert matching.correspondent == sender

    rule.delete()
    with patch("archive.tasks.apply_rules", wraps=apply_rules) as classify:
        reclassify_filing_candidates(owner.id, FilingRule.Kind.CORRESPONDENT, sender.id, "Milan", deleted=True)
        assert classify.call_count == 1
    matching.refresh_from_db()
    unrelated.refresh_from_db()
    assert matching.correspondent is None
    assert unrelated.correspondent is None

    title_only = ready_document(owner, text="No city is named here")
    title_only.title = "Milan permit"
    title_only.save(update_fields=["title"])
    title_rule = FilingRule.objects.create(owner=owner, kind=FilingRule.Kind.CORRESPONDENT, correspondent=sender, pattern="Milan", field=FilingRule.Field.TITLE)
    with patch("archive.tasks.apply_rules", wraps=apply_rules) as classify:
        reclassify_filing_candidates(owner.id, title_rule.kind, sender.id, title_rule.pattern, title_rule.field)
        assert classify.call_count == 1
    title_only.refresh_from_db()
    matching.refresh_from_db()
    assert title_only.correspondent == sender
    assert matching.correspondent is None

    title_rule.delete()
    text_rule = FilingRule.objects.create(owner=owner, kind=FilingRule.Kind.CORRESPONDENT, correspondent=sender, pattern="Milan", field=FilingRule.Field.TEXT)
    with patch("archive.tasks.apply_rules", wraps=apply_rules) as classify:
        reclassify_filing_candidates(owner.id, text_rule.kind, sender.id, text_rule.pattern, text_rule.field)
        assert classify.call_count == 1
    matching.refresh_from_db()
    assert matching.correspondent == sender
