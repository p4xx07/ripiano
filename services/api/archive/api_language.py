"""Send API error messages in the person's interface language.

The PWA sends `Accept-Language` with its chosen language. Messages are written in English in the
code; this middleware swaps the `error` text of JSON responses for its Italian version from
`messages_it.py` (exact strings first, then templates with placeholders). Unknown text stays English.
"""

import json
import re

from django.utils import translation
from django.utils.cache import patch_vary_headers

from .messages_it import DISPLAY, EXACT, TEMPLATES, VALUES


def _compile(template):
    parts = re.split(r"(\{\d+\})", template.replace("{{", "\0").replace("}}", "\1"))
    pattern = "".join(
        f"(?P<p{part[1:-1]}>.+?)" if re.fullmatch(r"\{\d+\}", part) else re.escape(part.replace("\0", "{").replace("\1", "}"))
        for part in parts
    )
    return re.compile(f"^{pattern}$", re.S)


_TEMPLATES = [(_compile(english), italian, english.startswith("{0} ") or english == "Enter the {0}")
              for english, italian in sorted(TEMPLATES.items(), key=lambda item: -len(item[0]))]


def _value(text):
    """A field name inside a template (from archive.field_labels), keeping its capitalization."""
    if text in VALUES:
        return VALUES[text]
    italian = VALUES.get(text[:1].upper() + text[1:])
    return italian[:1].lower() + italian[1:] if italian else text


def to_italian(message):
    if not isinstance(message, str) or not message:
        return message
    if message in EXACT:
        return EXACT[message]
    for pattern, italian, names_field in _TEMPLATES:
        match = pattern.match(message)
        if match:
            # Only a leading {0} (or "Enter the {0}") is a field name; other values are user data and stay as written.
            values = {int(name[1:]): _value(value) if names_field and name == "p0" else value for name, value in match.groupdict().items()}
            return re.sub(r"\{(\d+)\}", lambda found: values.get(int(found.group(1)), found.group(0)), italian)
    return message


def wants_italian(request):
    return translation.get_language_from_request(request).split("-")[0] == "it"


def display(request, text, *values):
    """Display text (not an error) in the request's language: `text` may hold {0}-style placeholders."""
    if request is not None and wants_italian(request):
        text = DISPLAY.get(text, text)
    return text.format(*values) if values else text


class ApiLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        italian = request.path.startswith("/api/") and wants_italian(request)
        if not italian:
            response = self.get_response(request)
            if request.path.startswith("/api/"):
                patch_vary_headers(response, ("Accept-Language",))
            return response
        # Django's own messages (for example password rules) use its Italian catalog.
        with translation.override("it"):
            response = self.get_response(request)
        if response.get("Content-Type", "").startswith("application/json") and not getattr(response, "streaming", False):
            try:
                payload = json.loads(response.content)
            except (ValueError, UnicodeDecodeError):
                return response
            if isinstance(payload, dict) and isinstance(payload.get("error"), str):
                translated = to_italian(payload["error"])
                if translated != payload["error"]:
                    payload["error"] = translated
                    response.content = json.dumps(payload, ensure_ascii=False).encode()
                    response["Content-Length"] = str(len(response.content))
        response["Content-Language"] = "it"
        patch_vary_headers(response, ("Accept-Language",))
        return response
