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
MSG_TYPE = (".msg", "application/vnd.ms-outlook")
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
MSG_MAX_ATTACHMENTS = 100
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


def inspect_msg(path, filename):
    """Return the .msg type for an Outlook message, None for other extensions, or raise ValueError."""
    if Path(filename).suffix.lower() != MSG_TYPE[0]:
        return None
    import olefile

    with open(path, "rb") as source:
        if source.read(8) != OLE_MAGIC:
            raise ValueError("This file does not look like an Outlook message (.msg)")
    try:
        with olefile.OleFileIO(str(path)) as ole:
            if not any(entry[0].startswith("__substg1.0_") for entry in ole.listdir()):
                raise ValueError
    except Exception as exc:  # noqa: BLE001 - any parser failure on untrusted input means "not a valid .msg"
        raise ValueError("This file does not look like an Outlook message (.msg)") from exc
    return MSG_TYPE


def _msg_property(ole, prefix, tag):
    """Read a MAPI property stream (MS-OXMSG): Unicode string, ANSI string, or binary."""
    for kind in ("001F", "001E", "0102"):
        name = f"{prefix}__substg1.0_{tag}{kind}"
        if ole.exists(name):
            data = ole.openstream(name).read()
            if kind == "001F":
                return data.decode("utf-16-le", "replace").rstrip("\x00")
            if kind == "001E":
                return data.decode("cp1252", "replace").rstrip("\x00")
            return data
    return None


def msg_to_message(path):
    """An Outlook .msg as a standard email message (headers, plain text, and attachments)."""
    import olefile
    from email.message import EmailMessage
    from email.utils import format_datetime, parsedate_to_datetime

    message = EmailMessage(policy=policy.default)
    with olefile.OleFileIO(str(path)) as ole:
        sender_name = _msg_property(ole, "", "0C1A") or ""
        sender_address = _msg_property(ole, "", "5D01") or _msg_property(ole, "", "0C1F") or ""
        headers = _msg_property(ole, "", "007D") or ""
        for name, value in (("Subject", _msg_property(ole, "", "0037")), ("To", _msg_property(ole, "", "0E04")), ("Cc", _msg_property(ole, "", "0E03"))):
            if isinstance(value, str) and value.strip():
                message[name] = " ".join(value.split())
        if sender_name or sender_address:
            message["From"] = f"{sender_name} <{sender_address}>" if sender_name and "@" in sender_address else (sender_name or sender_address)
        date_line = next((line.split(":", 1)[1].strip() for line in str(headers).splitlines() if line.lower().startswith("date:")), "")
        if date_line:
            try:
                message["Date"] = format_datetime(parsedate_to_datetime(date_line))
            except (TypeError, ValueError):
                pass
        body = _msg_property(ole, "", "1000")
        html = _msg_property(ole, "", "1013")
        if isinstance(body, str) and body.strip():
            message.set_content(body)
        elif isinstance(html, (bytes, str)):
            text = html.decode("utf-8", "replace") if isinstance(html, bytes) else html
            message.set_content(text, subtype="html")
        else:
            message.set_content("")
        storages = sorted({entry[0] for entry in ole.listdir() if entry[0].startswith("__attach_version1.0_#")})[:MSG_MAX_ATTACHMENTS]
        for storage in storages:
            prefix = storage + "/"
            data = _msg_property(ole, prefix, "3701")
            name = _msg_property(ole, prefix, "3707") or _msg_property(ole, prefix, "3704") or "attachment"
            if isinstance(data, bytes) and data and isinstance(name, str):
                message.add_attachment(data, maintype="application", subtype="octet-stream", filename=Path(name.replace("\\", "/")).name)
    return message


def subject_of(path):
    if Path(path).suffix.lower() == MSG_TYPE[0]:
        return _header(msg_to_message(path), "Subject")
    with open(path, "rb") as source:
        message = email.message_from_bytes(source.read(HEADER_SCAN_BYTES), policy=policy.default)
    return _header(message, "Subject")


def render_html(path, mime=EML_TYPE[1]):
    if mime == MSG_TYPE[1]:
        message = msg_to_message(path)
    else:
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
