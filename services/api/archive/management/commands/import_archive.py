from django.core.management.base import BaseCommand, CommandError

from archive.portable import PortableError, import_archive


class Command(BaseCommand):
    help = "Import a folder made by export_archive into a new, empty Ripiano"

    def add_arguments(self, parser):
        parser.add_argument("source")
        parser.add_argument("--yes", action="store_true", help="Confirm this is a new, empty Ripiano")

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("Pass --yes after checking that this Ripiano is new and empty")
        try:
            counts, files = import_archive(options["source"])
        except PortableError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Imported {counts.get('archive.Document', 0)} documents and {files} files. Restart the application services."))
