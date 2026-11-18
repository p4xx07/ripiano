"""Language-aware full-text matching for the Library search (PostgreSQL only).

Archives mix Italian and English, so each document keeps one stored `tsvector` (column
`archive_document.search_tsv`, filled by the trigger in migration 0055 and, for documents older than
that migration, by the background `backfill`) holding the words three ways:
as written ('simple'), Italian stems and English stems. A search word matches when any of the three
forms matches, so "rifiuto" finds "rifiuti" and "invoice" finds "invoices", while an exact word still
matches as before and ranks higher (it hits more than one form).

The column is not a model field, so ordinary document queries never load it; `StoredSearchVector`
reads it only inside search queries. SQLite (development/tests) keeps the `icontains` fallback.
"""

import re

from django.contrib.postgres.search import SearchQuery, SearchVectorField
from django.db.models import Expression

CONFIGS = ("simple", "italian", "english")
MAX_QUERY_WORDS = 32


class StoredSearchVector(Expression):
    """The `search_tsv` column of the queryset's document table (relabeled correctly inside subqueries)."""

    output_field = SearchVectorField()
    contains_aggregate = False

    def __init__(self, alias=None):
        super().__init__()
        self.alias = alias

    def resolve_expression(self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False):
        clone = self.copy()
        if clone.alias is None:
            clone.alias = query.get_initial_alias()
        return clone

    def relabeled_clone(self, change_map):
        clone = self.copy()
        clone.alias = change_map.get(self.alias, self.alias)
        return clone

    def as_sql(self, compiler, connection):
        table = compiler.quote_name_unless_alias(self.alias)
        # Rows that existed before migration 0055 have no stored vector until the background backfill reaches them
        # (see `backfill`); compute theirs on the fly so they never drop out of search.
        column = {name: f"{table}.{connection.ops.quote_name(name)}" for name in ("search_tsv", "title", "extracted_text", "action_note")}
        sql = "coalesce(%(search_tsv)s, ripiano_document_search_tsv(%(title)s, %(extracted_text)s, %(action_note)s))" % column
        return sql, []

    def get_group_by_cols(self):
        return [self]

    def __eq__(self, other):
        return isinstance(other, StoredSearchVector) and other.alias == self.alias

    def __hash__(self):
        return hash((StoredSearchVector, self.alias))


def search_query(text):
    """Every word must match, each in its written, Italian-stemmed, or English-stemmed form (or the
    whole query matches under Italian or English rules, which ignore stopwords)."""
    words = [word for word in re.split(r"\s+", text.strip()) if word][:MAX_QUERY_WORDS]
    combined = None
    for word in words:
        forms = None
        for config in CONFIGS:
            form = SearchQuery(word, search_type="plain", config=config)
            forms = form if forms is None else forms | form
        combined = forms if combined is None else combined & forms
    if combined is None:
        return SearchQuery(text, search_type="plain", config="simple")
    # Whole-query stemming too, so a stopword ("il", "the") need not appear in the document.
    return combined | SearchQuery(text, search_type="plain", config="italian") | SearchQuery(text, search_type="plain", config="english")


def backfill(limit=200):
    """Store the vector for up to `limit` documents that have none yet. Returns (indexed, more_remain).

    Small batches with short row locks, so a large archive is indexed in the background without blocking
    uploads or edits. Rows being edited right now are skipped and picked up by the next batch.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        return 0, False
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE archive_document SET search_tsv = ripiano_document_search_tsv(title, extracted_text, action_note)
            WHERE id IN (SELECT id FROM archive_document WHERE search_tsv IS NULL LIMIT %s FOR UPDATE SKIP LOCKED)
            """, [limit])
        indexed = cursor.rowcount
        cursor.execute("SELECT EXISTS (SELECT 1 FROM archive_document WHERE search_tsv IS NULL)")
        return indexed, bool(cursor.fetchone()[0])
