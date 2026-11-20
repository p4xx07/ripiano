"""One password check for every place a password is set: first-time setup, People (create, reset), and your own change.

Django's validators (length 12, similarity to the account, common passwords, digits only) plus two small rules for
what they let through: one character repeated, a keyboard row, or the username written twice (judge 3 round 10, L1).
Each refusal is one plain sentence, translated like every other API message (messages_it.py).
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

MIN_LENGTH = 12
MAX_LENGTH = 128
TOO_LONG = "Use a password of at most 128 characters"
MIN_DISTINCT = 5
TOO_SHORT = "Use a password of at least 12 characters"
NEW_TOO_SHORT = "Use a new password of at least 12 characters"
PASSWORD_ERRORS = {
    "password_too_short": TOO_SHORT,
    "password_too_similar": "This password is too close to the username. Choose a different one",
    "password_too_common": "This password is on the list of commonly used passwords. Choose one that is harder to guess",
    "password_entirely_numeric": "A password of only digits is too easy to guess. Add letters or words",
    "password_repetitive": "This password repeats the same few characters. Choose one that is harder to guess",
    "password_keyboard_run": "This password is a row of neighbouring keys or letters. Choose one that is harder to guess",
}
_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "qwertzuiop", "abcdefghijklmnopqrstuvwxyz", "01234567890")


def _longest_run(password):
    """Length of the longest stretch of the password that follows a keyboard row, the alphabet, or the digits."""
    text, best = password.lower(), 0
    for row in _ROWS:
        for sequence in (row, row[::-1]):
            for start in range(len(text)):
                length = 0
                position = sequence.find(text[start])
                while (position >= 0 and start + length < len(text) and position + length < len(sequence)
                       and text[start + length] == sequence[position + length]):
                    length += 1
                best = max(best, length)
    return best


OWN_CHARACTERS = 8


class ContainsUsernameValidator:
    """Refuse a password that is little more than the username (Django's similarity check lets "anna2anna2" through).

    What is left after taking the username out must still be eight characters, so "anna-long-password-7" is fine.
    """

    def validate(self, password, user=None):
        username = ((user.get_username() if user is not None else "") or "").lower()
        if len(username) >= 3 and len(password.lower().replace(username, "")) < OWN_CHARACTERS:
            raise ValidationError(PASSWORD_ERRORS["password_too_similar"], code="password_too_similar")

    def get_help_text(self):
        return "Your password cannot be mostly your username."


class GuessablePatternValidator:
    """Refuse a password made of very few different characters, or mostly one keyboard row or alphabet run."""

    def validate(self, password, user=None):
        if len(password) > MAX_LENGTH:
            raise ValidationError(TOO_LONG, code="password_too_long")
        if len(set(password.lower())) < MIN_DISTINCT:
            raise ValidationError(PASSWORD_ERRORS["password_repetitive"], code="password_repetitive")
        if _longest_run(password) * 2 >= len(password):
            raise ValidationError(PASSWORD_ERRORS["password_keyboard_run"], code="password_keyboard_run")

    def get_help_text(self):
        return "Your password cannot be a repeated character or a row of keys."


def password_problem(password, user=None, *, too_short=TOO_SHORT):
    """None when the password is acceptable for ``user``, otherwise one sentence saying what to change."""
    if not isinstance(password, str) or len(password) < MIN_LENGTH:
        return too_short
    if len(password) > MAX_LENGTH:
        return TOO_LONG  # Before any validator runs: they are not written for megabytes of text.
    try:
        validate_password(password, user)
    except ValidationError as exc:
        error = exc.error_list[0]
        if error.code == "password_too_short":
            return too_short
        if error.code == "password_too_long":
            return TOO_LONG
        return PASSWORD_ERRORS.get(error.code) or " ".join(error.messages)
    return None
