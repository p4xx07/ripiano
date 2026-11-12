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
OFFICE_EXTENSIONS = {mime: extension for extension, (mime, _) in OFFICE_TYPES.items()}
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_CONVERTED_BYTES = 100 * 1024 * 1024


class OfficeConversionError(RuntimeError):
    pass


def inspect_office(path, filename):
    extension = Path(filename).suffix.lower()
    if extension not in OFFICE_TYPES:
        return None
    mime, main_part = OFFICE_TYPES[extension]
    try:
        with ZipFile(path) as package:
            entries = package.infolist()
            names = {entry.filename for entry in entries}
            if not entries or len(entries) > 5000 or "[Content_Types].xml" not in names or main_part not in names:
                raise ValueError
            if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError
            if any(entry.flag_bits & 1 or entry.filename.lower().endswith("vbaproject.bin") for entry in entries):
                raise ValueError
    except (OSError, BadZipFile, ValueError) as exc:
        raise ValueError("This Office file is invalid, encrypted, or too large to expand") from exc
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
