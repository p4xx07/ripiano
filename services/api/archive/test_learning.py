import hashlib
import json
import random
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.auto_filing import apply_learned_filing
from archive.classification import apply_rules, filing_suggestions
from archive.learning import THRESHOLD, predict, train_owner
from archive.models import AutoFilingPolicy, Correspondent, Document, DocumentTag, DocumentType, FilingModel, FilingRule, Tag, TagOverride

PASSWORD = "secure-password-1"
VOCABULARY = {
    "Enel": "bolletta energia elettrica consumo kilowattora contatore fornitura luce",
    "Comune": "tributi tassa rifiuti avviso pagamento comunale imposta immobili",
    "Clinica": "referto esame sangue visita medico ambulatorio analisi laboratorio",
}
FILLER = "documento allegato numero cliente servizio periodo importo totale scadenza codice riferimento".split()


def make(owner, title, text, correspondent=None, tags=(), manual=True):
    digest = hashlib.sha256(f"{title}{random.random()}".encode()).hexdigest()
    document = Document.objects.create(
        owner=owner, title=title, original_name=f"{digest[:8]}.pdf", original_path=f"originals/{digest[:2]}/{digest}.pdf",
        original_mime="application/pdf", original_sha256=digest, original_size=10, status=Document.Status.READY,
        extracted_text=text, correspondent=correspondent,
        correspondent_origin=Document.FilingOrigin.MANUAL if correspondent and manual else Document.FilingOrigin.NONE,
    )
    for tag in tags:
        DocumentTag.objects.create(document=document, tag=tag, origin=DocumentTag.Origin.MANUAL)
    return document


def text_for(name, rng):
    words = VOCABULARY[name].split()
    return " ".join(rng.sample(words, 5) + rng.sample(FILLER, 6))


@pytest.mark.django_db
def test_learned_model_suggests_with_calibrated_probability():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    rng = random.Random(3)
    senders = {name: Correspondent.objects.create(owner=owner, name=name) for name in VOCABULARY}
    health = Tag.objects.create(owner=owner, name="Health")
    house = Tag.objects.create(owner=owner, name="House")
    for index in range(16):
        for name, sender in senders.items():
            make(owner, f"{name} {index}", text_for(name, rng), sender, tags=[health] if name == "Clinica" else [house] if name == "Comune" else [])
    train_owner(owner.pk)
    model = FilingModel.objects.get(owner=owner)
    assert model.status == FilingModel.Status.READY and model.examples == 48, (model.metrics, model.examples)
    metrics = model.metrics["correspondents"]
    assert metrics["ready"] and metrics["labels"] == 3 and metrics["accuracy"] >= 0.9
    assert metrics["precision"] >= 0.9 and metrics["brier"] < 0.1
    assert metrics["tested_suggestions"] >= 20
    assert metrics["auto_precision"] >= 0.95 and metrics["auto_tested_suggestions"] >= 20
    assert model.metrics["tags"]["ready"]

    new = make(owner, "Nuovo documento", text_for("Comune", rng))
    predicted = predict(new, new.title, new.extracted_text)
    assert predicted["correspondents"][0][0] == str(senders["Comune"].id)
    assert predicted["correspondents"][0][1] >= THRESHOLD
    assert metrics["auto_precision"] >= 0.95 and predicted["correspondents"][0][1] >= 0.9
    suggestions = filing_suggestions(new)
    top = suggestions["correspondents"][0]
    assert top["id"] == str(senders["Comune"].id) and top["probability"] >= THRESHOLD
    # Suggestions never change the document.
    new.refresh_from_db()
    assert new.correspondent_id is None

    medical = make(owner, "Referto", text_for("Clinica", rng))
    assert [item["name"] for item in filing_suggestions(medical)["tags"]] == ["Health"]

    # While the next model learns, or after it fails, the previous one keeps suggesting.
    FilingModel.objects.filter(owner=owner).update(status=FilingModel.Status.FAILED)
    assert predict(new, new.title, new.extracted_text)["correspondents"][0][0] == str(senders["Comune"].id)
    # Another person's model is never used.
    stranger = get_user_model().objects.create_user("stranger", password=PASSWORD)
    theirs = make(stranger, "Avviso", text_for("Comune", rng))
    assert predict(theirs, theirs.title, theirs.extracted_text) == {}
    client = Client()
    client.force_login(owner)
    backfilled = client.post("/api/documents/bulk-learned-filing", json.dumps({"document_ids": [str(new.id)]}),
                             content_type="application/json")
    assert backfilled.status_code == 200 and backfilled.json()["updated"] == 1
    assert backfilled.json()["assignments"] >= 1 and backfilled.json()["skipped_ids"] == []
    assert not AutoFilingPolicy.objects.filter(owner=owner).exists()  # a one-time request does not enable new intake
    new.refresh_from_db()
    assert new.correspondent == senders["Comune"] and new.correspondent_origin == Document.FilingOrigin.LEARNED

    auto_target = make(owner, "Another new document", "tributi " + text_for("Comune", rng))
    AutoFilingPolicy.objects.create(owner=owner, enabled=True)
    assert apply_learned_filing(auto_target.id) >= 1
    auto_target.refresh_from_db()
    assert auto_target.correspondent == senders["Comune"] and auto_target.correspondent_origin == Document.FilingOrigin.LEARNED
    apply_rules(auto_target)
    auto_target.refresh_from_db()
    assert auto_target.correspondent == senders["Comune"] and auto_target.correspondent_origin == Document.FilingOrigin.LEARNED
    FilingRule.objects.create(owner=owner, kind=FilingRule.Kind.CORRESPONDENT,
                              correspondent=senders["Enel"], pattern="tributi")
    apply_rules(auto_target)
    auto_target.refresh_from_db()
    assert auto_target.correspondent == senders["Enel"] and auto_target.correspondent_origin == Document.FilingOrigin.RULE


@pytest.mark.django_db
def test_bulk_learned_filing_validates_the_whole_selection_before_writing():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    other = get_user_model().objects.create_user("other", password=PASSWORD)
    owned = make(owner, "Owned", "taxes council payment reference")
    foreign = make(other, "Foreign", "taxes council payment reference")
    client = Client()
    client.force_login(owner)
    url = "/api/documents/bulk-learned-filing"
    with patch("archive.auto_filing.apply_learned_filing") as apply:
        assert client.post(url, json.dumps({"document_ids": [str(owned.id), str(foreign.id)]}),
                           content_type="application/json").status_code == 404
        assert client.post(url, json.dumps({"document_ids": [str(owned.id)] * 2}),
                           content_type="application/json").status_code == 400
        assert client.post(url, json.dumps({"document_ids": ["bad-id"]}), content_type="application/json").status_code == 400
        assert client.post(url, json.dumps({"document_ids": []}), content_type="application/json").status_code == 400
        apply.assert_not_called()
    assert Client().post(url, json.dumps({"document_ids": [str(owned.id)]}), content_type="application/json").status_code == 401
    single = client.post(url, json.dumps({"document_ids": [str(owned.id)]}), content_type="application/json")
    assert single.status_code == 200 and single.json() == {
        "updated": 0, "assignments": 0, "skipped": 1, "skipped_ids": [str(owned.id)],
    }


@pytest.mark.django_db
def test_bulk_learned_filing_reports_assignment_after_a_model_change_during_prediction():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    sender = Correspondent.objects.create(owner=owner, name="Council")
    target = make(owner, "Council notice", "taxes council payment reference")
    record = FilingModel.objects.create(owner=owner, status=FilingModel.Status.READY, payload=b"test model",
                                        metrics={"correspondents": {"ready": True, "auto_precision": 0.98,
                                                                      "auto_tested_suggestions": 25}}, trained_at=timezone.now())
    predictions = {"correspondents": [(str(sender.id), 0.99)]}
    calls = []

    def predict_after_retrain(*_args):
        calls.append(1)
        if len(calls) == 1:
            record.metrics = {**record.metrics, "revision": 2}
            record.save(update_fields=["metrics"])
        return predictions

    client = Client()
    client.force_login(owner)
    with patch("archive.auto_filing._load", return_value={"trained": True}), patch(
            "archive.auto_filing.predict", side_effect=predict_after_retrain):
        response = client.post("/api/documents/bulk-learned-filing", json.dumps({"document_ids": [str(target.id)]}),
                               content_type="application/json")
    assert len(calls) == 2
    assert response.status_code == 200 and response.json() == {
        "updated": 1, "assignments": 1, "skipped": 0, "skipped_ids": [],
    }
    target.refresh_from_db()
    assert target.correspondent == sender and target.correspondent_origin == Document.FilingOrigin.LEARNED


@pytest.mark.django_db
def test_random_labels_produce_no_confident_suggestions():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    rng = random.Random(11)
    senders = [Correspondent.objects.create(owner=owner, name=f"Sender {index}") for index in range(3)]
    everything = " ".join(VOCABULARY.values()).split() + FILLER
    for index in range(60):
        make(owner, f"Doc {index}", " ".join(rng.sample(everything, 10)), rng.choice(senders))
    train_owner(owner.pk)
    metrics = FilingModel.objects.get(owner=owner).metrics["correspondents"]
    # With nothing to learn, calibration keeps probabilities low, so almost nothing is shown.
    assert metrics["coverage"] <= 0.1


@pytest.mark.django_db
def test_too_few_examples_and_retrain_endpoint(django_capture_on_commit_callbacks):
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    sender = Correspondent.objects.create(owner=owner, name="Only")
    make(owner, "One", "bolletta energia contatore fornitura", sender)
    client = Client()
    client.force_login(owner)
    assert client.get("/api/filing-model").json()["status"] == "none"
    with patch("archive.tasks.train_filing_model.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            first = client.post("/api/filing-model")
        assert first.status_code == 202 and first.json()["status"] == "queued"
        delay.assert_called_once_with(owner.pk)
        assert client.post("/api/filing-model").status_code == 409
    train_owner(owner.pk)
    status = client.get("/api/filing-model").json()
    assert status["status"] == "not_enough" and status["metrics"]["correspondents"]["ready"] is False
    assert client.post("/api/filing-model").status_code == 429  # cooldown after a run
    # A run whose worker died is reported as stopped, and a new one can start.
    FilingModel.objects.filter(owner=owner).update(status=FilingModel.Status.TRAINING, started_at=timezone.now() - timedelta(hours=1), trained_at=timezone.now() - timedelta(hours=1))
    assert client.get("/api/filing-model").json()["status"] == "failed"
    with patch("archive.tasks.train_filing_model.delay", side_effect=OSError("broker down")):
        with django_capture_on_commit_callbacks(execute=True):
            assert client.post("/api/filing-model").status_code == 202
    assert "could not start" in client.get("/api/filing-model").json()["error"]
    assert Client().get("/api/filing-model").status_code == 401


@pytest.mark.django_db
def test_opt_in_auto_filing_fills_only_confident_unclaimed_fields():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    other = get_user_model().objects.create_user("other", password=PASSWORD)
    sender = Correspondent.objects.create(owner=owner, name="Council")
    kind = DocumentType.objects.create(owner=owner, name="Notice")
    tag = Tag.objects.create(owner=owner, name="Taxes")
    removed = Tag.objects.create(owner=owner, name="Removed by me")
    foreign = Tag.objects.create(owner=other, name="Private")
    target = make(owner, "Council notice", "taxes council payment reference")
    TagOverride.objects.create(document=target, tag=removed)
    metrics = {name: {"ready": True, "auto_precision": 0.98, "auto_tested_suggestions": 25} for name in ("tags", "correspondents", "document_types")}
    FilingModel.objects.create(owner=owner, status=FilingModel.Status.READY, payload=b"test model", metrics=metrics, trained_at=timezone.now())
    predictions = {
        "tags": [(str(removed.id), 0.99), (str(foreign.id), 0.98), (str(tag.id), 0.97)],
        "correspondents": [(str(sender.id), 0.96)],
        "document_types": [(str(kind.id), 0.91)],
    }
    with patch("archive.auto_filing._load", return_value={"trained": True}), patch("archive.auto_filing.predict", return_value=predictions):
        assert apply_learned_filing(target.id) == 0  # off by default
        client = Client()
        client.force_login(owner)
        assert client.get("/api/filing-model").json()["auto_apply"] is False
        assert client.patch("/api/filing-model", json.dumps({"auto_apply": "yes"}), content_type="application/json").status_code == 400
        enabled = client.patch("/api/filing-model", json.dumps({"auto_apply": True}), content_type="application/json")
        assert enabled.status_code == 200 and enabled.json()["auto_apply"] is True
        assert apply_learned_filing(target.id) == 3
        assert apply_learned_filing(target.id) == 0  # idempotent
        target.refresh_from_db()
        assert (target.correspondent, target.document_type) == (sender, kind)
        assert (target.correspondent_origin, target.document_type_origin) == (Document.FilingOrigin.LEARNED,) * 2
        assert list(DocumentTag.objects.filter(document=target).values_list("tag_id", "origin")) == [(tag.id, DocumentTag.Origin.LEARNED)]

        # Human clear, input rules, and prior tag removals are final, even when retried.
        manual = make(owner, "Another notice", "taxes council payment reference")
        manual.correspondent_origin = Document.FilingOrigin.MANUAL
        manual.document_type_origin = Document.FilingOrigin.SOURCE
        manual.save(update_fields=["correspondent_origin", "document_type_origin"])
        TagOverride.objects.create(document=manual, tag=tag)
        TagOverride.objects.create(document=manual, tag=removed)
        assert apply_learned_filing(manual.id) == 0
        assert not DocumentTag.objects.filter(document=manual).exists()

        # The local model cannot assign another person's tag, and turning it off is immediate.
        disabled = client.patch("/api/filing-model", json.dumps({"auto_apply": False}), content_type="application/json")
        assert disabled.status_code == 200 and disabled.json()["auto_apply"] is False
        assert apply_learned_filing(make(owner, "Third notice", "taxes council payment reference").id) == 0
        assert not AutoFilingPolicy.objects.filter(owner=other).exists()


@pytest.mark.django_db
def test_auto_filing_rejects_unproven_predictions():
    owner = get_user_model().objects.create_user("owner", password=PASSWORD)
    sender = Correspondent.objects.create(owner=owner, name="Council")
    target = make(owner, "Notice", "taxes council payment reference")
    AutoFilingPolicy.objects.create(owner=owner, enabled=True)
    record = FilingModel.objects.create(owner=owner, status=FilingModel.Status.READY, payload=b"test model",
                                        metrics={"correspondents": {"ready": True, "precision": 0.99, "auto_precision": 0.94, "auto_tested_suggestions": 25}}, trained_at=timezone.now())
    with patch("archive.auto_filing._load", return_value={"trained": True}), patch("archive.auto_filing.predict", return_value={"correspondents": [(str(sender.id), 0.99)]}):
        assert apply_learned_filing(target.id) == 0  # held-out quality gate
        record.metrics = {"correspondents": {"ready": True, "auto_precision": 0.98, "auto_tested_suggestions": 25}}
        record.save(update_fields=["metrics"])
        with patch("archive.auto_filing.predict", return_value={"correspondents": [(str(sender.id), 0.89)]}):
            assert apply_learned_filing(target.id) == 0  # per-document confidence gate
        record.metrics = {"correspondents": {"ready": True, "auto_precision": 0.98, "auto_tested_suggestions": 1}}
        record.save(update_fields=["metrics"])
        assert apply_learned_filing(target.id) == 0  # too few held-out predictions to trust
