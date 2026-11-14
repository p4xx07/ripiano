import time
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from archive import two_factor
from archive.models import AccountSecurity


def test_codes_follow_rfc_6238_and_cannot_be_replayed():
    # RFC 6238 appendix B, SHA-1 secret "12345678901234567890" at T=59 → 94287082 (last 6 digits: 287082).
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert two_factor._code(secret, 59 // 30) == "287082"
    step = two_factor.matching_step(secret, "287082", now=59)
    assert step == 1
    assert two_factor.matching_step(secret, "287082", now=59, last_step=step) is None
    assert two_factor.matching_step(secret, "12345", now=59) is None


@pytest.mark.django_db
def test_two_step_sign_in_setup_login_recovery_and_lockout():
    user = get_user_model().objects.create_user("owner", password="secure-password-1")
    client = Client()
    client.force_login(user)
    assert client.post("/api/account/security/setup", {"password": "wrong"}, content_type="application/json").status_code == 400
    setup = client.post("/api/account/security/setup", {"password": "secure-password-1"}, content_type="application/json").json()
    assert setup["uri"].startswith("otpauth://totp/Ripiano:owner?secret=") and setup["qr_svg"].startswith("<svg")
    assert setup["secret"] not in AccountSecurity.objects.get(user=user).pending_secret  # stored encrypted
    assert client.post("/api/account/security/enable", {"code": "000000"}, content_type="application/json").status_code == 400
    now = time.time()
    code = two_factor._code(setup["secret"], int(now // 30))
    enabled = client.post("/api/account/security/enable", {"code": code}, content_type="application/json").json()
    assert enabled["two_factor"] is True and len(enabled["recovery_codes"]) == 10
    assert AccountSecurity.objects.get(user=user).recovery_hashes[0] not in enabled["recovery_codes"]

    anonymous = Client()
    first = anonymous.post("/api/session", {"username": "owner", "password": "secure-password-1"}, content_type="application/json")
    assert first.status_code == 401 and first.json()["two_factor_required"] is True
    assert anonymous.get("/api/session").json()["authenticated"] is False
    replay = anonymous.post("/api/session", {"username": "owner", "password": "secure-password-1", "code": code}, content_type="application/json")
    assert replay.status_code == 401  # the setup code was already used
    recovery = enabled["recovery_codes"][0]
    assert anonymous.post("/api/session", {"username": "owner", "password": "secure-password-1", "code": recovery}, content_type="application/json").status_code == 200
    assert anonymous.get("/api/session").json()["authenticated"] is True
    other = Client()
    assert other.post("/api/session", {"username": "owner", "password": "secure-password-1", "code": recovery}, content_type="application/json").status_code == 401

    for _ in range(5):
        other.post("/api/session", {"username": "owner", "password": "secure-password-1", "code": "111111"}, content_type="application/json")
    future = two_factor._code(setup["secret"], int(time.time() // 30) + 1)
    locked = other.post("/api/session", {"username": "owner", "password": "secure-password-1", "code": future}, content_type="application/json")
    assert locked.status_code == 401 and "Too many" in locked.json()["error"]
    assert other.post("/api/session", {"username": "owner", "password": "wrong-password", "code": future}, content_type="application/json").json()["error"] == "Invalid credentials"

    AccountSecurity.objects.filter(user=user).update(locked_until=None)
    __import__("django.core.cache", fromlist=["cache"]).cache.clear()  # the attempts above also count toward the password throttle
    later = two_factor._code(setup["secret"], int(time.time() // 30) + 1)
    with patch("archive.two_factor.time.time", return_value=time.time() + 30):
        assert client.post("/api/account/security/disable", {"password": "secure-password-1", "code": later}, content_type="application/json").json()["two_factor"] is False
    assert Client().post("/api/session", {"username": "owner", "password": "secure-password-1"}, content_type="application/json").status_code == 200


@pytest.mark.django_db
def test_admin_needs_a_ripiano_sign_in_and_recovery_beats_lockout_and_password_guessing_is_throttled():
    from django.core.cache import cache
    from django.core.management import call_command

    cache.clear()
    owner = get_user_model().objects.create_superuser("admin-owner", password="secure-password-1")
    admin_client = Client()
    assert admin_client.post("/admin/login/", {"username": "admin-owner", "password": "secure-password-1"})["Location"] == "/"
    assert admin_client.get("/admin/").status_code == 302  # no session from the admin form
    forced = Client()
    forced.force_login(owner)  # a session that did not come through Ripiano's sign-in
    assert forced.get("/admin/").status_code == 302
    signed_in = Client()
    assert signed_in.post("/api/session", {"username": "admin-owner", "password": "secure-password-1"}, content_type="application/json").status_code == 200
    assert signed_in.get("/admin/").status_code == 200

    secret = two_factor.begin_setup(owner)
    codes = two_factor.finish_setup(owner, two_factor._code(secret, int(time.time() // 30)))
    AccountSecurity.objects.filter(user=owner).update(locked_until="2999-01-01T00:00:00Z")
    assert two_factor.verify(owner, "123456")[0] is False
    assert two_factor.verify(owner, codes[0]) == (True, "")  # a recovery code works even while locked
    AccountSecurity.objects.filter(user=owner).update(totp_secret="unreadable")
    assert "recovery code" in two_factor.verify(owner, "123456")[1]
    call_command("reset_two_factor", "admin-owner")
    assert two_factor.is_enabled(owner) is False

    guesser = Client()
    for _ in range(10):
        guesser.post("/api/session", {"username": "admin-owner", "password": "wrong"}, content_type="application/json")
    blocked = guesser.post("/api/session", {"username": "admin-owner", "password": "secure-password-1"}, content_type="application/json")
    assert blocked.status_code == 429
    cache.clear()


@pytest.mark.django_db
def test_turning_on_two_step_ends_other_sessions_and_password_checks_are_throttled():
    user = get_user_model().objects.create_user("owner", password="secure-password-1")
    laptop, phone = Client(), Client()
    laptop.force_login(user)
    phone.force_login(user)
    assert phone.get("/api/session").json()["authenticated"] is True
    secret = laptop.post("/api/account/security/setup", {"password": "secure-password-1"}, content_type="application/json").json()["secret"]
    laptop.post("/api/account/security/enable", {"code": two_factor._code(secret, int(time.time() // 30))}, content_type="application/json")
    assert laptop.get("/api/session").json()["authenticated"] is True
    assert phone.get("/api/session").json()["authenticated"] is False

    guesser = Client()
    guesser.force_login(get_user_model().objects.create_user("other", password="secure-password-2"))
    for _ in range(10):
        guesser.post("/api/account/security/setup", {"password": "wrong"}, content_type="application/json")
    assert guesser.post("/api/account/security/setup", {"password": "secure-password-2"}, content_type="application/json").status_code == 429
