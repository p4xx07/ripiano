"""Send API error messages in the person's interface language.

The PWA sends `Accept-Language` with its chosen language. Messages are written in English in the
code; this middleware swaps the `error` text of JSON responses for its Italian version from
`messages_it.py` (exact strings first, then templates with placeholders). Unknown text stays English.
"""

import json
import re

from django.utils import translation
from django.utils.cache import patch_vary_headers

from .messages_it import EXACT, TEMPLATES


def _compile(template):
    parts = re.split(r"(\{\d+\})", template.replace("{{", "\0").replace("}}", "\1"))
    pattern = "".join(
        f"(?P<p{part[1:-1]}>.+?)" if re.fullmatch(r"\{\d+\}", part) else re.escape(part.replace("\0", "{").replace("\1", "}"))
        for part in parts
    )
    return re.compile(f"^{pattern}$", re.S)


_TEMPLATES = [(_compile(english), italian) for english, italian in sorted(TEMPLATES.items(), key=lambda item: -len(item[0]))]


def to_italian(message):
    if not isinstance(message, str) or not message:
        return message
    if message in EXACT:
        return EXACT[message]
    for pattern, italian in _TEMPLATES:
        match = pattern.match(message)
        if match:
            values = {int(name[1:]): value for name, value in match.groupdict().items()}
            return re.sub(r"\{(\d+)\}", lambda found: values.get(int(found.group(1)), found.group(0)), italian)
    return message


def wants_italian(request):
    return translation.get_language_from_request(request).split("-")[0] == "it"


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
