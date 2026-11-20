"""Conservative filing from an owner's local model, automatic or explicitly requested."""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction

from .classification import file_name_words
from .learning import AUTO_THRESHOLD, TEXT_CHARS, _load, predict
from .models import AutoFilingPolicy, Correspondent, Document, DocumentTag, DocumentType, FilingModel, SuggestionDismissal, Tag, TagOverride

logger = logging.getLogger(__name__)

MIN_HELD_OUT_PRECISION = 0.95
MIN_TESTED_SUGGESTIONS = 20
MAX_AUTO_TAGS = 3
_RETRY = object()


def _trusted(metrics, kind):
    measured = metrics.get(kind) or {}
    precision = measured.get("auto_precision")
    return (measured.get("ready") is True and isinstance(precision, (int, float))
            and precision >= MIN_HELD_OUT_PRECISION
            and measured.get("auto_tested_suggestions", 0) >= MIN_TESTED_SUGGESTIONS)


def apply_learned_filing(document_id, *, require_opt_in=True, expected_owner_id=None):
    """Fill only unclaimed fields and unsuppressed tags; return the number of new assignments.

    Prediction runs outside locks. The owner and document are locked before writing, then the
    consent (for automatic intake), model version, document text, and human choices are checked
    again. A retrain or edit during prediction causes a bounded fresh attempt with current data.
    """
    for _ in range(3):
        result = _apply_once(document_id, require_opt_in=require_opt_in, expected_owner_id=expected_owner_id)
        if result is not _RETRY:
            return result
    logger.warning("Local filing skipped document %s after repeated concurrent edits", document_id)
    return 0


def _apply_once(document_id, *, require_opt_in, expected_owner_id):
    snapshot = Document.objects.filter(pk=document_id).values(
        "id", "owner_id", "title", "extracted_text", "status", "trashed_at", "is_split_source", "original_name", "split_parent__original_name",
    ).first()
    if (not snapshot or snapshot["status"] != Document.Status.READY or snapshot["trashed_at"] or snapshot["is_split_source"]
            or (expected_owner_id is not None and snapshot["owner_id"] != expected_owner_id)):
        return 0
    owner_id = snapshot["owner_id"]
    if require_opt_in and not AutoFilingPolicy.objects.filter(owner_id=owner_id, enabled=True).exists():
        return 0
    record = FilingModel.objects.filter(owner_id=owner_id, trained_at__isnull=False).exclude(payload=b"").values("trained_at", "metrics").first()
    if record is None:
        return 0
    trusted = {kind for kind in ("tags", "correspondents", "document_types") if _trusted(record["metrics"], kind)}
    if not trusted:
        return 0
    try:
        model = _load(owner_id)
        predictions = predict(Document(owner_id=owner_id), snapshot["title"], snapshot["extracted_text"][:TEXT_CHARS], model,
                              file_name_words([snapshot])[snapshot["id"]]) if model else {}
    except Exception:  # noqa: BLE001 - a damaged model must never prevent archive intake
        logger.exception("Local auto-filing prediction failed for %s", document_id)
        return 0
    confident = {
        kind: [label for label, probability in predictions.get(kind, []) if probability >= AUTO_THRESHOLD]
        for kind in trusted
    }
    if not any(confident.values()):
        return 0
    with transaction.atomic():
        get_user_model().objects.select_for_update(no_key=True).get(pk=owner_id)
        if require_opt_in:
            policy = AutoFilingPolicy.objects.select_for_update().filter(owner_id=owner_id).first()
            if not policy or not policy.enabled:
                return 0
        current = FilingModel.objects.filter(owner_id=owner_id).values("trained_at", "metrics").first()
        locked = Document.objects.select_for_update().filter(pk=document_id, owner_id=owner_id).first()
        if not locked or locked.trashed_at or locked.status != Document.Status.READY or locked.is_split_source:
            return 0
        if (current is None or current["trained_at"] != record["trained_at"] or current["metrics"] != record["metrics"]
                or locked.title != snapshot["title"] or locked.extracted_text != snapshot["extracted_text"]):
            return _RETRY

        from . import history

        before = history.snapshot(locked)
        assignments = 0
        changed = []
        for kind, field, model_type in (
            ("correspondents", "correspondent", Correspondent),
            ("document_types", "document_type", DocumentType),
        ):
            if kind not in trusted or getattr(locked, f"{field}_origin") != Document.FilingOrigin.NONE or getattr(locked, f"{field}_id"):
                continue
            label = next(iter(confident.get(kind, [])), None)
            if label and SuggestionDismissal.objects.filter(document=locked, **{f"{field}_id": label}).exists():
                label = None  # the owner said this sender or type is wrong for this document
            if label and model_type.objects.filter(pk=label, owner_id=owner_id).exists():
                setattr(locked, f"{field}_id", label)
                setattr(locked, f"{field}_origin", Document.FilingOrigin.LEARNED)
                changed.extend([field, f"{field}_origin"])
                assignments += 1
        if changed:
            locked.save(update_fields=changed)

        if "tags" in trusted and confident.get("tags"):
            existing = {str(pk) for pk in DocumentTag.objects.filter(document=locked).values_list("tag_id", flat=True)}
            suppressed = {str(pk) for pk in TagOverride.objects.filter(document=locked).values_list("tag_id", flat=True)}
            wanted = [label for label in confident["tags"] if label not in existing | suppressed]
            available = {str(pk): pk for pk in Tag.objects.filter(owner_id=owner_id, pk__in=wanted).values_list("pk", flat=True)}
            capacity = min(MAX_AUTO_TAGS, max(0, 100 - len(existing)))
            added_tags = 0
            for label in wanted:
                if added_tags >= capacity:
                    break
                if label in available:
                    _, created = DocumentTag.objects.get_or_create(
                        document=locked, tag_id=available[label], defaults={"origin": DocumentTag.Origin.LEARNED},
                    )
                    added_tags += int(created)
            assignments += added_tags
        history.record(locked, before, action=history.Action.FILED_AUTOMATICALLY, actor_kind=history.Kind.LEARNED_FILING)
        return assignments
