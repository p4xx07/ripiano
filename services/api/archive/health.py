"""Cheap dependency checks for the health endpoints (docs/BACKUP_RESTORE.md, "Health checks")."""

import logging

from django.conf import settings
import time

from django.db import Error as DatabaseFailure
from django.db import connection

logger = logging.getLogger(__name__)


def database_ok():
    """One `SELECT 1` on the default database; False (and logged) when it cannot answer."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except DatabaseFailure as exc:  # includes InterfaceError ("connection already closed")
        logger.warning("Health check: database unavailable: %s", exc)
        return False


def broker_ok():
    """One PING to the queue/cache server (Valkey) with a one-second timeout."""
    try:
        import redis

        client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=1, socket_timeout=1)
        try:
            return bool(client.ping())
        finally:
            client.close()
    except Exception as exc:  # noqa: BLE001 - any failure means "not reachable"
        logger.warning("Health check: broker unavailable: %s", exc)
        return False


# /healthz is reachable without signing in: the answer is reused for a few seconds, so repeated calls cost the
# database and the queue server nothing (round-9 review, L4).
CACHE_SECONDS = 5
_last = None


def checks():
    """{"database": "ok"|"down", "broker": "ok"|"down"}, at most CACHE_SECONDS old."""
    global _last
    if _last is None or time.monotonic() - _last[0] >= CACHE_SECONDS:
        _last = (time.monotonic(), {"database": "ok" if database_ok() else "down", "broker": "ok" if broker_ok() else "down"})
    return dict(_last[1])


def forget():
    global _last
    _last = None
