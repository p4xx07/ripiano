"""Local, explainable rules that never delay document availability."""

from django.db import transaction

from .models import ClassificationRule, Document, DocumentTag, FilingRule, TagOverride


def _matches(rule, title, text):
    needle = rule.pattern.casefold()
    if rule.field == "title":
        return needle in title
    if rule.field == "text":
        return needle in text
    return needle in title or needle in text


def apply_rules(document):
    title = document.title.casefold()
    text = document.extracted_text.casefold()
    rules = ClassificationRule.objects.filter(owner=document.owner, enabled=True).select_related("tag")
    matching = []
    for rule in rules:
        if _matches(rule, title, text):
            matching.append(rule.tag)
    filing_matches = {}
    for rule in FilingRule.objects.filter(owner=document.owner, enabled=True):
        if not _matches(rule, title, text):
            continue
        current = filing_matches.get(rule.kind)
        if current is None or (-len(rule.pattern), rule.created_at, str(rule.id)) < (-len(current.pattern), current.created_at, str(current.id)):
            filing_matches[rule.kind] = rule
    suppressed = set(TagOverride.objects.filter(document=document).values_list("tag_id", flat=True))
    with transaction.atomic():
        DocumentTag.objects.filter(document=document, origin=DocumentTag.Origin.RULE).delete()
        for tag in matching:
            if tag.id in suppressed:
                continue
            DocumentTag.objects.get_or_create(document=document, tag=tag, defaults={"origin": DocumentTag.Origin.RULE})
        locked = Document.objects.select_for_update().get(pk=document.pk)
        changes = []
        for kind, field in ((FilingRule.Kind.CORRESPONDENT, "correspondent"), (FilingRule.Kind.DOCUMENT_TYPE, "document_type")):
            origin_field = f"{field}_origin"
            if getattr(locked, origin_field) == Document.FilingOrigin.MANUAL:
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
