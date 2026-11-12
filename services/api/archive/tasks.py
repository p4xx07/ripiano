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
from .browse_export import build_browse_tree, prune_old_browse_trees
from .classification import apply_rules
from .models import BackupRun, BrowseExportRun, Document, DocumentTag, FilingRule, PurgeJob, TrashRetentionPolicy
from .email_render import EML_TYPE, render_html
from .office import OFFICE_EXTENSIONS, convert_office
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
            output_type = "pdfa"
            if document.original_mime.startswith("image/"):
                input_file = work_dir / "input.pdf"
                with Image.open(original) as image:
                    image.convert("RGB").save(input_file, "PDF", resolution=300)
            elif document.original_mime == EML_TYPE[1]:
                page = work_dir / "message.html"
                page.write_text(render_html(original), encoding="utf-8")
                input_file = work_dir / "input.pdf"
                convert_office(page, "message.html", "text/html", input_file)
                output_type = "pdf"
            elif document.original_mime in OFFICE_EXTENSIONS:
                input_file = work_dir / "input.pdf"
                convert_office(original, document.original_name, document.original_mime, input_file)
                # PDF/A conversion can damage LibreOffice's text map; keep its searchable text.
                output_type = "pdf"
            if settings.RIPIANO_BARCODES and (document.original_mime == "application/pdf" or document.original_mime.startswith("image/")):
                apply_barcodes(document, original, input_file, work_dir)
            output_file = work_dir / "archive.pdf"
            subprocess.run(
                [
                    str(Path(sys.executable).parent / "ocrmypdf"), "--skip-text", "--output-type", output_type,
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


@shared_task(name="archive.tasks.build_browse_export", time_limit=6 * 3600)
def build_browse_export(run_id):
    with transaction.atomic():
        run = BrowseExportRun.objects.select_for_update().filter(pk=run_id).first()
        if run is None or run.status != BrowseExportRun.Status.PENDING:
            return
        run.status = BrowseExportRun.Status.RUNNING
        run.started_at = timezone.now()
        run.error = ""
        run.save(update_fields=["status", "started_at", "error"])
    try:
        folder_name, count = build_browse_tree(run)
    except Exception as exc:
        logger.exception("NAS browse export failed: %s", run_id)
        run.status = BrowseExportRun.Status.FAILED
        run.error = str(exc)[:500]
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error", "completed_at"])
        return
    run.status = BrowseExportRun.Status.COMPLETE
    run.folder_name = folder_name
    run.document_count = count
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "folder_name", "document_count", "completed_at"])
    prune_old_browse_trees(run)


@shared_task(name="archive.tasks.reconcile_browse_exports")
def reconcile_browse_exports():
    stale_before = timezone.now() - timedelta(hours=7)
    BrowseExportRun.objects.filter(status=BrowseExportRun.Status.RUNNING, started_at__lt=stale_before).update(
        status=BrowseExportRun.Status.PENDING, started_at=None,
    )
    for run_id in BrowseExportRun.objects.filter(status=BrowseExportRun.Status.PENDING).values_list("id", flat=True)[:20]:
        try:
            build_browse_export.delay(str(run_id))
        except Exception:
            logger.exception("NAS browse export queue unavailable: %s", run_id)
            return


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
            job.version_files = []
            job.save(update_fields=["status", "completed_at", "title", "original_path", "archive_path", "original_sha256", "version_files"])
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


@shared_task(name="archive.tasks.poll_mail_account", time_limit=30 * 60)
def poll_mail_account(account_id):
    from .mail import poll_account

    return poll_account(account_id)


@shared_task(name="archive.tasks.poll_mail_accounts")
def poll_mail_accounts():
    from .models import MailAccount

    for account_id in MailAccount.objects.filter(enabled=True, rules__enabled=True).distinct().values_list("id", flat=True):
        poll_mail_account.delay(str(account_id))


def _note(document, body):
    from .models import DocumentNote

    DocumentNote.objects.create(document=document, author_id=document.owner_id, body=body)


def _split(document, pdf, ranges):
    """Create one document per page range, carrying over the source's filing. All or nothing."""
    from io import BytesIO

    from django.core.files.base import File
    from pypdf import PdfReader, PdfWriter

    from .ingestion import ingest_document
    from .models import DocumentEmail

    reader = PdfReader(pdf)
    stem = Path(document.original_name).stem[:80] or "scan"
    written = []
    try:
        with transaction.atomic():
            locked = Document.objects.select_for_update().get(pk=document.pk)
            if locked.trashed_at or locked.is_split_source:
                return False
            links = list(DocumentTag.objects.filter(document=locked).exclude(origin=DocumentTag.Origin.RULE))
            origin = DocumentEmail.objects.filter(document=locked).first()
            for number, (start, end) in enumerate(ranges, start=1):
                writer = PdfWriter()
                for index in range(start, end):
                    writer.add_page(reader.pages[index])
                data = BytesIO()
                writer.write(data)
                part = ingest_document(locked.owner, File(BytesIO(data.getvalue()), name=f"{stem}-{number}.pdf"),
                                       source=locked.source, title=f"{locked.title} ({number}/{len(ranges)})", queue=False)
                written.append(part.original_path)
                # Parts keep what an input rule or the owner already decided about the scan.
                part.split_parent = locked
                part.correspondent_id, part.correspondent_origin = locked.correspondent_id, locked.correspondent_origin
                part.document_type_id, part.document_type_origin = locked.document_type_id, locked.document_type_origin
                part.save(update_fields=["split_parent", "correspondent", "correspondent_origin", "document_type", "document_type_origin"])
                DocumentTag.objects.bulk_create([DocumentTag(document=part, tag_id=link.tag_id, origin=link.origin) for link in links], ignore_conflicts=True)
                if origin:
                    DocumentEmail.objects.create(document=part, account=origin.account, account_name=origin.account_name, sender=origin.sender,
                                                 subject=origin.subject, received_at=origin.received_at, message_id=origin.message_id)
                transaction.on_commit(lambda part_id=str(part.id): process_document.delay(part_id), robust=True)
            locked.is_split_source = True
            locked.save(update_fields=["is_split_source"])
    except Exception:  # noqa: BLE001 - a failed split leaves the scan whole and searchable
        for path in written:
            (Path(settings.MEDIA_ROOT) / path).unlink(missing_ok=True)
        logger.warning("Splitting document %s failed", document.id, exc_info=True)
        _note(document, "This scan has separator sheets, but Ripiano could not split it. It was kept as one document.")
        return False
    document.is_split_source = True
    return True


def apply_barcodes(document, original, pdf, work_dir):
    """Split at separator sheets, or give this document its ASN and tag barcodes. Never fails processing."""
    from django.db import IntegrityError

    from .barcodes import scan_image, scan_pdf, split_ranges
    from .models import Tag, TagOverride

    try:
        scan = scan_image(original) if document.original_mime.startswith("image/") else scan_pdf(pdf, work_dir)
    except Exception:  # noqa: BLE001 - barcodes are optional; OCR continues
        logger.warning("Barcode scan failed for document %s", document.id, exc_info=True)
        return
    # Only a document's first processing may split it: reprocessing must never hide a curated document.
    first_run = document.processed_at is None
    if (first_run and document.original_mime == "application/pdf" and document.split_parent_id is None
            and not document.is_split_source and scan.separators):
        if scan.truncated:
            _note(document, f"This scan has separator sheets, but only the first {scan.scanned} pages are checked, so it was kept as one document.")
        else:
            ranges = split_ranges(scan)
            if ranges and ranges != [(0, scan.pages)] and _split(document, pdf, ranges):
                return
    if document.is_split_source:
        return
    suppressed = set(TagOverride.objects.filter(document=document).values_list("tag_id", flat=True))
    for name in scan.tags:
        tag = Tag.objects.filter(owner_id=document.owner_id, name__iexact=name).order_by("created_at").first()
        if tag and tag.id not in suppressed:
            DocumentTag.objects.get_or_create(document=document, tag=tag, defaults={"origin": DocumentTag.Origin.SOURCE})
    if scan.asn and document.asn is None:
        try:
            with transaction.atomic():
                Document.objects.filter(pk=document.pk, asn__isnull=True).update(asn=scan.asn)
        except IntegrityError:
            _note(document, f"Barcode ASN {scan.asn} is already used by another document, so it was not assigned here.")
