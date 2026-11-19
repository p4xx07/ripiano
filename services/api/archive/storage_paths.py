"""Storage-path templates: owner-defined folder layouts for the human-readable NAS browse copy.

Templates only shape the disposable browse copy; managed originals keep their stable internal paths.
"""

import re
import unicodedata
from pathlib import PurePath

PLACEHOLDERS = {
    "year", "month", "day", "added_year", "added_month", "correspondent", "document_type", "title", "asn", "tag", "source",
}
TEMPLATE = re.compile(r"\{([a-z_]+)\}")
MAX_DEPTH = 6
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}


def validate_template(template):
    if not isinstance(template, str) or not template.strip() or len(template) > 200:
        return "Write a template of up to 200 characters"
    if template.startswith("/") or "\\" in template or any(part in ("", ".", "..") for part in template.strip("/").split("/")):
        return "Use folder names separated by /, without empty, . or .. parts"
    unknown = sorted(set(TEMPLATE.findall(template)) - PLACEHOLDERS)
    if unknown:
        return f"Unknown placeholder: {{{unknown[0]}}}. Use " + ", ".join(f"{{{name}}}" for name in sorted(PLACEHOLDERS))
    if template.strip("/").count("/") + 1 > MAX_DEPTH:
        return f"Use at most {MAX_DEPTH} folder levels"
    return ""


def fit_bytes(value, limit=180):
    """Trim so the UTF-8 name fits NAS filesystems (255-byte names) with room for a suffix."""
    while len(value.encode("utf-8")) > limit:
        value = value[:-1]
    return value


def _component(value):
    value = unicodedata.normalize("NFC", str(value))
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .")[:80]
    value = fit_bytes(value).rstrip(" .")
    value = value.replace("--", "-")  # "--" marks a document leaf folder; never let a rendered folder imitate one
    if value.split(".")[0].upper() in WINDOWS_RESERVED:
        value += "_"  # SMB shares on Windows clients cannot open CON, NUL, COM1, …
    return value or "None"


def _values(template, document):
    date = document.document_date or document.created_at.date()
    first_tag = document.tag_links.select_related("tag").order_by("tag__name").first() if "{tag}" in template else None
    return {
        "year": f"{date.year:04d}", "month": f"{date.month:02d}", "day": f"{date.day:02d}",
        "added_year": f"{document.created_at.year:04d}", "added_month": f"{document.created_at.month:02d}",
        "correspondent": document.correspondent.name if document.correspondent_id else "No sender",
        "document_type": document.document_type.name if document.document_type_id else "No type",
        "title": document.title, "asn": f"{document.asn:06d}" if document.asn else "No ASN",
        "tag": first_tag.tag.name if first_tag else "No tag", "source": document.get_source_display(),
    }


def render(template, document):
    """Folder parts for one document; every part is a safe single path component."""
    values = _values(template, document)
    parts = []
    for raw in template.strip("/").split("/"):
        rendered = TEMPLATE.sub(lambda match: _component(values[match.group(1)]), raw)
        parts.append(_component(rendered))
    return parts[:MAX_DEPTH]


# Workflow title templates use the same placeholders, plus whole dates and the original file name.
TITLE_PLACEHOLDERS = PLACEHOLDERS | {"date", "added_date", "added_day", "original_filename"}
TITLE_MAX = 300  # Document.title


def validate_title_template(template):
    if not isinstance(template, str) or not template.strip() or len(template) > 200 or re.search(r"[\x00-\x1f\x7f]", template):
        return "Write a title template of up to 200 characters on one line"
    unknown = sorted(set(TEMPLATE.findall(template)) - TITLE_PLACEHOLDERS)
    if unknown:
        bad, allowed = f"{{{unknown[0]}}}", ", ".join(f"{{{name}}}" for name in sorted(TITLE_PLACEHOLDERS))
        return f"The title template uses an unknown placeholder: {bad}. Use {allowed}"
    return ""


def render_title(template, document):
    """The title a template gives one document: one line, at most 300 characters; "" if nothing is left."""
    date = document.document_date or document.created_at.date()
    values = _values(template, document)
    values.update(date=date.isoformat(), added_date=document.created_at.date().isoformat(), added_day=f"{document.created_at.day:02d}",
                  original_filename=PurePath(document.original_name).stem)
    title = TEMPLATE.sub(lambda match: str(values.get(match.group(1), match.group(0))), template)
    title = re.sub(r"[\x00-\x1f\x7f]", " ", unicodedata.normalize("NFC", title))
    return re.sub(r"\s+", " ", title).strip()[:TITLE_MAX].strip()
