""""Did you mean …?" for searches that found nothing, using the person's own archive vocabulary.

Words come from the titles of their documents and the names of their tags, senders, and document types, so a
suggestion always points at something that exists. Pure Python (difflib), bounded in size, and only run when a
search returned no documents, so normal searches pay nothing.
"""

import difflib
import re
import unicodedata

from .models import Correspondent, Document, DocumentType, Tag

WORD = re.compile(r"[^\W\d_]{4,}", re.UNICODE)
MAX_TITLES = 5000
MAX_WORDS = 20000


def _fold(text):
    return "".join(char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char))


def _vocabulary(user):
    names = [*Tag.objects.filter(owner=user).values_list("name", flat=True)[:2000],
             *Correspondent.objects.filter(owner=user).values_list("name", flat=True)[:2000],
             *DocumentType.objects.filter(owner=user).values_list("name", flat=True)[:2000],
             *Document.objects.filter(owner=user, trashed_at__isnull=True).order_by("-created_at").values_list("title", flat=True)[:MAX_TITLES]]
    words = {}
    for name in names:
        for word in WORD.findall(name or ""):
            words.setdefault(_fold(word), word.casefold())
            if len(words) >= MAX_WORDS:
                return words
    return words


def suggest(user, query):
    """A corrected query, or None. Only plain words are corrected; field terms and dates are kept as typed."""
    tokens = query.split()
    if not tokens or len(tokens) > 6:
        return None
    vocabulary = _vocabulary(user)
    if not vocabulary:
        return None
    folded = list(vocabulary)
    changed, result = False, []
    for token in tokens:
        if ":" in token or not WORD.fullmatch(token) or _fold(token) in vocabulary:
            result.append(token)
            continue
        match = difflib.get_close_matches(_fold(token), folded, n=1, cutoff=0.8)
        if match:
            result.append(vocabulary[match[0]])
            changed = True
        else:
            result.append(token)
    return " ".join(result) if changed else None
