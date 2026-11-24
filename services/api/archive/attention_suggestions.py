"""Conservative, local date suggestions for payment notices and event tickets.

Only an explicit date beside a due/event label is offered. This never creates a task,
sends text to a model, or treats a generic date in a document header as a deadline.
"""

import re
from datetime import date, timedelta

from django.utils import timezone

from . import date_detection

SCAN_CHARS = 30_000
HORIZON_DAYS = 730
PAYMENT_DOCUMENT = re.compile(r"\b(?:pagopa|mav|bollettin[oi]|avviso di pagamento|payment notice|fattura|invoice|tari|imu|bollo|multa|tributo)\b", re.I)
PAID_RECEIPT = re.compile(r"\b(?:ricevuta di pagamento|pagamento effettuato|pagato|pagata|paid on|payment received|payment completed)\b", re.I)
PAYMENT_DATE = re.compile(r"\b(?:scadenza|scade il|pagare entro|da pagare entro|versare entro|payment due|due date|pay by)\b\s*[:\-]?\s*", re.I)
EVENT_DOCUMENT = re.compile(r"\b(?:concerto|concert|festival|biglietto|ticket|evento|event)\b", re.I)
EVENT_DATE = re.compile(r"\b(?:data evento|data del concerto|concerto il|evento il|event date|concert on|show date)\b\s*[:\-]?\s*", re.I)


def _dates_after_labels(text, label_pattern, today):
    latest = today + timedelta(days=HORIZON_DAYS)
    found = set()
    for label in label_pattern.finditer(text):
        # A date must follow its label immediately or in the next short OCR line.
        window = text[label.end():label.end() + 90]
        candidates = []
        for kind, pattern in date_detection.PATTERNS:
            if kind == "numeric2":  # Future two-digit years are too easy to misread.
                continue
            for match in pattern.finditer(window):
                # Do not borrow a date from a later field when the labelled field is blank.
                if not re.fullmatch(r"\s*(?:(?:della\s+)?rata(?:\s+\d+)?\s+)?(?:il\s+)?", window[:match.start()], re.I):
                    continue
                value = date_detection._candidate(kind, match, date_detection._order(), today, latest)
                if value is not None and today <= value <= latest:
                    candidates.append((match.start(), value))
                    break
        if candidates:
            found.add(min(candidates, key=lambda item: item[0])[1])
    return found


def suggest_attention(title, text, *, today=None):
    """Return {kind, date} only for one explicit future date; otherwise None."""
    today = today or timezone.localdate()
    window = f"{title}\n{(text or '')[:SCAN_CHARS]}"
    if PAYMENT_DOCUMENT.search(window) and not PAID_RECEIPT.search(window):
        dates = _dates_after_labels(window, PAYMENT_DATE, today)
        if len(dates) == 1:
            return {"kind": "payment", "date": dates.pop().isoformat()}
    if EVENT_DOCUMENT.search(window):
        dates = _dates_after_labels(window, EVENT_DATE, today)
        if len(dates) == 1:
            return {"kind": "event", "date": dates.pop().isoformat()}
    return None
