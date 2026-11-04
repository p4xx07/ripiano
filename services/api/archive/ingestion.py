import logging
from pathlib import Path

from django.conf import settings

from .models import Document
from .storage import save_original
from .tasks import process_document

logger = logging.getLogger(__name__)


def ingest_document(owner, upload, *, source=Document.Source.WEB, source_ref=""):
    """Shared durable entry point for browser and external document inputs."""
    original_path, mime, digest, size = save_original(upload)
    name = Path(upload.name).name[:500]
    try:
        document = Document.objects.create(
            owner=owner,
            source=source,
            source_ref=source_ref,
            title=Path(name).stem[:300] or "Untitled document",
            original_name=name,
            original_path=original_path,
            original_mime=mime,
            original_sha256=digest,
            original_size=size,
        )
    except Exception:
        (Path(settings.MEDIA_ROOT) / original_path).unlink(missing_ok=True)
        raise
    try:
        process_document.delay(str(document.id))
    except Exception:
        logger.exception("Queue unavailable; pending document will be reconciled")
    return document
