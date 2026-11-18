"""Library search syntax: field terms, exclusion, OR, and date ranges.

    lease sender:"City office"           words plus a field term (all must match)
    -tag:Draft  -receipt                 exclude a field term or a word
    tag:Bills OR tag:Car                 either side may match (bare words too: invoice OR receipt)
    date:2026  date:2026-03              a whole year or month (document date)
    date:2026-01-01..2026-03-31          an inclusive range; either end may be left open (2026-01..)
    date:>=2026-01-01  added:<2026-11    open-ended comparisons; added: is the day Ripiano received it
    created:2026                         same as date: (the Paperless name)

`parse` returns (free words for ranking, clauses). A clause is (field, value), ("-" + field, value) for an
exclusion, or ("or", [clauses]). `clause_filter` turns one clause into a Q for the document queryset.
"""

import calendar
import re
import shlex
from datetime import date

from django.db.models import Exists, OuterRef, Q

FIELDS = {"title", "text", "note", "tag", "sender", "type", "sticker", "date", "added", "field", "asn", "is"}
ALIASES = {"created": "date", "correspondent": "sender", "document_type": "type"}
# Collected by archive/message_catalog.py (names ending in _ERRORS) so they get an Italian version.
SEARCH_ERRORS = {
    "date": "Use a date after date: or added:, like 2026-03-01, 2026-03, 2026, a range 2026-01-01..2026-03-31, or >=2026-01-01",
}
DATE_HELP = SEARCH_ERRORS["date"]


def _bound(text, end):
    """First (or last, when `end`) day of a YYYY, YYYY-MM, or YYYY-MM-DD value."""
    match = re.fullmatch(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", text)
    if not match or (match.group(3) and not match.group(2)):
        raise ValueError(DATE_HELP)
    year, month, day = int(match.group(1)), match.group(2), match.group(3)
    try:
        if day:
            return date(year, int(month), int(day))
        if month:
            return date(year, int(month), calendar.monthrange(year, int(month))[1] if end else 1)
        return date(year, 12, 31) if end else date(year, 1, 1)
    except ValueError as exc:
        raise ValueError(DATE_HELP) from exc


def date_range(value):
    try:
        return _date_range(value)
    except OverflowError as exc:
        raise ValueError(DATE_HELP) from exc
    except ValueError as exc:  # e.g. date:>9999 or date:<0001 run past the calendar: keep only our own messages
        if str(exc) in (DATE_HELP, "The start of a date range must be before its end"):
            raise
        raise ValueError(DATE_HELP) from exc


def _date_range(value):
    """(first, last) inclusive ISO dates for a date term; None stands for an open end."""
    for operator in (">=", "<=", ">", "<"):
        if value.startswith(operator):
            rest = value[len(operator):]
            if operator == ">=":
                return _bound(rest, False).isoformat(), None
            if operator == "<=":
                return None, _bound(rest, True).isoformat()
            if operator == ">":
                return date.fromordinal(_bound(rest, True).toordinal() + 1).isoformat(), None
            return None, date.fromordinal(_bound(rest, False).toordinal() - 1).isoformat()
    if ".." in value:
        start, _, stop = value.partition("..")
        if not start and not stop:
            raise ValueError(DATE_HELP)
        first = _bound(start, False) if start else None
        last = _bound(stop, True) if stop else None
        if first and last and first > last:
            raise ValueError("The start of a date range must be before its end")
        return (first.isoformat() if first else None), (last.isoformat() if last else None)
    return _bound(value, False).isoformat(), _bound(value, True).isoformat()


def _term(token):
    """A field clause for `field:value`, or None for an ordinary word."""
    field, separator, value = token.partition(":")
    field = ALIASES.get(field, field)
    if not (separator and field in FIELDS and value):
        return None
    if field in ("date", "added"):
        return field, date_range(value)
    if field == "asn":
        if not re.fullmatch(r"\d{1,9}", value):
            raise ValueError("Use a number after asn:")
        return field, str(int(value))
    if field == "field" and ("=" not in value or not all(part.strip() for part in value.split("=", 1))):
        raise ValueError('Use field:"Name=value" to search a custom field')
    if field == "is" and value not in {"tagged", "untagged"}:
        raise ValueError("Use is:tagged or is:untagged")
    return field, value


def parse(query):
    try:
        tokens = shlex.split(query)
    except ValueError:
        return query, []
    items = []  # ("word", text) | clause | "OR"
    for token in tokens:
        if token == "OR":
            items.append("OR")
            continue
        negate = token.startswith("-") and len(token) > 1
        body = token[1:] if negate else token
        clause = _term(body)
        if clause is None:
            items.append(("-any", body) if negate else ("word", body))
        else:
            items.append(("-" + clause[0], clause[1]) if negate else clause)
    words, clauses, index = [], [], 0
    while index < len(items):
        item = items[index]
        index += 1
        if item == "OR":
            continue  # a stray OR at the start or end is ignored
        group = [item]
        while index + 1 < len(items) and items[index] == "OR" and items[index + 1] != "OR":
            group.append(items[index + 1])
            index += 2
        if len(group) > 1:
            clauses.append(("or", [("any", part[1]) if part[0] == "word" else part for part in group]))
        elif item[0] == "word":
            words.append(item[1])
        else:
            clauses.append(item)
    return " ".join(words), clauses


def clause_filter(field, value, user):
    """A Q for one clause. Raises ValueError for an invalid custom-field value."""
    from .custom_field_views import normalize_filter_value
    from .models import CustomField, CustomFieldValue, DocumentNote, DocumentTag, PhysicalCopy, Tag

    if field == "or":
        combined = Q(pk__in=[])
        for part_field, part_value in value:
            combined |= clause_filter(part_field, part_value, user)
        return combined
    if field.startswith("-"):
        return ~clause_filter(field[1:], value, user)
    if field == "any":
        return (Q(title__icontains=value) | Q(extracted_text__icontains=value) | Q(action_note__icontains=value)
                | Q(correspondent__name__icontains=value) | Q(document_type__name__icontains=value)
                | Q(Exists(Tag.objects.filter(document_links__document_id=OuterRef("pk"), name__icontains=value)))
                | Q(Exists(DocumentNote.objects.filter(document_id=OuterRef("pk"), body__icontains=value))))
    if field == "title":
        return Q(title__icontains=value)
    if field == "text":
        return Q(extracted_text__icontains=value)
    if field == "note":
        return Q(action_note__icontains=value) | Q(Exists(DocumentNote.objects.filter(document_id=OuterRef("pk"), body__icontains=value)))
    if field == "tag":
        return Q(Exists(Tag.objects.filter(document_links__document_id=OuterRef("pk"), name__icontains=value)))
    if field == "is":
        linked = Q(Exists(DocumentTag.objects.filter(document_id=OuterRef("pk"))))
        return linked if value == "tagged" else ~linked
    if field == "sender":
        return Q(correspondent__name__icontains=value)
    if field == "type":
        return Q(document_type__name__icontains=value)
    if field == "asn":
        return Q(asn=int(value))
    if field == "sticker":
        return Q(Exists(PhysicalCopy.objects.filter(document_id=OuterRef("pk"), sticker_code__icontains=value)))
    if field in ("date", "added"):
        first, last = value
        column = "document_date" if field == "date" else "created_at__date"
        result = Q()
        if first:
            result &= Q(**{f"{column}__gte": first})
        if last:
            result &= Q(**{f"{column}__lte": last})
        return result
    if field == "field":
        name, raw_value = (part.strip() for part in value.split("=", 1))
        definition = CustomField.objects.filter(owner=user, name__iexact=name).first()
        if definition is None:
            return Q(pk__in=[])
        if definition.kind == CustomField.Kind.TEXT:
            return Q(Exists(CustomFieldValue.objects.filter(document_id=OuterRef("pk"), field=definition, value__icontains=raw_value)))
        normalized = normalize_filter_value(definition, raw_value)
        return Q(Exists(CustomFieldValue.objects.filter(document_id=OuterRef("pk"), field=definition, value=normalized)))
    raise AssertionError(field)
