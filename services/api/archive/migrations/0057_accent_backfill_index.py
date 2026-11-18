"""Build the old-vector backfill index without blocking writes; retry safely if interrupted."""

from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    # A cancelled concurrent build can leave an invalid index behind. Remove it before retrying.
    schema_editor.execute("DROP INDEX CONCURRENTLY IF EXISTS archive_document_search_tsv_old")
    schema_editor.execute("""
        CREATE INDEX CONCURRENTLY archive_document_search_tsv_old ON archive_document (id)
        WHERE search_tsv_version < 2 OR search_tsv IS NULL
    """)


def reverse(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP INDEX CONCURRENTLY IF EXISTS archive_document_search_tsv_old")


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("archive", "0056_accent_folded_search")]
    operations = [migrations.RunPython(forward, reverse, elidable=False)]
