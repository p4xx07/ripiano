"""OAuth sign-in for Gmail and Outlook mailboxes (IMAP XOAUTH2).

The operator registers an OAuth client and sets its ID and secret in the
environment; the refresh token is encrypted like a password.
"""

import base64
import json
import secrets

import httpx
from django.conf import settings
from django.core import signing

from .mail import MailError, decrypt_secret, encrypt_secret

PROVIDERS = {
    "gmail": {
        "label": "Gmail",
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://mail.google.com/ openid email",
        "host": "imap.gmail.com",
        "extra": {"access_type": "offline", "prompt": "consent"},
    },
    "outlook": {
        "label": "Outlook",
        "authorize": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scope": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access openid email",
        "host": "outlook.office365.com",
        "extra": {"prompt": "select_account"},
    },
}
STATE_SALT = "ripiano.mail.oauth"
STATE_MAX_AGE = 15 * 60


def _client(provider):
    return settings.RIPIANO_MAIL_OAUTH.get(provider) or (None, None)


def enabled_providers():
    return [{"id": key, "label": value["label"]} for key, value in PROVIDERS.items() if all(_client(key))]


def redirect_uri():
    return f"{settings.PUBLIC_ORIGIN.rstrip('/')}/api/mail/oauth/callback"


def authorization_url(user, provider):
    client_id, _ = _client(provider)
    if provider not in PROVIDERS or not client_id:
        raise MailError("This provider is not configured on this server.", "not_configured")
    config = PROVIDERS[provider]
    state = signing.dumps({"user": user.pk, "provider": provider, "nonce": secrets.token_urlsafe(8)}, salt=STATE_SALT)
    query = httpx.QueryParams({
        "client_id": client_id, "redirect_uri": redirect_uri(), "response_type": "code",
        "scope": config["scope"], "state": state, **config["extra"],
    })
    return f"{config['authorize']}?{query}"


def read_state(value):
    try:
        state = signing.loads(value, salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.BadSignature as exc:
        raise MailError("The sign-in link expired. Start again.", "expired") from exc
    if state.get("provider") not in PROVIDERS:
        raise MailError("Unknown mail provider.", "provider")
    return state


def _token_request(provider, data):
    client_id, client_secret = _client(provider)
    if not client_id:
        raise MailError("This provider is no longer configured on this server.", "not_configured")
    try:
        response = httpx.post(PROVIDERS[provider]["token"], data={"client_id": client_id, "client_secret": client_secret, **data}, timeout=20)
    except httpx.HTTPError as exc:
        raise MailError("Could not reach the sign-in service.", "provider") from exc
    if response.status_code != 200:
        raise MailError("The provider refused the sign-in. Connect the mailbox again.", "provider")
    try:
        return response.json()
    except ValueError as exc:
        raise MailError("The sign-in service sent an unexpected reply.", "provider") from exc


def exchange_code(provider, code):
    """Return (email address, refresh token) for a completed consent."""
    payload = _token_request(provider, {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()})
    refresh = payload.get("refresh_token")
    if not refresh:
        raise MailError("The provider did not grant offline access. Try again and accept all permissions.", "offline")
    # The ID token comes straight from the token endpoint over TLS, so its claims can be read directly.
    try:
        segment = payload["id_token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
    except (KeyError, IndexError, ValueError) as exc:
        raise MailError("The provider did not return the mailbox address.", "address") from exc
    address = claims.get("email") or claims.get("preferred_username") or ""
    if "@" not in address:
        raise MailError("The provider did not return the mailbox address.", "address")
    return address, refresh


def access_token(account):
    payload = _token_request(account.oauth_provider, {"grant_type": "refresh_token", "refresh_token": decrypt_secret(account.secret, oauth=True)})
    token = payload.get("access_token")
    if not token:
        raise MailError("The provider refused the sign-in. Connect the mailbox again.", "provider")
    rotated = payload.get("refresh_token")
    if rotated:
        # Microsoft rotates refresh tokens; keep the newest one.
        account.secret = encrypt_secret(rotated)
        type(account).objects.filter(pk=account.pk).update(secret=account.secret)
    return token
