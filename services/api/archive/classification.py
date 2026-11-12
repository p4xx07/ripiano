"""Local, explainable rules that never delay document availability."""

import re
from collections import Counter

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Substr

from .models import ClassificationRule, Document, DocumentTag, FilingRule, TagOverride


# Common English/Italian filler words are not evidence that two documents match.
STOPWORDS = frozenset(
    "about after also been before from have here into more only other over page please some than that their them then there these they this were what when which will with your "
    "alla alle anche come con dalla dalle degli della delle dello nella nelle negli pagina per perché quando questa questo sono sulla sulle tutti tutto".split()
)


def _terms(value):
    return {term for term in re.findall(r"[^\W_]{4,}", value.casefold()) if not term.isdecimal() and term not in STOPWORDS}


def filing_suggestions(document):
    """Suggest labels from this owner's manual examples; never mutate a document.

    This intentionally ranks a bounded recent sample. The score is similarity,
    not a calibrated probability, so the UI always requires human acceptance.
    """
    if document.status != Document.Status.READY or document.trashed_at:
        return {"tags": [], "correspondents": [], "document_types": []}
    text_start = document.text_start if hasattr(document, "text_start") else document.extracted_text[:1800]
    target = _terms(document.title + " " + text_start)
    if len(target) < 2:
        return {"tags": [], "correspondents": [], "document_types": []}
    rows = list(
        Document.objects.filter(owner_id=document.owner_id, status=Document.Status.READY, trashed_at__isnull=True, is_split_source=False)
        .exclude(pk=document.pk)
        .filter(
            Exists(DocumentTag.objects.filter(document=OuterRef("pk"), origin=DocumentTag.Origin.MANUAL))
            | Q(correspondent_origin=Document.FilingOrigin.MANUAL, correspondent__isnull=False)
            | Q(document_type_origin=Document.FilingOrigin.MANUAL, document_type__isnull=False)
        )
        .order_by("-created_at", "-id")[:300]
        .annotate(text_start=Substr("extracted_text", 1, 1800))
        .values("id", "title", "text_start", "correspondent_id", "correspondent__name", "correspondent_origin", "document_type_id", "document_type__name", "document_type_origin")
    )
    ids = [row["id"] for row in rows]
    tags_by_document = {}
    if ids:
        for doc_id, tag_id, name in DocumentTag.objects.filter(document_id__in=ids, origin=DocumentTag.Origin.MANUAL, tag__owner_id=document.owner_id).values_list("document_id", "tag_id", "tag__name"):
            tags_by_document.setdefault(doc_id, []).append((tag_id, name))
    suppressed = set(TagOverride.objects.filter(document=document).values_list("tag_id", flat=True))
    existing = set(DocumentTag.objects.filter(document=document).values_list("tag_id", flat=True))
    sources = [_terms(row["title"] + " " + row["text_start"]) for row in rows]
    # Words in many examples (letterhead, scanner boilerplate) do not tell documents apart.
    frequency = Counter(term for terms in sources for term in terms)
    common = {term for term, count in frequency.items() if count > max(4, len(rows) // 4)}
    target -= common
    candidates = {"tags": {}, "correspondents": {}, "document_types": {}}
    for row, source in zip(rows, sources):
        source -= common
        shared = target & source
        if len(shared) < 3:
            continue
        similarity = len(shared) / max(len(target), len(source))
        if similarity < 0.3:
            continue
        example = {"id": str(row["id"]), "title": row["title"]}
        evidence = sorted(shared, key=lambda term: (-len(term), term))[:4]

        def add(kind, item_id, name):
            item = {"id": str(item_id), "name": name, "example": example, "shared_terms": evidence, "similarity": round(similarity, 2)}
            old = candidates[kind].get(str(item_id))
            if old is None or item["similarity"] > old["similarity"]:
                candidates[kind][str(item_id)] = item

        for tag_id, name in tags_by_document.get(row["id"], []):
            if tag_id not in existing and tag_id not in suppressed:
                add("tags", tag_id, name)
        if document.correspondent_origin == Document.FilingOrigin.NONE and row["correspondent_origin"] == Document.FilingOrigin.MANUAL and row["correspondent_id"]:
            add("correspondents", row["correspondent_id"], row["correspondent__name"])
        if document.document_type_origin == Document.FilingOrigin.NONE and row["document_type_origin"] == Document.FilingOrigin.MANUAL and row["document_type_id"]:
            add("document_types", row["document_type_id"], row["document_type__name"])
    limits = {"tags": 3, "correspondents": 2, "document_types": 2}
    result = {}
    for kind, values in candidates.items():
        ranked = sorted(values.values(), key=lambda item: (-item["similarity"], item["name"], item["id"]))
        cutoff = ranked[0]["similarity"] * 0.8 if ranked else 1
        result[kind] = [item for item in ranked if item["similarity"] >= cutoff][:limits[kind]]
    return result


def _matches(rule, title, text):
    needle = rule.pattern.casefold()
    if rule.field == "title":
        return needle in title
    if rule.field == "text":
        return needle in text
    return needle in title or needle in text


def apply_rules(document):
    with transaction.atomic():
        # Rule mutations take the same owner lock, so a queued classifier cannot
        # commit a rule snapshot after that rule has been deleted.
        get_user_model().objects.select_for_update(no_key=True).get(pk=document.owner_id)
        locked = Document.objects.select_for_update().get(pk=document.pk)
        if locked.trashed_at:
            return 0
        title = locked.title.casefold()
        text = locked.extracted_text.casefold()
        matching = [rule.tag for rule in ClassificationRule.objects.filter(owner_id=document.owner_id, enabled=True).select_related("tag") if _matches(rule, title, text)]
        filing_matches = {}
        for rule in FilingRule.objects.filter(owner_id=document.owner_id, enabled=True):
            if not _matches(rule, title, text):
                continue
            current = filing_matches.get(rule.kind)
            if current is None or (-len(rule.pattern), rule.created_at, str(rule.id)) < (-len(current.pattern), current.created_at, str(current.id)):
                filing_matches[rule.kind] = rule
        suppressed = set(TagOverride.objects.filter(document=locked).values_list("tag_id", flat=True))
        DocumentTag.objects.filter(document=locked, origin=DocumentTag.Origin.RULE).delete()
        for tag in matching:
            if tag.id in suppressed:
                continue
            DocumentTag.objects.get_or_create(document=locked, tag=tag, defaults={"origin": DocumentTag.Origin.RULE})
        changes = []
        for kind, field in ((FilingRule.Kind.CORRESPONDENT, "correspondent"), (FilingRule.Kind.DOCUMENT_TYPE, "document_type")):
            origin_field = f"{field}_origin"
            if getattr(locked, origin_field) in (Document.FilingOrigin.MANUAL, Document.FilingOrigin.SOURCE):
                continue
            rule = filing_matches.get(kind)
            target_id = getattr(rule, f"{field}_id") if rule else None
            origin = Document.FilingOrigin.RULE if rule else Document.FilingOrigin.NONE
            if getattr(locked, f"{field}_id") != target_id or getattr(locked, origin_field) != origin:
                setattr(locked, f"{field}_id", target_id)
                setattr(locked, origin_field, origin)
                changes.extend([field, origin_field])
        if changes:
            locked.save(update_fields=changes)
    return len(matching)
