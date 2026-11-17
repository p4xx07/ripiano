"""Poll an S3-compatible bucket prefix and import new objects (see archive/s3_input.py)."""

import os
import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from archive.s3_input import BucketImporter, S3Client, S3Error, settings_from_env

EXPIRY_INTERVAL_SECONDS = 3600


class Command(BaseCommand):
    help = "Import new files from an S3-compatible bucket prefix, move them to a processed prefix, and expire them later"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one import and one expiry pass, then exit")

    def handle(self, *args, **options):
        env = os.environ
        missing = [name for name in ("RIPIANO_S3_ENDPOINT", "RIPIANO_S3_BUCKET", "RIPIANO_S3_ACCESS_KEY", "RIPIANO_S3_SECRET_KEY",
                                     "RIPIANO_S3_OWNER_USERNAME") if not env.get(name)]
        if missing:
            raise CommandError(f"Set {', '.join(missing)}")
        owner = get_user_model().objects.filter(username=env["RIPIANO_S3_OWNER_USERNAME"]).first()
        if owner is None:
            raise CommandError("RIPIANO_S3_OWNER_USERNAME must name an existing account")
        try:
            config = settings_from_env(env)
            client = S3Client(endpoint=env["RIPIANO_S3_ENDPOINT"], bucket=env["RIPIANO_S3_BUCKET"],
                              access_key=env["RIPIANO_S3_ACCESS_KEY"], secret_key=env["RIPIANO_S3_SECRET_KEY"],
                              region=env.get("RIPIANO_S3_REGION", "us-east-1"), addressing=env.get("RIPIANO_S3_ADDRESSING", "path"))
            interval = max(10, int(env.get("RIPIANO_S3_POLL_SECONDS", "60")))
        except (S3Error, ValueError) as error:
            raise CommandError(str(error) if isinstance(error, S3Error) else "RIPIANO_S3_POLL_SECONDS must be a whole number") from error
        importer = BucketImporter(client, owner, config)
        last_expiry = 0.0
        while True:
            try:
                added = importer.import_new()
                if added:
                    self.stdout.write(f"Imported {added} document(s)")
                if time.monotonic() - last_expiry >= EXPIRY_INTERVAL_SECONDS or options["once"]:
                    importer.expire_processed()
                    last_expiry = time.monotonic()
            except S3Error as error:
                # Credentials and signatures never appear in these messages.
                self.stderr.write(f"S3 input: {error}")
                if options["once"]:
                    raise CommandError(str(error)) from error
            if options["once"]:
                return
            time.sleep(interval)
