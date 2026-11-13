"""Deterministic owner workflows: match conditions, apply actions once, and keep a visible run history.

Metadata actions run inside the caller's transaction. Webhooks and emails run afterwards on the
maintenance queue and only carry metadata, never OCR text (unless the owner attaches the file).
"""

import fnmatch
import logging
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .models import Document, DocumentNote, DocumentTag, TagOverride, Workflow, WorkflowRun

logger = logging.getLogger(__name__)
SCHEDULE_BATCH = 500


def matches(workflow, document):
    if workflow.filter_sources and document.source not in workflow.filter_sources:
        return False
    if workflow.filter_filename and not fnmatch.fnmatch(document.original_name.casefold(), workflow.filter_filename.casefold()):
        return False
    if workflow.filter_text:
        needle = workflow.filter_text.casefold()
        if needle not in document.title.casefold() and needle not in document.extracted_text.casefold():
            return False
    if workflow.filter_tag_id and not DocumentTag.objects.filter(document=document, tag_id=workflow.filter_tag_id).exists():
        return False
    if workflow.filter_correspondent_id and document.correspondent_id != workflow.filter_correspondent_id:
        return False
    if workflow.filter_document_type_id and document.document_type_id != workflow.filter_document_type_id:
        return False
    return True


def _apply(workflow, document, *, first_time=True):
    """Apply metadata actions; return a short description of what changed.

    Notes, webhooks, and emails happen only the first time a workflow applies to a document.
    """
    changes = []
    suppressed = set(TagOverride.objects.filter(document=document).values_list("tag_id", flat=True))
    added = [tag for tag in workflow.add_tags.all() if tag.id not in suppressed]
    for tag in added:
        link, created = DocumentTag.objects.get_or_create(document=document, tag=tag, defaults={"origin": DocumentTag.Origin.SOURCE})
        if created:
            changes.append(f"added tag {tag.name}")
    removed = DocumentTag.objects.filter(document=document, tag__in=workflow.remove_tags.all()).exclude(origin=DocumentTag.Origin.MANUAL)
    for link in removed.select_related("tag"):
        changes.append(f"removed tag {link.tag.name}")
    removed.delete()
    fields = []
    # A sender or type the owner chose by hand is never overwritten by automation.
    if workflow.set_correspondent_id and document.correspondent_origin != Document.FilingOrigin.MANUAL and document.correspondent_id != workflow.set_correspondent_id:
        document.correspondent_id, document.correspondent_origin = workflow.set_correspondent_id, Document.FilingOrigin.SOURCE
        fields += ["correspondent", "correspondent_origin"]
        changes.append(f"set sender {workflow.set_correspondent.name}")
    if workflow.set_document_type_id and document.document_type_origin != Document.FilingOrigin.MANUAL and document.document_type_id != workflow.set_document_type_id:
        document.document_type_id, document.document_type_origin = workflow.set_document_type_id, Document.FilingOrigin.SOURCE
        fields += ["document_type", "document_type_origin"]
        changes.append(f"set type {workflow.set_document_type.name}")
    # Only start a follow-up; never reopen one the owner completed.
    if workflow.set_needs_action and document.action_status == Document.ActionStatus.NONE:
        document.action_status, document.action_completed_at = Document.ActionStatus.OPEN, None
        fields += ["action_status", "action_completed_at"]
        if workflow.action_note and not document.action_note:
            document.action_note = workflow.action_note
            fields.append("action_note")
        changes.append("marked as needing action")
    if fields:
        document.save(update_fields=fields)
    if workflow.add_note and first_time:
        DocumentNote.objects.create(document=document, author_id=document.owner_id, body=workflow.add_note)
        changes.append("added a note")
    if workflow.webhook_url and first_time:
        changes.append("queued webhook")
    if workflow.email_to and first_time:
        changes.append("queued email")
    return ", ".join(changes) or "conditions matched; nothing needed changing"


def run_workflow(workflow, document, trigger):
    """Run one workflow for one document. Returns the WorkflowRun, or None if it already ran or did not match."""
    from .tasks import send_workflow_notifications

    if not matches(workflow, document):
        return None
    try:
        with transaction.atomic():
            Document.objects.select_for_update().filter(pk=document.pk).first()
            # Side effects (note, webhook, email) happen on the first run only, whatever its delivery outcome.
            first_time = not WorkflowRun.objects.filter(workflow=workflow, document=document).exists()
            try:
                with transaction.atomic():
                    run = WorkflowRun.objects.create(workflow=workflow, document=document, trigger=trigger)
            except IntegrityError:
                return None  # Already ran for this document and trigger.
            run.detail = _apply(workflow, document, first_time=first_time)[:500]
            run.save(update_fields=["detail"])
            if first_time and (workflow.webhook_url or workflow.email_to):
                transaction.on_commit(lambda run_id=str(run.id): send_workflow_notifications.delay(run_id), robust=True)
    except Exception:
        logger.exception("Workflow %s failed for document %s", workflow.id, document.id)
        try:
            return WorkflowRun.objects.create(workflow=workflow, document=document, trigger=trigger, status=WorkflowRun.Status.FAILED,
                                              detail="This workflow could not be applied to this document. It will not retry automatically.")
        except IntegrityError:
            return None
    return run


def run_for_document(document, trigger):
    """Run the owner's enabled workflows for a trigger, in order. Workflow changes never trigger further workflows."""
    runs = []
    for workflow in Workflow.objects.filter(owner_id=document.owner_id, enabled=True, trigger=trigger).prefetch_related("add_tags", "remove_tags").select_related("set_correspondent", "set_document_type"):
        document.refresh_from_db()
        run = run_workflow(workflow, document, trigger)
        if run:
            runs.append(run)
    return runs


def run_scheduled():
    """Daily: apply scheduled workflows to documents whose chosen date is the configured number of days ago or older."""
    today = timezone.localdate()
    total = 0
    for workflow in Workflow.objects.filter(enabled=True, trigger=Workflow.Trigger.SCHEDULED).prefetch_related("add_tags", "remove_tags").select_related("set_correspondent", "set_document_type"):
        cutoff = today - timedelta(days=workflow.schedule_days)
        candidates = Document.objects.filter(owner_id=workflow.owner_id, trashed_at__isnull=True, is_split_source=False, status=Document.Status.READY)
        if workflow.schedule_field == Workflow.DateField.CREATED:
            candidates = candidates.filter(created_at__date__lte=cutoff)
        else:
            candidates = candidates.filter(**{f"{workflow.schedule_field}__lte": cutoff})
        # A new workflow applies to documents that become due after it was created, not the whole history.
        since = workflow.created_at.date() - timedelta(days=workflow.schedule_days) - timedelta(days=1)
        if workflow.schedule_field == Workflow.DateField.CREATED:
            candidates = candidates.filter(created_at__date__gte=since)
        else:
            candidates = candidates.filter(**{f"{workflow.schedule_field}__gte": since})
        done = WorkflowRun.objects.filter(workflow=workflow, trigger=Workflow.Trigger.SCHEDULED, document=OuterRef("pk"))
        candidates = candidates.filter(~Exists(done)).order_by("created_at", "id")
        applied, after = 0, None
        while applied < SCHEDULE_BATCH:
            page = candidates
            if after:
                page = page.filter(Q(created_at__gt=after[0]) | Q(created_at=after[0], id__gt=after[1]))
            batch = list(page[:200])
            if not batch:
                break
            for document in batch:
                if run_workflow(workflow, document, Workflow.Trigger.SCHEDULED):
                    applied += 1
            after = (batch[-1].created_at, batch[-1].id)
        total += applied
    return total


def notification_payload(run):
    document = run.document
    return {
        "event": f"document.{run.trigger}",
        "workflow": run.workflow.name,
        "document": {
            "id": str(document.id), "title": document.title, "original_name": document.original_name, "source": document.source,
            "created_at": document.created_at.isoformat(), "document_date": document.document_date.isoformat() if document.document_date else None,
            "asn": document.asn, "correspondent": document.correspondent.name if document.correspondent_id else None,
            "document_type": document.document_type.name if document.document_type_id else None,
            "tags": sorted(link.tag.name for link in document.tag_links.select_related("tag")),
            "url": f"{settings.PUBLIC_ORIGIN.rstrip('/')}/?document={document.id}",
        },
    }


def send_notifications(run):
    """Deliver the webhook and email for a run; always record the outcome on the run."""
    outcome, failed = [], False
    workflow = run.workflow
    try:
        payload = notification_payload(run)
    except Exception:  # noqa: BLE001
        logger.exception("Workflow payload failed for run %s", run.id)
        WorkflowRun.objects.filter(pk=run.pk).update(status=WorkflowRun.Status.FAILED, detail=f"{run.detail}; notification could not be prepared"[:500])
        return
    if workflow.webhook_url:
        try:
            outcome.append(post_webhook(workflow.webhook_url, payload))
        except WebhookError as exc:
            outcome.append(str(exc))
            failed = True
        except Exception:  # noqa: BLE001 - any delivery problem is reported, never crashes the worker
            logger.warning("Webhook failed for run %s", run.id, exc_info=True)
            outcome.append("webhook could not be delivered")
            failed = True
    if workflow.email_to:
        try:
            outcome.append(_send_email(run, workflow, payload))
        except WebhookError as exc:
            outcome.append(str(exc))
            failed = True
        except Exception:  # noqa: BLE001
            logger.warning("Workflow email failed for run %s", run.id, exc_info=True)
            outcome.append("email could not be sent")
            failed = True
    detail = "; ".join(filter(None, [run.detail.replace("queued webhook", "").replace("queued email", "").strip(", "), *outcome]))
    WorkflowRun.objects.filter(pk=run.pk).update(detail=detail[:500], status=WorkflowRun.Status.FAILED if failed else run.status)


class WebhookError(Exception):
    """A user-presentable delivery outcome."""


def _blocked(ip):
    import ipaddress

    candidates = [ip]
    if ip.version == 6:
        if ip.ipv4_mapped:
            candidates.append(ip.ipv4_mapped)
        if ip.sixtofour:
            candidates.append(ip.sixtofour)
        if ip in ipaddress.ip_network("64:ff9b::/96"):  # NAT64 embeds an IPv4 address
            candidates.append(ipaddress.ip_address(int(ip) & 0xFFFFFFFF))
    return any(not item.is_global for item in candidates)


def check_webhook_host(url):
    """Resolve the webhook host and return one permitted address to connect to.

    Private, loopback, and link-local targets are refused unless the operator allows them.
    """
    import ipaddress
    import socket
    from urllib.parse import urlsplit

    host = urlsplit(url).hostname or ""
    try:
        host.encode("idna")
        addresses = [item[4][0] for item in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)]
    except (UnicodeError, OSError) as exc:
        raise WebhookError("webhook address could not be found") from exc
    if not addresses:
        raise WebhookError("webhook address could not be found")
    ips = [ipaddress.ip_address(address.split("%")[0]) for address in addresses]
    if not settings.RIPIANO_WEBHOOK_ALLOW_PRIVATE and any(_blocked(ip) for ip in ips):
        raise WebhookError("webhook refused: it points to a private network address (see RIPIANO_WEBHOOK_ALLOW_PRIVATE)")
    return ips[0]


def post_webhook(url, payload, deadline_seconds=15):
    """POST JSON to the checked address only (no second DNS lookup), with a short timeout and a capped read."""
    import time
    from urllib.parse import urlsplit, urlunsplit

    import httpx

    ip = check_webhook_host(url)
    parts = urlsplit(url)
    literal = f"[{ip}]" if ip.version == 6 else str(ip)
    pinned = urlunsplit((parts.scheme, f"{literal}:{parts.port}" if parts.port else literal, parts.path or "/", parts.query, ""))
    host_header = parts.hostname + (f":{parts.port}" if parts.port else "")
    started = time.monotonic()
    with httpx.Client(timeout=httpx.Timeout(5, connect=5), follow_redirects=False, trust_env=False) as client:
        # TLS still verifies the certificate for the original host name (SNI), not for the IP.
        request = client.build_request("POST", pinned, json=payload, headers={"Host": host_header},
                                       extensions={"sni_hostname": parts.hostname})
        response = client.send(request, stream=True)
        try:
            received = 0
            for chunk in response.iter_raw():
                received += len(chunk)
                if received > 64 * 1024 or time.monotonic() - started > deadline_seconds:
                    break
        finally:
            response.close()
    if 200 <= response.status_code < 300:
        return "webhook delivered"
    raise WebhookError(f"webhook refused ({response.status_code})")


def _send_email(run, workflow, payload):
    from django.core.mail import EmailMessage

    recipients = [item.strip() for item in workflow.email_to.split(",") if item.strip()]
    if not settings.EMAIL_HOST:
        raise WebhookError("email not sent: no mail server is configured")
    document = run.document
    data = payload["document"]
    body = (f"{data['title']}\n\nWorkflow: {workflow.name}\nSender: {data['correspondent'] or '—'}\n"
            f"Type: {data['document_type'] or '—'}\nTags: {', '.join(data['tags']) or '—'}\n\nOpen in Ripiano: {data['url']}\n")
    subject = " ".join(f"[Ripiano] {document.title}".split())[:200]
    message = EmailMessage(subject=subject, body=body, to=recipients)
    note = ""
    if workflow.email_attach:
        path = Path(settings.MEDIA_ROOT) / document.original_path
        limit_mb = settings.RIPIANO_EMAIL_ATTACH_MAX_BYTES // (1024 * 1024)
        if document.original_size > settings.RIPIANO_EMAIL_ATTACH_MAX_BYTES:
            note = f" without the file (over {limit_mb} MB)"
        else:
            try:
                message.attach(Path(document.original_name).name, path.read_bytes(), document.original_mime)
            except OSError:
                note = " without the file (it could not be read)"
    message.send(fail_silently=False)
    return f"email sent to {len(recipients)} recipient{'s' if len(recipients) != 1 else ''}{note}"
