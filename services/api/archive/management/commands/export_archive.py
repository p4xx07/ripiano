from django.core.management.base import BaseCommand, CommandError

from archive.portable import PortableError, export_archive


class Command(BaseCommand):
    help = "Export every account, record, and stored file to a portable folder (manifest.json + media/)"

    def add_arguments(self, parser):
        parser.add_argument("destination", help="An empty or new folder, for example /backup/export-2026-11")

    def handle(self, *args, **options):
        try:
            counts, files = export_archive(options["destination"])
        except PortableError as exc:
            raise CommandError(str(exc)) from exc
        documents = counts.get("archive.Document", 0)
        self.stdout.write(self.style.SUCCESS(f"Exported {documents} documents and {files} files to {options['destination']}"))
