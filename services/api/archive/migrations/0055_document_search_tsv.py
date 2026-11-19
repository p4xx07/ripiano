"""Store a language-aware full-text vector for each document (PostgreSQL only; see archive/fulltext.py)."""

from django.db import migrations

# Weights: title A, OCR/text B, action note C (as the on-the-fly vector used before).
# The text is tried whole, then cut shorter if PostgreSQL's 1 MB tsvector limit is reached,
# so an enormous OCR text can never make saving a document fail.
FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION ripiano_document_search_tsv(head text, body text, note text)
RETURNS tsvector LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE SET search_path = pg_catalog AS $$
DECLARE
    cap integer;
    part text;
BEGIN
    head := coalesce(head, '');
    body := coalesce(body, '');
    note := coalesce(note, '');
    FOREACH cap IN ARRAY ARRAY[0, 400000, 100000, 20000, 1] LOOP
        part := CASE WHEN cap = 0 THEN body ELSE left(body, cap - 1) END;
        BEGIN
            RETURN setweight(to_tsvector('simple', head) || to_tsvector('italian', head) || to_tsvector('english', head), 'A')
                || setweight(to_tsvector('simple', part) || to_tsvector('italian', part) || to_tsvector('english', part), 'B')
                || setweight(to_tsvector('simple', note) || to_tsvector('italian', note) || to_tsvector('english', note), 'C');
        EXCEPTION WHEN OTHERS THEN
            NULL;  -- too large: try a shorter text
        END;
    END LOOP;
    RETURN ''::tsvector;
END;
$$;

CREATE OR REPLACE FUNCTION ripiano_document_search_tsv_trigger() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.title IS NOT DISTINCT FROM OLD.title
       AND NEW.extracted_text IS NOT DISTINCT FROM OLD.extracted_text
       AND NEW.action_note IS NOT DISTINCT FROM OLD.action_note THEN
        -- Status/tag/date edits do not re-stem the text. A row that has no vector yet (it existed before this
        -- migration) gets one here, unless the background backfill is setting it in this very statement.
        IF NEW.search_tsv IS NULL THEN
            NEW.search_tsv := ripiano_document_search_tsv(NEW.title, NEW.extracted_text, NEW.action_note);
        END IF;
    ELSE
        NEW.search_tsv := ripiano_document_search_tsv(NEW.title, NEW.extracted_text, NEW.action_note);
    END IF;
    RETURN NEW;
END;
$$;
"""

# Documents that already exist are NOT indexed here: stemming a large archive inside the migration would hold a
# lock on the table and delay the API's start on a NAS. Their column stays NULL and the maintenance worker fills it
# in small batches (archive.tasks.index_search_text). Until then searches compute the vector for those rows on the
# fly (fulltext.StoredSearchVector), exactly as every search did before, so nothing drops out of the results.
# The partial index makes "is anything left to index?" instant; it is empty once the backfill is done.
FORWARD_SQL = FUNCTION_SQL + """
ALTER TABLE archive_document ADD COLUMN IF NOT EXISTS search_tsv tsvector;
DROP TRIGGER IF EXISTS archive_document_search_tsv ON archive_document;
CREATE TRIGGER archive_document_search_tsv BEFORE INSERT OR UPDATE ON archive_document
    FOR EACH ROW EXECUTE FUNCTION ripiano_document_search_tsv_trigger();
CREATE INDEX IF NOT EXISTS archive_document_search_tsv_missing ON archive_document (id) WHERE search_tsv IS NULL;
"""

REVERSE_SQL = """
DROP INDEX IF EXISTS archive_document_search_tsv_missing;
DROP TRIGGER IF EXISTS archive_document_search_tsv ON archive_document;
ALTER TABLE archive_document DROP COLUMN IF EXISTS search_tsv;
DROP FUNCTION IF EXISTS ripiano_document_search_tsv_trigger();
DROP FUNCTION IF EXISTS ripiano_document_search_tsv(text, text, text);
"""


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD_SQL)


def reverse(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0054_document_date_origin"),
    ]

    operations = [migrations.RunPython(forward, reverse, elidable=False)]
