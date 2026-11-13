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
    if not request.user.check_password(str(body.get("password", ""))):
        return JsonResponse({"error": "Your password is not correct"}, status=400)
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
    return JsonResponse({**_status(request.user), "recovery_codes": codes})


def _confirm(request):
    body = _body(request) or {}
    if not request.user.check_password(str(body.get("password", ""))):
        return JsonResponse({"error": "Your password is not correct"}, status=400)
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
