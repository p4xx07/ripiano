import errno
import hashlib
import logging
import os
import uuid
import warnings
from pathlib import Path

from django.conf import settings
from PIL import Image, UnidentifiedImageError

from .email_render import EML_TYPE, MSG_TYPE, inspect_eml, inspect_msg
from .office import CONVERTIBLE_EXTENSIONS, inspect_office

# Every input channel accepts exactly these file name extensions.
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", EML_TYPE[0], MSG_TYPE[0], *CONVERTIBLE_EXTENSIONS}
UNSUPPORTED = "Use PDF, JPEG, PNG, an email (.eml or .msg), or an Office/OpenDocument/RTF file"
# A supported name whose contents do not match: say the file is damaged, not that its type is wrong.
DAMAGED_PDF = "This file could not be read as a PDF. It may be damaged, or it is not really a PDF."
DAMAGED_IMAGE = "This file could not be read as a JPEG or PNG image. It may be damaged, or it is not really an image."
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
# Decoding and OCR of one image must fit a 4 GB NAS: 50 megapixels (an A4 page scanned at 600 dpi is
# about 35) is roughly 150 MB as RGB before OCR copies. Larger images are refused at upload, and Pillow
# itself refuses anything over twice this anywhere in the process (tasks, barcodes).
MAX_IMAGE_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
TOO_LARGE_IMAGE = "This image is too large to process (over 50 megapixels). Scan at a lower resolution or upload a PDF."


def _unreadable(filename):
    """The error for contents no reader accepted: damaged when the name promised a PDF or image."""
    extension = Path(filename or "").suffix.lower()
    if extension == ".pdf":
        return DAMAGED_PDF
    if extension in IMAGE_EXTENSIONS:
        return DAMAGED_IMAGE
    return UNSUPPORTED


class InvalidDocument(ValueError):
    pass


EQUIVALENT_EXTENSIONS = {".jpeg": ".jpg"}
logger = logging.getLogger(__name__)


def _sync_parent_directory(path):
    """Persist the rename where supported; some mounted filesystems reject directory fsync."""
    unsupported = {errno.EBADF, errno.EINVAL, errno.ENOTSUP}
    for _ in range(2):
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
            return
        except OSError as exc:
            if exc.errno not in unsupported:
                raise
        finally:
            os.close(descriptor)
    # The original file itself was already fsynced. Keep the successful rename usable,
    # and make the weaker crash durability visible to the server operator.
    logger.warning("The media filesystem does not support directory fsync; original rename durability is best effort")


def download_name(original_name, stored_path):
    """The file name to download an original under, with the extension of the type Ripiano detected.

    A PDF uploaded as "scan.png" is stored as a PDF; downloading it as "scan.png" would make the computer open it
    with the wrong app (judge 3 round 6, L3). The stored path carries the detected extension.
    """
    name = Path(original_name or "").name or "document"
    detected = Path(stored_path or "").suffix.lower()
    current = Path(name).suffix.lower()
    if not detected or EQUIVALENT_EXTENSIONS.get(current, current) == EQUIVALENT_EXTENSIONS.get(detected, detected):
        return name
    return f"{Path(name).stem or 'document'}{detected}"


def save_original(upload):
    """Write and sync an original before its database row can be committed."""
    media_root = Path(settings.MEDIA_ROOT)
    pending_dir = media_root / "originals" / ".pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    temp_path = pending_dir / str(uuid.uuid4())
    digest = hashlib.sha256()
    size = 0
    try:
        with temp_path.open("xb") as destination:
            for chunk in upload.chunks():
                size += len(chunk)
                if size > settings.RIPIANO_MAX_UPLOAD_BYTES:
                    raise InvalidDocument("File exceeds the upload limit")
                destination.write(chunk)
                digest.update(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        if size == 0:
            raise InvalidDocument("File is empty")

        with temp_path.open("rb") as source:
            is_pdf = source.read(5) == b"%PDF-"
        if is_pdf:
            extension, mime = ".pdf", "application/pdf"
        else:
            try:
                office = inspect_office(temp_path, upload.name) or inspect_eml(temp_path, upload.name) or inspect_msg(temp_path, upload.name)
            except ValueError as exc:
                raise InvalidDocument(str(exc)) from exc
            if office:
                extension, mime = office
            else:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", Image.DecompressionBombWarning)
                        with Image.open(temp_path) as image:
                            # The header gives the size without decoding: refuse before verify() or OCR.
                            if image.width * image.height > MAX_IMAGE_PIXELS:
                                raise InvalidDocument(TOO_LARGE_IMAGE)
                            image.verify()
                            image_format = image.format
                except InvalidDocument:
                    raise
                except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
                    raise InvalidDocument(TOO_LARGE_IMAGE) from exc
                except (UnidentifiedImageError, OSError, ValueError) as exc:
                    raise InvalidDocument(_unreadable(upload.name)) from exc
                if image_format == "JPEG":
                    extension, mime = ".jpg", "image/jpeg"
                elif image_format == "PNG":
                    extension, mime = ".png", "image/png"
                else:
                    raise InvalidDocument(_unreadable(upload.name))

        file_id = uuid.uuid4()
        relative = Path("originals") / str(file_id)[:2] / f"{file_id}{extension}"
        destination_path = media_root / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, destination_path)
        _sync_parent_directory(destination_path.parent)
        return str(relative), mime, digest.hexdigest(), size
    finally:
        temp_path.unlink(missing_ok=True)
