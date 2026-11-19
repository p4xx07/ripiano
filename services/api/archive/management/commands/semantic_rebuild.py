"""Rebuild every semantic-search passage (for example after changing the embedding model's settings).

    manage.py semantic_rebuild            mark all documents for re-indexing and start the background job
    manage.py semantic_rebuild --owner ada  only one person's documents

Existing passages keep answering searches until each document is re-indexed.
"""

from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from archive.models import SemanticDocument, SemanticSettings

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class Command(BaseCommand):
    help = "Re-index all documents for semantic search in the background."

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="Only this user's documents (username)")

    def handle(self, *args, owner=None, **options):
        if SemanticSettings.current().mode == SemanticSettings.Mode.OFF:
            raise CommandError("Semantic search is off. Turn it on in Agents → Semantic search first.")
        rows = SemanticDocument.objects.all()
        if owner:
            user = get_user_model().objects.filter(username=owner).first()
            if user is None:
                raise CommandError(f"No user named {owner}")
            rows = rows.filter(document__owner=user)
        marked = rows.update(indexed_at=EPOCH)
        from archive.tasks import semantic_index

        semantic_index.delay()
        self.stdout.write(f"Marked {marked} indexed documents for rebuilding; documents never indexed are queued too. The background job has started.")
