"""Find a document's date in its text, and file email date and sender, during processing.

Like Paperless-ngx, the first plausible date near the start of the text wins: letters and invoices
print their date in the header. Numeric dates are read day-first by default (Italian/European);
``RIPIANO_DATE_ORDER`` (DMY, MDY, YMD) changes that. Dates after tomorrow or before 1900 are ignored.
Written dates in Italian and English are recognised ("10 novembre 2026", "1° marzo 2026",
"10 Nov 2026", "November 10, 2026").

Emails (.eml, .msg, and mail-rule imports) use the message Date header instead. An email's sender is
filed only when it matches an existing correspondent exactly; correspondents are never created.

Nothing here overwrites a date someone set or cleared by hand (``document_date_origin == manual``).
"""

import email
import logging
import re
from datetime import date, timedelta
from email import policy
from email.utils import getaddresses, parsedate_to_datetime

from django.conf import settings
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

logger = logging.getLogger(__name__)

# Dates are searched near the start; the bound keeps detection fast on very long documents.
SCAN_CHARS = 20_000
EARLIEST_YEAR = 1900

MONTHS = {
    # Italian
    "gennaio": 1, "gen": 1, "febbraio": 2, "feb": 2, "marzo": 3, "mar": 3, "aprile": 4, "apr": 4,
    "maggio": 5, "mag": 5, "giugno": 6, "giu": 6, "luglio": 7, "lug": 7, "agosto": 8, "ago": 8,
    "settembre": 9, "set": 9, "sett": 9, "ottobre": 10, "ott": 10, "novembre": 11, "nov": 11,
    "dicembre": 12, "dic": 12,
    # English
    "january": 1, "jan": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "jun": 6,
    "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "december": 12, "dec": 12,
}
_MONTH = "(?P<month>" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")(?![^\W\d_])\.?"
_NOT_DIGIT_BEFORE = r"(?<![\d])"
_NOT_DIGIT_AFTER = r"(?![\d])"

PATTERNS = (
    # 2026-11-10, 2026/11/10, 2026.11.10
    ("ymd", re.compile(_NOT_DIGIT_BEFORE + r"(?P<year>\d{4})(?P<sep>[-./])(?P<a>\d{1,2})(?P=sep)(?P<b>\d{1,2})" + _NOT_DIGIT_AFTER)),
    # 10/11/2026, 10.11.2026, 10-11-2026
    ("numeric", re.compile(_NOT_DIGIT_BEFORE + r"(?P<a>\d{1,2})(?P<sep>[-./])(?P<b>\d{1,2})(?P=sep)(?P<year>\d{4})" + _NOT_DIGIT_AFTER)),
    # 10/11/26: two-digit years only with two-digit day and month and a / or . separator (not phone-like -).
    ("numeric2", re.compile(r"(?<![\d.,/-])(?P<a>\d{2})(?P<sep>[./])(?P<b>\d{2})(?P=sep)(?P<year>\d{2})(?![\d.,/-]?\d)")),
    # 10 novembre 2026, 1° marzo 2026, 10 Nov. 2026, 3rd of March, 2026
    ("day_month", re.compile(
        _NOT_DIGIT_BEFORE + r"(?P<day>\d{1,2})\s*(?:°|º|st|nd|rd|th)?\.?\s*(?:of\s+|de\s+)?" + _MONTH + r",?\s+(?P<year>\d{4})" + _NOT_DIGIT_AFTER,
        re.IGNORECASE)),
    # November 10, 2026; Nov 10th 2026
    ("month_day", re.compile(
        r"(?<![^\W\d_])" + _MONTH + r"\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<year>\d{4})" + _NOT_DIGIT_AFTER,
        re.IGNORECASE)),
)


def _order():
    order = str(getattr(settings, "RIPIANO_DATE_ORDER", "DMY")).upper()
    return order if order in {"DMY", "MDY", "YMD"} else "DMY"


def _make(year, month, day, latest):
    try:
        value = date(year, month, day)
    except ValueError:
        return None
    return value if EARLIEST_YEAR <= value.year and value <= latest else None


def _two_digit_year(value, today):
    # Conservative: a two-digit year is read as 2000-today only; older years must be written in full.
    year = 2000 + value
    return year if year <= today.year else None


def _candidate(kind, match, order, today, latest):
    groups = match.groupdict()
    if kind in {"day_month", "month_day"}:
        return _make(int(groups["year"]), MONTHS[groups["month"].lower().rstrip(".")], int(groups["day"]), latest)
    if kind == "ymd":
        return _make(int(groups["year"]), int(groups["a"]), int(groups["b"]), latest)
    first, second = int(groups["a"]), int(groups["b"])
    if kind == "numeric2":
        if order == "YMD":
            # 26/11/10 read year first.
            year = _two_digit_year(first, today)
            return _make(year, second, int(groups["year"]), latest) if year else None
        year = _two_digit_year(int(groups["year"]), today)
        if year is None:
            return None
    else:
        year = int(groups["year"])
    # The configured order decides an ambiguous date; an impossible reading falls back to the other one.
    day, month = (second, first) if order == "MDY" else (first, second)
    return _make(year, month, day, latest) or _make(year, day, month, latest)


def detect_date(text, today=None):
    """The first plausible date in ``text``, or None."""
    if not text:
        return None
    today = today or timezone.localdate()
    latest = today + timedelta(days=1)
    order = _order()
    window = text[:SCAN_CHARS]
    found = []
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(window):
            value = _candidate(kind, match, order, today, latest)
            if value is not None:
                found.append((match.start(), value))
                break  # Later matches of the same pattern cannot be earlier than this one.
    return min(found, key=lambda item: item[0])[1] if found else None


# --- Email date and sender -------------------------------------------------------------------


def _parse_email_date(value, today=None):
    try:
        moment = parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError, IndexError):
        return None
    if moment is None:
        return None
    today = today or timezone.localdate()
    # The date the sender wrote, in the sender's own time zone.
    day = moment.date()
    return day if EARLIEST_YEAR <= day.year and day <= today + timedelta(days=1) else None


def email_details(path, mime):
    """(date or None, From header) of an .eml or .msg file."""
    from .email_render import EML_TYPE, HEADER_SCAN_BYTES, MSG_TYPE, _header, msg_to_message

    if mime == MSG_TYPE[1]:
        message = msg_to_message(path)
    elif mime == EML_TYPE[1]:
        with open(path, "rb") as source:
            message = email.message_from_bytes(source.read(HEADER_SCAN_BYTES), policy=policy.default)
    else:
        return None, ""
    return _parse_email_date(_header(message, "Date")), _header(message, "From")


def matching_correspondent(owner_id, sender):
    """An existing correspondent whose name is exactly the sender's display name, address, or domain."""
    from .models import Correspondent

    try:
        name, address = getaddresses([sender or ""])[0]
    except Exception:  # noqa: BLE001 - an unreadable sender files nothing
        return None
    address = address.strip().casefold()
    domain = address.rsplit("@", 1)[1] if "@" in address else ""
    candidates = [value for value in (name.strip().casefold(), address if "@" in address else "", domain) if value]
    if not candidates:
        return None
    found = {row["lower"]: row["id"] for row in Correspondent.objects.filter(owner_id=owner_id)
             .annotate(lower=Lower("name")).filter(lower__in=candidates).values("id", "lower")}
    return next((found[value] for value in candidates if value in found), None)


def _email_origin(document):
    from .models import DocumentEmail

    return DocumentEmail.objects.filter(document_id=document.pk).values("sender", "received_at").first()


def apply_document_details(document, *, first_run):
    """Fill an empty, never hand-edited document date; on the first run, file a known email sender."""
    from pathlib import Path

    from . import history
    from .email_render import EML_TYPE, MSG_TYPE
    from .models import Document

    header_date, sender = None, ""
    if document.original_mime in (EML_TYPE[1], MSG_TYPE[1]):
        try:
            header_date, sender = email_details(Path(settings.MEDIA_ROOT) / document.original_path, document.original_mime)
        except Exception:  # noqa: BLE001 - a malformed message just files nothing
            logger.warning("Could not read email headers of document %s", document.pk, exc_info=True)
    origin = _email_origin(document)
    if origin and not sender:
        sender = origin["sender"]

    with transaction.atomic():
        locked = Document.objects.select_for_update().get(pk=document.pk)
        if locked.trashed_at:
            return
        before = history.snapshot(locked)
        updates = []
        if locked.document_date is None and locked.document_date_origin != Document.DateOrigin.MANUAL:
            value, date_origin = header_date, Document.DateOrigin.SOURCE
            if value is None and settings.RIPIANO_DATE_DETECTION:
                value, date_origin = detect_date(locked.extracted_text), Document.DateOrigin.DETECTED
            if value is None and origin and origin["received_at"]:
                # An attachment with no readable date takes the date of the email that brought it.
                value, date_origin = timezone.localtime(origin["received_at"]).date(), Document.DateOrigin.SOURCE
            if value is not None:
                locked.document_date, locked.document_date_origin = value, date_origin
                updates += ["document_date", "document_date_origin"]
        if first_run and sender and locked.correspondent_id is None and locked.correspondent_origin == Document.FilingOrigin.NONE:
            correspondent_id = matching_correspondent(locked.owner_id, sender)
            if correspondent_id:
                locked.correspondent_id, locked.correspondent_origin = correspondent_id, Document.FilingOrigin.SOURCE
                updates += ["correspondent", "correspondent_origin"]
        if updates:
            locked.save(update_fields=updates)
            history.record(locked, before, action=history.Action.FILED_AUTOMATICALLY, actor_kind=history.Kind.DETECTION)
    for field in ("document_date", "document_date_origin", "correspondent_id", "correspondent_origin"):
        setattr(document, field, getattr(locked, field))
