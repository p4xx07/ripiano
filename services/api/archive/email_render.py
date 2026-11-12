"""Turn an email (.eml) into a printable page without loading anything remote.

The page is built from escaped text only, so links, images, scripts, and styles
in the message can never run or fetch content during conversion.
"""

import email
import html
import re
from email import policy
from html.parser import HTMLParser
from pathlib import Path

EML_TYPE = (".eml", "message/rfc822")
HEADER_SCAN_BYTES = 64 * 1024
REQUIRED_HEADERS = {"from", "date", "subject", "message-id", "to"}


def _header(message, name):
    from .mail import _header as read_header

    return read_header(message, name)


def inspect_eml(path, filename):
    """Return the .eml type if the file is a plausible email, None for other extensions."""
    if Path(filename).suffix.lower() != EML_TYPE[0]:
        return None
    with open(path, "rb") as source:
        head = source.read(HEADER_SCAN_BYTES)
    header_block = re.split(rb"\r?\n\r?\n", head, maxsplit=1)[0]
    names = {match.group(1).decode("ascii", "ignore").lower() for match in re.finditer(rb"^([A-Za-z][A-Za-z0-9-]*):", header_block, re.MULTILINE)}
    if len(names & REQUIRED_HEADERS) < 2:
        raise ValueError("This file does not look like an email (.eml) message")
    return EML_TYPE


class _TextExtractor(HTMLParser):
    """Keep readable text from HTML mail; drop scripts, styles, and markup."""

    BLOCKS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "article", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "title"}:
            self.skip += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "title"} and self.skip:
            self.skip -= 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", "".join(self.parts))).strip()


def message_text(message):
    try:
        part = message.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        content = part.get_content()
    except Exception:  # noqa: BLE001 - an unreadable body renders as empty
        return ""
    if part.get_content_type() == "text/html":
        parser = _TextExtractor()
        parser.feed(content)
        return parser.text()
    return content.strip()


def subject_of(path):
    with open(path, "rb") as source:
        message = email.message_from_bytes(source.read(HEADER_SCAN_BYTES), policy=policy.default)
    return _header(message, "Subject")


def render_html(path):
    with open(path, "rb") as source:
        message = email.message_from_bytes(source.read(), policy=policy.default)
    rows = "".join(
        f"<tr><th>{label}</th><td>{html.escape(value)}</td></tr>"
        for label, value in (("From", _header(message, "From")), ("To", _header(message, "To")), ("Cc", _header(message, "Cc")),
                             ("Date", _header(message, "Date")), ("Subject", _header(message, "Subject")))
        if value
    )
    attachments = []
    for part in message.walk():
        if part.is_multipart():
            continue
        try:
            name = part.get_filename()
        except Exception:  # noqa: BLE001
            name = None
        if name:
            attachments.append(html.escape(Path(str(name).replace("\\", "/")).name))
    attached = f"<p class='files'><b>Attachments:</b> {', '.join(attachments)}</p>" if attachments else ""
    body = html.escape(message_text(message)) or "<i>(no text)</i>"
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Email</title>"
        "<style>body{font-family:sans-serif;font-size:11pt;margin:2em}th{text-align:left;padding-right:1em;vertical-align:top}"
        "pre{white-space:pre-wrap;font-family:sans-serif}.files{color:#444}</style></head><body>"
        f"<table>{rows}</table>{attached}<hr><pre>{body}</pre></body></html>"
    )
