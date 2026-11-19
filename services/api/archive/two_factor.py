"""Time-based one-time passwords (RFC 6238) for sign-in, with single-use recovery codes."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta
from urllib.parse import quote

from django.db import transaction
from django.utils import timezone

from .mail import MailError, decrypt_secret, encrypt_secret
from .models import AccountSecurity

STEP_SECONDS = 30
DIGITS = 6
MAX_FAILURES = 5
LOCK_MINUTES = 15


def _code(secret, step):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def provisioning_uri(secret, username, issuer="Ripiano"):
    return f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP_SECONDS}"


def matching_step(secret, code, now=None, last_step=0):
    """Return the time step a code belongs to (±1 step for clock drift), refusing reuse of old steps."""
    code = "".join(ch for ch in str(code) if ch.isdigit())
    if len(code) != DIGITS:
        return None
    current = int((now if now is not None else time.time()) // STEP_SECONDS)
    for step in (current - 1, current, current + 1):
        if step > last_step and hmac.compare_digest(_code(secret, step), code):
            return step
    return None


SESSION_FLAG = "ripiano_signed_in"


def admin_has_permission(request):
    """Admin access only for active staff whose session came through Ripiano's own sign-in."""
    user = request.user
    return bool(user.is_active and user.is_staff and request.session.get(SESSION_FLAG))


def _hash_recovery(code):
    return hashlib.sha256(code.replace("-", "").strip().lower().encode()).hexdigest()


def new_recovery_codes():
    codes = [f"{secrets.token_hex(5)}-{secrets.token_hex(5)}" for _ in range(10)]  # 80 bits each
    return codes, [_hash_recovery(code) for code in codes]


def is_enabled(user):
    security = AccountSecurity.objects.filter(user=user).first()
    return bool(security and security.enabled_at)


def verify(user, code):
    """Check a TOTP or recovery code for sign-in. Returns (ok, message). Locks TOTP entry after repeated failures.

    Recovery codes are checked first and work even while TOTP entry is locked or the secret cannot be read,
    so the owner always has a way back in.
    """
    with transaction.atomic():
        security = AccountSecurity.objects.select_for_update().filter(user=user).first()
        if not security or not security.enabled_at:
            return True, ""
        now = timezone.now()
        hashed = _hash_recovery(str(code))
        if hashed in security.recovery_hashes:
            security.recovery_hashes = [item for item in security.recovery_hashes if item != hashed]
            security.failed_attempts, security.locked_until = 0, None
            security.save(update_fields=["recovery_hashes", "failed_attempts", "locked_until"])
            return True, ""
        if security.locked_until and security.locked_until > now:
            return False, "Too many wrong codes. Try again in a few minutes, or use a recovery code."
        try:
            secret = decrypt_secret(security.totp_secret)
        except MailError:
            return False, "Your authenticator setup cannot be read on this server. Use a recovery code."
        step = matching_step(secret, code, last_step=security.last_step)
        if step is not None:
            security.last_step, security.failed_attempts, security.locked_until = step, 0, None
            security.save(update_fields=["last_step", "failed_attempts", "locked_until"])
            return True, ""
        security.failed_attempts += 1
        if security.failed_attempts >= MAX_FAILURES:
            security.failed_attempts, security.locked_until = 0, now + timedelta(minutes=LOCK_MINUTES)
        security.save(update_fields=["failed_attempts", "locked_until"])
        return False, "That code is not valid."


def begin_setup(user):
    security, _ = AccountSecurity.objects.get_or_create(user=user)
    secret = new_secret()
    security.pending_secret = encrypt_secret(secret)
    security.save(update_fields=["pending_secret"])
    return secret


def finish_setup(user, code):
    """Enable 2FA if the code matches the pending secret. Returns recovery codes, or None."""
    with transaction.atomic():
        security = AccountSecurity.objects.select_for_update().filter(user=user).first()
        if not security or not security.pending_secret:
            return None
        secret = decrypt_secret(security.pending_secret)
        step = matching_step(secret, code)
        if step is None:
            return None
        codes, hashes = new_recovery_codes()
        security.totp_secret, security.pending_secret = encrypt_secret(secret), ""
        security.enabled_at, security.last_step, security.recovery_hashes = timezone.now(), step, hashes
        security.failed_attempts, security.locked_until = 0, None
        security.save()
        return codes


def disable(user):
    AccountSecurity.objects.filter(user=user).update(totp_secret="", pending_secret="", enabled_at=None, recovery_hashes=[], last_step=0)


def remaining_recovery_codes(user):
    security = AccountSecurity.objects.filter(user=user).first()
    return len(security.recovery_hashes) if security else 0
