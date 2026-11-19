from django.core.management.base import BaseCommand, CommandError

from archive.backup import BackupError, restore_snapshot


class Command(BaseCommand):
    help = "Restore a verified snapshot into an empty Ripiano stack"

    def add_arguments(self, parser):
        parser.add_argument("snapshot_name")
        parser.add_argument("--yes", action="store_true", help="Confirm the target stack is empty")

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("Pass --yes after checking that this is an empty target stack")
        try:
            restore_snapshot(options["snapshot_name"])
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Snapshot restored. Restart the application services."))
