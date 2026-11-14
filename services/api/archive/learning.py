"""A small, local, calibrated filing model learned from a person's own manual filing.

Naive Bayes over the words of the title and the start of the text: one model each for sender and
document type (one label per document) and one-vs-rest models for tags (several labels). Raw Naive
Bayes scores are overconfident, so scores from held-out folds fit a Platt scaling that turns a
score into the probability that the suggestion is right. The reported precision and coverage come
from folds the calibration did not see. Suggestions are shown only above a probability threshold
and normally need a person to accept them. Owners can separately opt into conservative
automatic filing for new documents when held-out quality and per-document confidence are high.
"""

import json
import logging
import math
import random
import zlib
from collections import Counter, OrderedDict, defaultdict
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Substr
from django.utils import timezone

from .classification import _terms
from .models import Document, DocumentTag, FilingModel

logger = logging.getLogger(__name__)

TEXT_CHARS = 4000
MAX_DOCUMENTS = 5000
MAX_CALIBRATION_DOCUMENTS = 1000
MAX_VOCABULARY = 4000
MAX_TERMS_PER_DOCUMENT = 200
MAX_TAGS = 100
MIN_LABEL_EXAMPLES = 3
MIN_DOCUMENTS = 10
MIN_CALIBRATION_POINTS = 20
FOLDS = 5
THRESHOLD = 0.6  # Suggest only when the calibrated probability of being right is at least this.
AUTO_THRESHOLD = 0.9  # The separate opt-in automatic decision threshold.
STALE_AFTER = timedelta(minutes=35)  # longer than the task's hard time limit
RETRAIN_COOLDOWN = timedelta(minutes=10)
KINDS = ("correspondents", "document_types", "tags")


def features(title, text, rank=None):
    """The words a document is judged by. With a vocabulary rank, keep the most frequent words first."""
    terms = _terms(f"{title} {text[:TEXT_CHARS]}")
    if rank is None:
        return terms
    return sorted((term for term in terms if term in rank), key=rank.__getitem__)[:MAX_TERMS_PER_DOCUMENT]


def has_manual_filing(owner_id):
    manual_tags = DocumentTag.objects.filter(document=OuterRef("pk"), origin=DocumentTag.Origin.MANUAL)
    return Document.objects.filter(owner_id=owner_id, status=Document.Status.READY, trashed_at__isnull=True, is_split_source=False).filter(
        Exists(manual_tags) | Q(correspondent_origin=Document.FilingOrigin.MANUAL, correspondent__isnull=False)
        | Q(document_type_origin=Document.FilingOrigin.MANUAL, document_type__isnull=False))


def _examples(owner_id):
    rows = list(
        has_manual_filing(owner_id).order_by("-created_at", "-id")[:MAX_DOCUMENTS]
        .annotate(text_start=Substr("extracted_text", 1, TEXT_CHARS))
        .values("id", "title", "text_start", "correspondent_id", "correspondent_origin", "document_type_id", "document_type_origin")
    )
    manual, automatic = defaultdict(set), defaultdict(set)
    for document_id, tag_id, origin in DocumentTag.objects.filter(document_id__in=[row["id"] for row in rows]).values_list("document_id", "tag_id", "origin"):
        (manual if origin == DocumentTag.Origin.MANUAL else automatic)[document_id].add(str(tag_id))
    return [{
        "terms": features(row["title"], row["text_start"]),
        "correspondents": str(row["correspondent_id"]) if row["correspondent_origin"] == Document.FilingOrigin.MANUAL and row["correspondent_id"] else None,
        "document_types": str(row["document_type_id"]) if row["document_type_origin"] == Document.FilingOrigin.MANUAL and row["document_type_id"] else None,
        "tags": manual.get(row["id"], set()),
        # Tags a rule or agent added are not used to judge the model.
        "auto_tags": automatic.get(row["id"], set()),
    } for row in rows]


class _NaiveBayes:
    """Multinomial Naive Bayes over word presence, with add-one smoothing."""

    def __init__(self, vocabulary_size):
        self.size = vocabulary_size
        self.documents = Counter()
        self.term_counts = defaultdict(Counter)
        self.totals = Counter()

    def add(self, label, terms):
        self.documents[label] += 1
        self.term_counts[label].update(terms)
        self.totals[label] += len(terms)

    def log_likelihood(self, label, terms):
        counts, denominator = self.term_counts[label], self.totals[label] + self.size
        return sum(math.log((counts.get(term, 0) + 1) / denominator) for term in terms)

    def to_json(self):
        return {"documents": dict(self.documents), "terms": {label: dict(counts) for label, counts in self.term_counts.items()}, "totals": dict(self.totals)}

    @classmethod
    def from_json(cls, data, size):
        model = cls(size)
        model.documents = Counter(data["documents"])
        model.term_counts = defaultdict(Counter, {label: Counter(counts) for label, counts in data["terms"].items()})
        model.totals = Counter(data["totals"])
        return model


def _single_label_scores(model, terms):
    """Return (best label, log-odds that it is the right one among the known labels)."""
    total = sum(model.documents.values())
    scores = {label: math.log(count / total) + model.log_likelihood(label, terms) for label, count in model.documents.items()}
    if len(scores) < 2:
        return None, None
    best = max(scores, key=lambda label: (scores[label], label))
    others = [value for label, value in scores.items() if label != best]
    peak = max(others)
    rest = peak + math.log(sum(math.exp(value - peak) for value in others))
    return best, scores[best] - rest


def _tag_scores(positives, everything, terms, examples):
    """Log-odds per tag that the tag belongs, one-vs-rest against the other tagged documents."""
    result = {}
    all_counts = everything.term_counts["*"]
    for tag, count in positives.documents.items():
        negatives = examples - count
        if negatives <= 0:
            continue
        tag_counts = positives.term_counts[tag]
        positive_denominator = positives.totals[tag] + positives.size
        negative_denominator = everything.totals["*"] - positives.totals[tag] + positives.size
        score = math.log(count / negatives)
        for term in terms:
            inside = tag_counts.get(term, 0)
            score += math.log((inside + 1) / positive_denominator) - math.log((all_counts.get(term, 0) - inside + 1) / negative_denominator)
        result[tag] = score
    return result


def _fit_platt(points):
    """Fit p = sigmoid(a * score + b) by Newton's method with Platt's target smoothing.

    Two anchor points say a tie (score 0) is a coin flip, so a model that was never wrong on
    held-out documents still gives lower probabilities to weaker evidence.
    """
    points = list(points) + [(0.0, True), (0.0, False)]
    positives = sum(1 for _, label in points if label)
    negatives = len(points) - positives
    high, low = (positives + 1) / (positives + 2), 1 / (negatives + 2)
    targets = [high if label else low for _, label in points]
    a, b = 0.1, 0.0
    for _ in range(100):
        ga = gb = haa = hab = hbb = 0.0
        for (score, _), target in zip(points, targets):
            z = max(-35.0, min(35.0, a * score + b))
            p = 1 / (1 + math.exp(-z))
            weight = max(p * (1 - p), 1e-9)
            ga += (p - target) * score
            gb += p - target
            haa += weight * score * score
            hab += weight * score
            hbb += weight
        haa += 1e-6
        hbb += 1e-6
        determinant = haa * hbb - hab * hab
        if abs(determinant) < 1e-12:
            break
        step_a = (hbb * ga - hab * gb) / determinant
        step_b = (haa * gb - hab * ga) / determinant
        a, b = a - step_a, b - step_b
        if abs(step_a) < 1e-7 and abs(step_b) < 1e-7:
            break
    return [a, b]


def _probability(platt, score):
    z = max(-35.0, min(35.0, platt[0] * score + platt[1]))
    return 1 / (1 + math.exp(-z))


def _train_kind(kind, examples, vocabulary_size):
    if kind == "tags":
        labelled = [example for example in examples if example["tags"]]
        counts = Counter(tag for example in labelled for tag in example["tags"])
        known = {label for label, count in counts.most_common(MAX_TAGS) if count >= MIN_LABEL_EXAMPLES}
    else:
        labelled = [example for example in examples if example[kind]]
        counts = Counter(example[kind] for example in labelled)
        known = {label for label, count in counts.items() if count >= MIN_LABEL_EXAMPLES}
    if len(labelled) < MIN_DOCUMENTS or len(known) < (1 if kind == "tags" else 2):
        return None, {"examples": len(labelled), "labels": len(known), "ready": False}

    def build(items):
        if kind == "tags":
            positives, everything = _NaiveBayes(vocabulary_size), _NaiveBayes(vocabulary_size)
            for example in items:
                everything.add("*", example["terms"])
                for tag in example["tags"] & known:
                    positives.add(tag, example["terms"])
            return positives, everything, len(items)
        model = _NaiveBayes(vocabulary_size)
        for example in items:
            if example[kind] in known:
                model.add(example[kind], example["terms"])
        return model

    # Held-out folds: every scored document is judged by a model that never saw it. Scoring is
    # limited to a sample of documents to bound training time; the final model uses all of them.
    shuffled = labelled[:]
    random.Random(7).shuffle(shuffled)
    fold_points = [[] for _ in range(FOLDS)]  # per fold: [(document index, score, right)]
    for fold in range(FOLDS):
        built = build([example for index, example in enumerate(shuffled) if index % FOLDS != fold])
        for index in range(fold, min(len(shuffled), MAX_CALIBRATION_DOCUMENTS), FOLDS):
            example = shuffled[index]
            if kind == "tags":
                positives, everything, size = built
                for tag, score in _tag_scores(positives, everything, example["terms"], size).items():
                    if tag not in example["auto_tags"]:
                        fold_points[fold].append((index, score, tag in example["tags"]))
            else:
                label, score = _single_label_scores(built, example["terms"])
                if label is not None:
                    # A document whose label is too rare to learn still gets a guess, which is wrong.
                    fold_points[fold].append((index, score, label == example[kind]))
    points = [point for fold in fold_points for point in fold]
    if len(points) < MIN_CALIBRATION_POINTS:
        return None, {"examples": len(labelled), "labels": len(known), "ready": False}

    # Honest numbers: calibrate on some folds, measure on the others, then swap.
    shown = correct = auto_shown = auto_correct = 0
    with_suggestion, measured_documents, squared = set(), set(), []
    for measured in (set(range(0, FOLDS, 2)), set(range(1, FOLDS, 2))):
        platt = _fit_platt([(score, right) for fold in range(FOLDS) if fold not in measured for _, score, right in fold_points[fold]])
        for fold in measured:
            for index, score, right in fold_points[fold]:
                probability = _probability(platt, score)
                measured_documents.add(index)
                squared.append((probability - right) ** 2)
                if probability >= THRESHOLD:
                    shown += 1
                    correct += right
                    with_suggestion.add(index)
                if probability >= AUTO_THRESHOLD:
                    auto_shown += 1
                    auto_correct += right
    metrics = {
        "examples": len(labelled), "labels": len(known), "ready": True,
        "precision": round(correct / shown, 3) if shown else None,
        "tested_suggestions": shown,
        "auto_precision": round(auto_correct / auto_shown, 3) if auto_shown else None,
        "auto_tested_suggestions": auto_shown,
        "coverage": round(len(with_suggestion) / len(measured_documents), 3) if measured_documents else 0.0,
        "brier": round(sum(squared) / len(squared), 4) if squared else None,
    }
    if kind != "tags":
        metrics["accuracy"] = round(sum(1 for _, _, right in points if right) / len(points), 3)
    final = build(labelled)
    if kind == "tags":
        positives, everything, size = final
        data = {"positives": positives.to_json(), "everything": everything.to_json(), "examples": size}
    else:
        data = final.to_json()
    return {"model": data, "platt": _fit_platt([(score, right) for _, score, right in points])}, metrics


def train(owner_id):
    """Train from the owner's manual filing. Returns (payload bytes or b"", metrics, example count)."""
    examples = _examples(owner_id)
    frequency = Counter(term for example in examples for term in example["terms"])
    ordered = [term for term, count in frequency.most_common(MAX_VOCABULARY) if count >= 2]
    rank = {term: position for position, term in enumerate(ordered)}
    for example in examples:
        example["terms"] = sorted((term for term in example["terms"] if term in rank), key=rank.__getitem__)[:MAX_TERMS_PER_DOCUMENT]
    payload, metrics = {"vocabulary": ordered, "kinds": {}}, {}
    for kind in KINDS:
        trained, metrics[kind] = _train_kind(kind, examples, len(ordered))
        if trained:
            payload["kinds"][kind] = trained
    if not payload["kinds"]:
        return b"", metrics, len(examples)
    return zlib.compress(json.dumps(payload, separators=(",", ":")).encode()), metrics, len(examples)


def _record(owner_id):
    try:
        with transaction.atomic():
            FilingModel.objects.get_or_create(owner_id=owner_id)
    except IntegrityError:
        pass  # created by a concurrent request


def request_training(owner_id):
    """A person asked to learn now. Returns (record, refusal message or None)."""
    _record(owner_id)
    now = timezone.now()
    with transaction.atomic():
        record = FilingModel.objects.select_for_update().get(owner_id=owner_id)
        status, _ = status_of(record)
        if status in (FilingModel.Status.QUEUED, FilingModel.Status.TRAINING):
            return record, "Learning is already running"
        if record.trained_at and record.trained_at > now - RETRAIN_COOLDOWN:
            return record, "Ripiano learned a few minutes ago. Try again in 10 minutes."
        record.status, record.requested_at, record.error = FilingModel.Status.QUEUED, now, ""
        record.save(update_fields=["status", "requested_at", "error"])
        return record, None


def _claim(owner_id):
    """Start a run unless one is running. Returns the record, or None."""
    _record(owner_id)
    now = timezone.now()
    with transaction.atomic():
        record = FilingModel.objects.select_for_update().get(owner_id=owner_id)
        if record.status == FilingModel.Status.TRAINING and record.started_at and record.started_at > now - STALE_AFTER:
            return None
        record.status, record.started_at, record.error = FilingModel.Status.TRAINING, now, ""
        record.save(update_fields=["status", "started_at", "error"])
        return record


def train_owner(owner_id):
    record = _claim(owner_id)
    if record is None:
        return
    try:
        payload, metrics, count = train(owner_id)
    except Exception:
        logger.exception("Training the filing model failed for owner %s", owner_id)
        # The previous model stays in use; only the status records the failure.
        FilingModel.objects.filter(pk=record.pk).update(status=FilingModel.Status.FAILED, error="Learning stopped because of an error. The previous suggestions stay in use.")
        raise
    FilingModel.objects.filter(pk=record.pk).update(
        status=FilingModel.Status.READY if payload else FilingModel.Status.NOT_ENOUGH,
        payload=payload, metrics=metrics, examples=count, trained_at=timezone.now(),
    )


def status_of(record):
    """The status a person sees; a run that outlived the task limit is reported as stopped."""
    if record is None:
        return "none", ""
    if record.status in (FilingModel.Status.QUEUED, FilingModel.Status.TRAINING):
        since = record.started_at if record.status == FilingModel.Status.TRAINING else record.requested_at
        if since is None or since < timezone.now() - STALE_AFTER:
            return FilingModel.Status.FAILED, "Learning did not finish. Try again; the previous suggestions stay in use."
    return record.status, record.error


_cache = OrderedDict()  # (owner id, trained_at) -> model, for a few people per worker
CACHE_SIZE = 4


def _load(owner_id):
    # Any trained model is used, even while the next one is learning or after a failed run.
    trained_at = FilingModel.objects.filter(owner_id=owner_id, trained_at__isnull=False).exclude(payload=b"").values_list("trained_at", flat=True).first()
    if trained_at is None:
        return None
    key = (owner_id, trained_at)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    payload = FilingModel.objects.filter(owner_id=owner_id, trained_at=trained_at).values_list("payload", flat=True).first()
    if not payload:
        return None
    data = json.loads(zlib.decompress(bytes(payload)))
    rank = {term: position for position, term in enumerate(data["vocabulary"])}
    size = len(rank)
    model = {"rank": rank, "kinds": {}}
    for kind, trained in data["kinds"].items():
        if kind == "tags":
            built = (_NaiveBayes.from_json(trained["model"]["positives"], size), _NaiveBayes.from_json(trained["model"]["everything"], size), trained["model"]["examples"])
        else:
            built = _NaiveBayes.from_json(trained["model"], size)
        model["kinds"][kind] = (built, trained["platt"])
    for old in [cached for cached in _cache if cached[0] == owner_id]:
        del _cache[old]
    _cache[key] = model
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return model


def predict(document, title, text, model=None):
    """Return {kind: [(label id, probability)]} at or above the threshold, best first.

    Pass the first TEXT_CHARS characters of the text, as training does, so probabilities stay calibrated.
    """
    model = model or _load(document.owner_id)
    if model is None:
        return {}
    terms = features(title, text, model["rank"])
    if len(terms) < 2:
        return {}
    result = {}
    for kind, (built, platt) in model["kinds"].items():
        if kind == "tags":
            positives, everything, size = built
            scored = [(tag, _probability(platt, score)) for tag, score in _tag_scores(positives, everything, terms, size).items()]
        else:
            label, score = _single_label_scores(built, terms)
            scored = [(label, _probability(platt, score))] if label is not None else []
        result[kind] = sorted([item for item in scored if item[1] >= THRESHOLD], key=lambda item: (-item[1], item[0]))
    return result
