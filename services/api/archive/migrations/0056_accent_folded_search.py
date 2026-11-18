"""Fold common accents in PostgreSQL search without a table-wide reindex during migration."""

from django.db import migrations

# Old rows retain their vector until the maintenance backfill reaches them. Their version is 0,
# so StoredSearchVector computes the new form on demand in the meantime. New/edited rows use version 2.
FORWARD_SQL = """
ALTER TABLE archive_document ADD COLUMN search_tsv_version smallint NOT NULL DEFAULT 0;

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
            RETURN setweight(to_tsvector('simple', head) || to_tsvector('italian', head) || to_tsvector('english', head) || to_tsvector('simple', translate(head, 'àáâäèéêëìíîïòóôöùúûüÀÁÂÄÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜ', 'aaaaeeeeiiiioooouuuuAAAAEEEEIIIIOOOOUUUU')), 'A')
                || setweight(to_tsvector('simple', part) || to_tsvector('italian', part) || to_tsvector('english', part) || to_tsvector('simple', translate(part, 'àáâäèéêëìíîïòóôöùúûüÀÁÂÄÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜ', 'aaaaeeeeiiiioooouuuuAAAAEEEEIIIIOOOOUUUU')), 'B')
                || setweight(to_tsvector('simple', note) || to_tsvector('italian', note) || to_tsvector('english', note) || to_tsvector('simple', translate(note, 'àáâäèéêëìíîïòóôöùúûüÀÁÂÄÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜ', 'aaaaeeeeiiiioooouuuuAAAAEEEEIIIIOOOOUUUU')), 'C');
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
       AND NEW.action_note IS NOT DISTINCT FROM OLD.action_note
       AND NEW.search_tsv IS NOT NULL
       AND NEW.search_tsv_version = 2 THEN
        RETURN NEW;
    END IF;
    NEW.search_tsv := ripiano_document_search_tsv(NEW.title, NEW.extracted_text, NEW.action_note);
    NEW.search_tsv_version := 2;
    RETURN NEW;
END;
$$;

"""

REVERSE_SQL = """
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

ALTER TABLE archive_document DROP COLUMN IF EXISTS search_tsv_version;
"""


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD_SQL)


def reverse(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [("archive", "0055_document_search_tsv")]
    operations = [migrations.RunPython(forward, reverse, elidable=False)]
