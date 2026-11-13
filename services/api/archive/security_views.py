"""Two-factor sign-in settings for the signed-in person."""

import json

import segno
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from . import two_factor


def _signed_in(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _password_ok(request, password):
    """Check the person's password with the same throttle as sign-in."""
    from .throttle import record_sign_in_failure, sign_in_blocked, sign_in_throttle_key

    keys = sign_in_throttle_key(request, request.user.get_username())
    if sign_in_blocked(keys):
        return False, JsonResponse({"error": "Too many attempts. Wait a few minutes and try again."}, status=429)
    if not request.user.check_password(str(password or "")):
        record_sign_in_failure(keys)
        return False, JsonResponse({"error": "Your password is not correct"}, status=400)
    return True, None


def _sign_out_other_sessions(request):
    """End every other session of this person (their other devices must sign in again with a code)."""
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    current = request.session.session_key
    user_id = str(request.user.pk)
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if session.session_key != current and str(session.get_decoded().get("_auth_user_id")) == user_id:
            session.delete()


def _status(user):
    return {"two_factor": two_factor.is_enabled(user), "recovery_remaining": two_factor.remaining_recovery_codes(user)}


@require_http_methods(["GET"])
def security(request):
    denied = _signed_in(request)
    return denied or JsonResponse(_status(request.user))


@require_http_methods(["POST"])
def security_setup(request):
    denied = _signed_in(request)
    if denied:
        return denied
    body = _body(request) or {}
    ok, refused = _password_ok(request, body.get("password"))
    if not ok:
        return refused
    if two_factor.is_enabled(request.user):
        return JsonResponse({"error": "Two-step sign-in is already on"}, status=409)
    secret = two_factor.begin_setup(request.user)
    uri = two_factor.provisioning_uri(secret, request.user.get_username())
    return JsonResponse({"secret": secret, "uri": uri, "qr_svg": segno.make(uri, error="m").svg_inline(scale=4, dark="#1f2a24", light="#ffffff")})


@require_http_methods(["POST"])
def security_enable(request):
    denied = _signed_in(request)
    if denied:
        return denied
    codes = two_factor.finish_setup(request.user, str((_body(request) or {}).get("code", "")))
    if codes is None:
        return JsonResponse({"error": "That code is not valid. Check the time on your phone and try the newest code."}, status=400)
    _sign_out_other_sessions(request)
    return JsonResponse({**_status(request.user), "recovery_codes": codes})


def _confirm(request):
    body = _body(request) or {}
    ok, refused = _password_ok(request, body.get("password"))
    if not ok:
        return refused
    ok, message = two_factor.verify(request.user, str(body.get("code", "")))
    if not ok:
        return JsonResponse({"error": message}, status=400)
    return None


@require_http_methods(["POST"])
def security_disable(request):
    denied = _signed_in(request) or _confirm(request)
    if denied:
        return denied
    two_factor.disable(request.user)
    return JsonResponse(_status(request.user))


@require_http_methods(["POST"])
def security_recovery_codes(request):
    denied = _signed_in(request) or _confirm(request)
    if denied:
        return denied
    from .models import AccountSecurity

    codes, hashes = two_factor.new_recovery_codes()
    AccountSecurity.objects.filter(user=request.user).update(recovery_hashes=hashes)
    return JsonResponse({**_status(request.user), "recovery_codes": codes})


@require_http_methods(["POST"])
def change_password(request):
    """Replace your own password; other devices sign out, this one stays signed in."""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    denied = _signed_in(request)
    if denied:
        return denied
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    ok, refused = _password_ok(request, body.get("current_password"))
    if not ok:
        return refused
    new = body.get("new_password")
    if not isinstance(new, str) or len(new) < 12:
        return JsonResponse({"error": "Use a new password of at least 12 characters"}, status=400)
    try:
        validate_password(new, request.user)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    request.user.set_password(new)
    request.user.save(update_fields=["password"])
    update_session_auth_hash(request, request.user)
    return JsonResponse({"changed": True})
