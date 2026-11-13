import hashlib
import random
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.classification import filing_suggestions
from archive.learning import THRESHOLD, predict, train_owner
from archive.models import Correspondent, Document, DocumentTag, FilingModel, Tag

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
    assert model.metrics["tags"]["ready"]

    new = make(owner, "Nuovo documento", text_for("Comune", rng))
    predicted = predict(new, new.title, new.extracted_text)
    assert predicted["correspondents"][0][0] == str(senders["Comune"].id)
    assert predicted["correspondents"][0][1] >= THRESHOLD
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
