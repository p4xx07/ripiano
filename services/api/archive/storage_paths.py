"""Storage-path templates: owner-defined folder layouts for the human-readable NAS browse copy.

Templates only shape the disposable browse copy; managed originals keep their stable internal paths.
"""

import re
import unicodedata

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


def render(template, document):
    """Folder parts for one document; every part is a safe single path component."""
    date = document.document_date or document.created_at.date()
    first_tag = document.tag_links.select_related("tag").order_by("tag__name").first() if "{tag}" in template else None
    values = {
        "year": f"{date.year:04d}", "month": f"{date.month:02d}", "day": f"{date.day:02d}",
        "added_year": f"{document.created_at.year:04d}", "added_month": f"{document.created_at.month:02d}",
        "correspondent": document.correspondent.name if document.correspondent_id else "No sender",
        "document_type": document.document_type.name if document.document_type_id else "No type",
        "title": document.title, "asn": f"{document.asn:06d}" if document.asn else "No ASN",
        "tag": first_tag.tag.name if first_tag else "No tag", "source": document.get_source_display(),
    }
    parts = []
    for raw in template.strip("/").split("/"):
        rendered = TEMPLATE.sub(lambda match: _component(values[match.group(1)]), raw)
        parts.append(_component(rendered))
    return parts[:MAX_DEPTH]
