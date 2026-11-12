"""Inspect Office originals and convert them with the private LibreOffice service."""

import os
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import httpx
from django.conf import settings

OFFICE_TYPES = {
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "word/document.xml"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xl/workbook.xml"),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "ppt/presentation.xml"),
}
# OpenDocument packages declare their type in an uncompressed "mimetype" entry.
ODF_TYPES = {
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
}
# Pre-2007 binary Office files are OLE compound documents.
LEGACY_TYPES = {
    ".doc": "application/msword",
    ".xls": "application/vnd.ms-excel",
    ".ppt": "application/vnd.ms-powerpoint",
}
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
RTF_TYPE = (".rtf", "application/rtf")
OFFICE_EXTENSIONS = {
    **{mime: extension for extension, (mime, _) in OFFICE_TYPES.items()},
    **{mime: extension for extension, mime in ODF_TYPES.items()},
    **{mime: extension for extension, mime in LEGACY_TYPES.items()},
    RTF_TYPE[1]: RTF_TYPE[0],
}
CONVERTIBLE_EXTENSIONS = set(OFFICE_EXTENSIONS.values())
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_CONVERTED_BYTES = 100 * 1024 * 1024


class OfficeConversionError(RuntimeError):
    pass


def _inspect_package(path, required, *, mimetype=None):
    try:
        with ZipFile(path) as package:
            entries = package.infolist()
            names = {entry.filename for entry in entries}
            if not entries or len(entries) > 5000 or not required <= names:
                raise ValueError
            if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError
            if any(entry.flag_bits & 1 or entry.filename.lower().endswith("vbaproject.bin") for entry in entries):
                raise ValueError
            if mimetype is not None and package.read("mimetype").strip() != mimetype.encode():
                raise ValueError
            if mimetype is not None and any(name.lower().startswith(("basic/", "scripts/")) for name in names):
                raise ValueError  # OpenDocument macros or scripts
            if mimetype is not None and "META-INF/manifest.xml" in names and b"encryption-data" in package.read("META-INF/manifest.xml"):
                raise ValueError  # OpenDocument password protection
    except (OSError, BadZipFile, ValueError, KeyError) as exc:
        raise ValueError("This Office file is invalid, password-protected, contains macros, or is too large to expand") from exc


def inspect_office(path, filename):
    """Return (extension, mime) for a convertible document, None if it is not one, or raise ValueError."""
    extension = Path(filename).suffix.lower()
    if extension in ODF_TYPES:
        _inspect_package(path, {"mimetype", "content.xml"}, mimetype=ODF_TYPES[extension])
        return extension, ODF_TYPES[extension]
    if extension in LEGACY_TYPES:
        with open(path, "rb") as source:
            if source.read(8) != OLE_MAGIC:
                raise ValueError("This file does not look like an older Office document")
        return extension, LEGACY_TYPES[extension]
    if extension == RTF_TYPE[0]:
        with open(path, "rb") as source:
            if not source.read(5).startswith(b"{\\rtf"):
                raise ValueError("This file does not look like an RTF document")
        return RTF_TYPE
    if extension not in OFFICE_TYPES:
        return None
    mime, main_part = OFFICE_TYPES[extension]
    _inspect_package(path, {"[Content_Types].xml", main_part})
    return extension, mime


def convert_office(source_path, original_name, mime, destination):
    origin = settings.RIPIANO_CONVERTER_URL.rstrip("/")
    if not origin:
        raise OfficeConversionError("Office converter is not configured")
    destination = Path(destination)
    complete = False
    try:
        timeout = httpx.Timeout(connect=5, read=180, write=60, pool=5)
        with source_path.open("rb") as source, httpx.Client(timeout=timeout, trust_env=False) as client:
            with client.stream("POST", f"{origin}/forms/libreoffice/convert", files={"files": (original_name, source, mime)}) as response:
                if response.status_code != 200:
                    raise OfficeConversionError(f"Office conversion failed ({response.status_code}); check the file and retry")
                if not response.headers.get("content-type", "").startswith("application/pdf"):
                    raise OfficeConversionError("Office converter did not return a PDF")
                size = 0
                with destination.open("xb") as output:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_CONVERTED_BYTES:
                            raise OfficeConversionError("Converted PDF exceeds the 100 MB limit")
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                with destination.open("rb") as output:
                    if size < 5 or output.read(5) != b"%PDF-":
                        raise OfficeConversionError("Office converter returned an invalid PDF")
                complete = True
    except (httpx.HTTPError, OSError) as exc:
        raise OfficeConversionError("Office converter is unavailable; retry this document when it is running") from exc
    finally:
        if not complete:
            destination.unlink(missing_ok=True)
