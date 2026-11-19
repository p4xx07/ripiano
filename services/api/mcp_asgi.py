import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ripiano.settings")
django.setup()

from archive.mcp_server import app  # noqa: E402
