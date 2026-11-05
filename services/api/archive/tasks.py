import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader

from .backup import create_snapshot
from .classification import apply_rules
from .models import BackupRun, Document, DocumentTag, FilingRule

logger = logging.getLogger(__name__)


@shared_task(name="archive.tasks.process_document")
def process_document(document_id):
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document_id)
        if document.status != Document.Status.PENDING:
            return
        document.status = Document.Status.PROCESSING
        document.processing_started_at = timezone.now()
        document.error = ""
        document.save(update_fields=["status", "processing_started_at", "error"])

    media_root = Path(settings.MEDIA_ROOT)
    original = media_root / document.original_path
    archive_dir = media_root / "archive" / str(document.id)[:2]
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f"{document.id}.pdf"

    try:
        with tempfile.TemporaryDirectory(dir=media_root) as work_dir:
            work_dir = Path(work_dir)
            input_file = original
            if document.original_mime.startswith("image/"):
                input_file = work_dir / "input.pdf"
                with Image.open(original) as image:
                    image.convert("RGB").save(input_file, "PDF", resolution=300)
            output_file = work_dir / "archive.pdf"
            subprocess.run(
                [
                    str(Path(sys.executable).parent / "ocrmypdf"), "--skip-text", "--output-type", "pdfa",
                    "--language", settings.RIPIANO_OCR_LANGUAGES,
                    "--skip-big", "50", str(input_file), str(output_file),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=3300,
            )
            text = "\n".join(page.extract_text() or "" for page in PdfReader(output_file).pages)
            with output_file.open("rb") as source:
                os.fsync(source.fileno())
            os.replace(output_file, archive)
        document.archive_path = str(archive.relative_to(media_root))
        document.extracted_text = text
        document.status = Document.Status.READY
        document.error = ""
        document.processed_at = timezone.now()
        document.save(update_fields=["archive_path", "extracted_text", "status", "error", "processed_at"])
    except Exception as exc:
        logger.exception("Document processing failed: %s", document.id)
        if isinstance(exc, subprocess.CalledProcessError):
            logger.error("OCR diagnostic: %s", (exc.stderr or "")[-2000:])
        document.status = Document.Status.FAILED
        diagnostic = (exc.stderr or "").strip() if isinstance(exc, subprocess.CalledProcessError) else ""
        document.error = (diagnostic.splitlines()[-1] if diagnostic else str(exc))[:500]
        document.save(update_fields=["status", "error"])
        return
    try:
        apply_rules(document)
    except Exception:
        logger.exception("Automatic filing failed for document %s", document.id)


@shared_task(name="archive.tasks.reconcile_pending_documents")
def reconcile_pending_documents():
    stale_before = timezone.now() - timedelta(hours=1)
    Document.objects.filter(
        status=Document.Status.PROCESSING,
        processing_started_at__lt=stale_before,
    ).update(status=Document.Status.PENDING, processing_started_at=None)
    for document_id in Document.objects.filter(status=Document.Status.PENDING).values_list("id", flat=True)[:100]:
        process_document.delay(str(document_id))


@shared_task(name="archive.tasks.backup_archive", time_limit=6 * 3600)
def backup_archive(run_id=None):
    run = BackupRun.objects.get(pk=run_id) if run_id else BackupRun.objects.create(trigger="schedule")
    run.status = BackupRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    try:
        snapshot = create_snapshot()
        run.status = BackupRun.Status.COMPLETE
        run.snapshot_name = snapshot.name
        run.completed_at = timezone.now()
        run.error = ""
    except Exception as exc:
        logger.exception("Backup failed: %s", run.id)
        run.status = BackupRun.Status.FAILED
        run.completed_at = timezone.now()
        run.error = str(exc)[:500]
    run.save(update_fields=["status", "snapshot_name", "completed_at", "error"])


@shared_task(name="archive.tasks.reclassify_owner")
def reclassify_owner(owner_id):
    for document in Document.objects.filter(owner_id=owner_id, status=Document.Status.READY).iterator():
        try:
            apply_rules(document)
        except Exception:
            logger.exception("Automatic filing failed for document %s", document.id)


@shared_task(name="archive.tasks.reclassify_filing_candidates")
def reclassify_filing_candidates(owner_id, kind, target_id, pattern, field="either", deleted=False):
    documents = Document.objects.filter(owner_id=owner_id, status=Document.Status.READY)
    if deleted:
        field = "correspondent" if kind == FilingRule.Kind.CORRESPONDENT else "document_type"
        documents = documents.filter(**{f"{field}_id": target_id, f"{field}_origin": Document.FilingOrigin.RULE})
    needle = pattern.casefold()
    for document in documents.iterator():
        if not deleted and not (
            (field in (FilingRule.Field.TITLE, FilingRule.Field.EITHER) and needle in document.title.casefold())
            or (field in (FilingRule.Field.TEXT, FilingRule.Field.EITHER) and needle in document.extracted_text.casefold())
        ):
            continue
        try:
            apply_rules(document)
        except Exception:
            logger.exception("Automatic filing failed for document %s", document.id)


@shared_task(name="archive.tasks.reclassify_tag_candidates")
def reclassify_tag_candidates(owner_id, tag_id, phrases, deleted=False):
    documents = Document.objects.filter(owner_id=owner_id, status=Document.Status.READY)
    if deleted:
        documents = documents.filter(tag_links__tag_id=tag_id, tag_links__origin=DocumentTag.Origin.RULE)
    compiled = [(entry["pattern"].casefold(), entry["field"]) for entry in phrases]
    for document in documents.iterator():
        if not deleted:
            title = document.title.casefold()
            text = document.extracted_text.casefold()
            if not any(
                (field in ("title", "either") and pattern in title)
                or (field in ("text", "either") and pattern in text)
                for pattern, field in compiled
            ):
                continue
        try:
            apply_rules(document)
        except Exception:
            logger.exception("Automatic tagging failed for document %s", document.id)
