"""Local, explainable rules that never delay document availability."""

from django.db import transaction

from .models import ClassificationRule, Document, DocumentTag, TagOverride


def apply_rules(document):
    title = document.title.casefold()
    text = document.extracted_text.casefold()
    rules = ClassificationRule.objects.filter(owner=document.owner, enabled=True).select_related("tag")
    matching = []
    for rule in rules:
        needle = rule.pattern.casefold()
        if rule.field == ClassificationRule.Field.TITLE:
            matched = needle in title
        elif rule.field == ClassificationRule.Field.TEXT:
            matched = needle in text
        else:
            matched = needle in title or needle in text
        if matched:
            matching.append(rule.tag)
    suppressed = set(TagOverride.objects.filter(document=document).values_list("tag_id", flat=True))
    with transaction.atomic():
        DocumentTag.objects.filter(document=document, origin=DocumentTag.Origin.RULE).delete()
        for tag in matching:
            if tag.id in suppressed:
                continue
            DocumentTag.objects.get_or_create(document=document, tag=tag, defaults={"origin": DocumentTag.Origin.RULE})
    return len(matching)
