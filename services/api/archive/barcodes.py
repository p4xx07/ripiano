"""Local barcode reading for paper workflows: separator sheets, ASN labels, and tag codes.

Pages are rasterized with Ghostscript and read with zbar; nothing leaves the NAS.
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from PIL import Image

logger = logging.getLogger(__name__)
MAX_PAGE_PIXELS = 40_000_000  # about A0 at 200 dpi


@dataclass
class BarcodeScan:
    pages: int = 0
    scanned: int = 0
    separators: list[int] = field(default_factory=list)  # zero-based page indexes
    asn: int | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def truncated(self):
        return self.scanned < self.pages


def _read(image):
    from pyzbar import pyzbar  # needs the system zbar library (Debian: libzbar0t64)

    try:
        return [result.data.decode("utf-8", "replace").strip() for result in pyzbar.decode(image.convert("L")) if result.data]
    except Exception:  # noqa: BLE001 - an unreadable page has no barcodes
        logger.warning("Barcode reading failed on one page", exc_info=True)
        return []


def _classify(scan, page, texts):
    asn = re.compile(rf"^{re.escape(settings.RIPIANO_BARCODE_ASN_PREFIX)}\s*0*(\d{{1,9}})$", re.IGNORECASE)
    for text in texts:
        if text.casefold() == settings.RIPIANO_BARCODE_SEPARATOR.casefold():
            if page not in scan.separators:
                scan.separators.append(page)
        elif (match := asn.match(text)) and scan.asn is None and int(match[1]) > 0:
            scan.asn = int(match[1])
        elif text.casefold().startswith(settings.RIPIANO_BARCODE_TAG_PREFIX.casefold()):
            name = text[len(settings.RIPIANO_BARCODE_TAG_PREFIX):].strip()
            if name and name.casefold() not in {item.casefold() for item in scan.tags}:
                scan.tags.append(name[:100])


def scan_pdf(pdf, work_dir):
    """Read barcodes from up to RIPIANO_BARCODE_MAX_PAGES pages of a PDF."""
    from pypdf import PdfReader

    reader = PdfReader(pdf)
    scan = BarcodeScan(pages=len(reader.pages))
    last = min(scan.pages, settings.RIPIANO_BARCODE_MAX_PAGES)
    # Refuse absurd page sizes (e.g. hostile mail attachments) instead of rendering gigapixel images.
    limit = MAX_PAGE_PIXELS / (settings.RIPIANO_BARCODE_DPI / 72) ** 2
    if any(float(item.mediabox.width) * float(item.mediabox.height) > limit for item in reader.pages[:last]):
        logger.warning("Barcode scan skipped: a page is larger than the safe rendering size")
        return scan
    scan.scanned = last
    if not last:
        return scan
    pattern = Path(work_dir) / "barcode-%04d.png"
    subprocess.run(
        ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pnggray", f"-r{settings.RIPIANO_BARCODE_DPI}",
         "-dFirstPage=1", f"-dLastPage={last}", f"-sOutputFile={pattern}", str(pdf)],
        check=True, capture_output=True, timeout=600,
    )
    for index in range(last):
        page = Path(work_dir) / f"barcode-{index + 1:04d}.png"
        if not page.exists():
            continue
        with Image.open(page) as image:
            _classify(scan, index, _read(image))
        page.unlink(missing_ok=True)
    return scan


def scan_image(path):
    scan = BarcodeScan(pages=1, scanned=1)
    with Image.open(path) as image:
        _classify(scan, 0, _read(image))
    return scan


def split_ranges(scan):
    """Page ranges between separator sheets; the separator pages themselves are dropped."""
    ranges, start = [], 0
    for separator in sorted(scan.separators):
        if separator > start:
            ranges.append((start, separator))
        start = separator + 1
    if start < scan.pages:
        ranges.append((start, scan.pages))
    return ranges
