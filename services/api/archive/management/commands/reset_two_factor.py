from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from archive import two_factor


class Command(BaseCommand):
    help = "Turn off two-step sign-in for one account (for a lost phone without recovery codes)"

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError("No account with that username")
        two_factor.disable(user)
        self.stdout.write(self.style.SUCCESS(f"Two-step sign-in is off for {user.get_username()}. Ask them to turn it on again."))
