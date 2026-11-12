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
from django.db import models
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader

from .backup import BackupError, backup_media_lock, create_snapshot
from .classification import apply_rules
from .models import BackupRun, Document, DocumentTag, FilingRule, PurgeJob, TrashRetentionPolicy
from .purge import record_purge, remove_job_media

logger = logging.getLogger(__name__)


@shared_task(name="archive.tasks.process_document")
def process_document(document_id):
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document_id)
        if document.status != Document.Status.PENDING or document.trashed_at:
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
        trashed_at__isnull=True,
        status=Document.Status.PROCESSING,
        processing_started_at__lt=stale_before,
    ).update(status=Document.Status.PENDING, processing_started_at=None)
    for document_id in Document.objects.filter(status=Document.Status.PENDING, trashed_at__isnull=True).values_list("id", flat=True)[:100]:
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


@shared_task(name="archive.tasks.purge_document")
def purge_document(job_id):
    try:
        with backup_media_lock():
            with transaction.atomic():
                job = PurgeJob.objects.select_for_update().get(pk=job_id)
                if job.status not in {PurgeJob.Status.PENDING, PurgeJob.Status.RUNNING}:
                    return
                job.status = PurgeJob.Status.RUNNING
                job.started_at = timezone.now()
                job.error = ""
                job.save(update_fields=["status", "started_at", "error"])
            try:
                remove_job_media(job)
            except Exception as exc:
                logger.exception("Permanent deletion cleanup failed: %s", job.id)
                job.status = PurgeJob.Status.FAILED
                job.error = str(exc)[:500]
                job.save(update_fields=["status", "error"])
                return
            job.status = PurgeJob.Status.COMPLETE
            job.completed_at = timezone.now()
            job.title = ""
            job.original_path = ""
            job.archive_path = ""
            job.original_sha256 = ""
            job.save(update_fields=["status", "completed_at", "title", "original_path", "archive_path", "original_sha256"])
    except BackupError:
        # The snapshot still needs its files. The scheduler retries pending jobs.
        logger.info("Permanent deletion waits for the current backup: %s", job_id)
    except Exception as exc:
        logger.exception("Permanent deletion could not access its storage: %s", job_id)
        PurgeJob.objects.filter(pk=job_id).update(status=PurgeJob.Status.FAILED, error=str(exc)[:500])


@shared_task(name="archive.tasks.reconcile_purge_jobs")
def reconcile_purge_jobs():
    stale_before = timezone.now() - timedelta(hours=1)
    ids = list(PurgeJob.objects.filter(
        models.Q(status=PurgeJob.Status.PENDING)
        | models.Q(status=PurgeJob.Status.RUNNING, started_at__lt=stale_before)
    ).order_by("created_at").values_list("id", flat=True)[:25])
    for job_id in ids:
        purge_document.delay(str(job_id))


@shared_task(name="archive.tasks.purge_expired_trash")
def purge_expired_trash():
    """Queue expired Trash items only for owners who opted in."""
    owner_ids = list(TrashRetentionPolicy.objects.filter(enabled=True).values_list("owner_id", flat=True))
    for owner_id in owner_ids:
        for _ in range(1000):
            try:
                with transaction.atomic():
                    policy = TrashRetentionPolicy.objects.select_for_update().get(owner_id=owner_id)
                    if not policy.enabled:
                        break
                    cutoff = timezone.now() - timedelta(days=policy.days)
                    document = Document.objects.select_for_update().filter(
                        owner_id=owner_id, trashed_at__lte=cutoff,
                    ).order_by("trashed_at", "id").first()
                    if document is None:
                        break
                    job = record_purge(document)
            except TrashRetentionPolicy.DoesNotExist:
                break
            except Exception:
                logger.exception("Automatic Trash cleanup failed for owner %s", owner_id)
                break
            try:
                purge_document.delay(str(job.id))
            except Exception:
                # The persisted pending job is retried by reconcile_purge_jobs.
                logger.exception("Could not queue automatic Trash cleanup %s", job.id)


@shared_task(name="archive.tasks.reclassify_owner")
def reclassify_owner(owner_id):
    for document in Document.objects.filter(owner_id=owner_id, status=Document.Status.READY, trashed_at__isnull=True).iterator():
        try:
            apply_rules(document)
        except Exception:
            logger.exception("Automatic filing failed for document %s", document.id)


@shared_task(name="archive.tasks.reclassify_filing_candidates")
def reclassify_filing_candidates(owner_id, kind, target_id, pattern, field="either", deleted=False):
    documents = Document.objects.filter(owner_id=owner_id, status=Document.Status.READY, trashed_at__isnull=True)
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
    documents = Document.objects.filter(owner_id=owner_id, status=Document.Status.READY, trashed_at__isnull=True)
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
