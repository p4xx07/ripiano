"""Sign-in throttling per username and per client address (cache-backed)."""

import hashlib

from django.core.cache import cache

WINDOW_SECONDS = 15 * 60
LIMIT_PER_USERNAME = 10
LIMIT_PER_ADDRESS = 30


def sign_in_throttle_key(request, username):
    address = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")
    name = hashlib.sha256(str(username or "").strip().casefold().encode()).hexdigest()[:24]
    return f"signin:u:{name}", f"signin:a:{address}"


def sign_in_blocked(keys):
    by_user, by_address = keys
    return cache.get(by_user, 0) >= LIMIT_PER_USERNAME or cache.get(by_address, 0) >= LIMIT_PER_ADDRESS


def record_sign_in_failure(keys):
    for key in keys:
        cache.add(key, 0, WINDOW_SECONDS)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, WINDOW_SECONDS)
