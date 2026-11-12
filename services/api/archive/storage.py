import hashlib
import os
import uuid
from pathlib import Path

from django.conf import settings
from PIL import Image, UnidentifiedImageError

from .email_render import EML_TYPE, inspect_eml
from .office import CONVERTIBLE_EXTENSIONS, inspect_office

# Every input channel accepts exactly these file name extensions.
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", EML_TYPE[0], *CONVERTIBLE_EXTENSIONS}
UNSUPPORTED = "Use PDF, JPEG, PNG, an email (.eml), or an Office/OpenDocument/RTF file"


class InvalidDocument(ValueError):
    pass


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
                office = inspect_office(temp_path, upload.name) or inspect_eml(temp_path, upload.name)
            except ValueError as exc:
                raise InvalidDocument(str(exc)) from exc
            if office:
                extension, mime = office
            else:
                try:
                    with Image.open(temp_path) as image:
                        image.verify()
                        image_format = image.format
                except (UnidentifiedImageError, OSError, ValueError) as exc:
                    raise InvalidDocument(UNSUPPORTED) from exc
                if image_format == "JPEG":
                    extension, mime = ".jpg", "image/jpeg"
                elif image_format == "PNG":
                    extension, mime = ".png", "image/png"
                else:
                    raise InvalidDocument(UNSUPPORTED)

        file_id = uuid.uuid4()
        relative = Path("originals") / str(file_id)[:2] / f"{file_id}{extension}"
        destination_path = media_root / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temp_path, destination_path)
        directory_fd = os.open(destination_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return str(relative), mime, digest.hexdigest(), size
    finally:
        temp_path.unlink(missing_ok=True)
