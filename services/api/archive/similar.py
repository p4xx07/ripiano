"""Local "more like this": compare a document's distinctive words with the owner's other documents.

No model or external service is involved. Scores are word-overlap similarity, not probabilities.
"""

from collections import Counter

from django.db.models.functions import Substr

from .classification import _terms
from .models import Document

SAMPLE = 500
TEXT_CHARS = 3000
MIN_SCORE = 0.15
LIKELY_DUPLICATE = 0.85


def similar_documents(document, limit=6):
    if document.status != Document.Status.READY:
        return []
    source = Document.objects.filter(pk=document.pk).annotate(start=Substr("extracted_text", 1, TEXT_CHARS)).values_list("title", "start").first()
    if source is None:
        return []
    rows = list(
        Document.objects.filter(owner_id=document.owner_id, status=Document.Status.READY, trashed_at__isnull=True, is_split_source=False)
        .exclude(pk=document.pk).order_by("-created_at", "-id")[:SAMPLE]
        .annotate(start=Substr("extracted_text", 1, TEXT_CHARS))
        .values("id", "title", "start", "original_sha256", "created_at")
    )
    sets = [_terms(row["title"] + " " + row["start"]) for row in rows]
    # Words in many documents (letterheads, scanner boilerplate) say little about similarity.
    frequency = Counter(term for terms in sets for term in terms)
    common = {term for term, count in frequency.items() if count > max(5, len(rows) // 4)}
    target = _terms(source[0] + " " + source[1]) - common
    if len(target) < 3:
        return []
    scored = []
    for row, terms in zip(rows, sets):
        terms -= common
        shared = target & terms
        if len(shared) < 3:
            continue
        score = len(shared) / len(target | terms)
        if score < MIN_SCORE:
            continue
        scored.append({
            "id": str(row["id"]), "title": row["title"], "score": round(score, 2), "created_at": row["created_at"].isoformat(),
            "shared_terms": sorted(shared, key=lambda term: (-len(term), term))[:5],
            "exact_copy": row["original_sha256"] == document.original_sha256,
            "likely_duplicate": score >= LIKELY_DUPLICATE and row["original_sha256"] != document.original_sha256,
        })
    scored.sort(key=lambda item: (-item["score"], item["title"]))
    return scored[:limit]
