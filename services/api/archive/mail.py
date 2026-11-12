"""IMAP intake: fetch matching attachments into the shared ingestion pipeline.

Messages are read with BODY.PEEK, imported idempotently, and only then marked,
flagged, or moved. Ripiano never deletes mail. One unreadable message is
recorded as failed and never blocks the rest of a mailbox.
"""

import base64
import email
import fnmatch
import hashlib
import imaplib
import logging
import re
import ssl
from datetime import timedelta, timezone as dt_timezone
from email import policy
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from io import BytesIO
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.files.base import File
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Document, DocumentEmail, DocumentTag, MailAccount, MailRule, ProcessedMail
from .storage import SUPPORTED_EXTENSIONS as ATTACHMENT_EXTENSIONS, InvalidDocument

logger = logging.getLogger(__name__)
MESSAGES_PER_POLL = 200
TIMEOUT = 30
# Longer than the poll task's time limit, so a running poll never loses its claim.
CLAIM_MINUTES = 35


class MailError(Exception):
    """A user-presentable mailbox problem. Messages never include server output."""

    def __init__(self, message, code="mail"):
        super().__init__(message)
        self.code = code


def _fernet():
    configured = [key.strip() for key in settings.RIPIANO_MAIL_KEY.split(",") if key.strip()]
    if not configured:
        derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"ripiano-mail-secret").derive(settings.SECRET_KEY.encode())
        configured = [base64.urlsafe_b64encode(derived)]
    try:
        # The first key encrypts; older keys listed after it still decrypt.
        return MultiFernet([Fernet(key) for key in configured])
    except (ValueError, TypeError) as exc:
        raise MailError("RIPIANO_MAIL_KEY is not a valid key. Ask the server administrator to fix it.", "key") from exc


def encrypt_secret(value):
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt_secret(value, *, oauth=False):
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        if oauth:
            raise MailError("The saved sign-in can no longer be read. Remove the mailbox and connect it again.", "key") from exc
        raise MailError("The saved password can no longer be read. Edit the mailbox and enter it again.", "key") from exc


# IMAP folder names use "modified UTF-7" (RFC 3501 §5.1.3).
def encode_folder(name):
    result, pending = [], []

    def flush():
        if pending:
            encoded = base64.b64encode("".join(pending).encode("utf-16-be")).decode().rstrip("=").replace("/", ",")
            result.append(f"&{encoded}-")
            pending.clear()

    for char in name:
        if 0x20 <= ord(char) <= 0x7E:
            flush()
            result.append("&-" if char == "&" else char)
        else:
            pending.append(char)
    flush()
    return "".join(result)


def decode_folder(name):
    def replace(match):
        chunk = match.group(1)
        if not chunk:
            return "&"
        chunk = chunk.replace(",", "/")
        try:
            return base64.b64decode(chunk + "=" * (-len(chunk) % 4)).decode("utf-16-be")
        except (ValueError, UnicodeDecodeError):
            return match.group(0)

    return re.sub(r"&([A-Za-z0-9+,]*)-", replace, name)


def _quote(folder):
    folder = encode_folder(folder)
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


def connect(account):
    """Open an authenticated IMAP connection, translating failures to safe messages."""
    try:
        context = ssl.create_default_context()
        if account.security == MailAccount.Security.SSL:
            connection = imaplib.IMAP4_SSL(account.host, account.port, ssl_context=context, timeout=TIMEOUT)
        else:
            connection = imaplib.IMAP4(account.host, account.port, timeout=TIMEOUT)
            if account.security == MailAccount.Security.STARTTLS:
                connection.starttls(ssl_context=context)
    except (OSError, imaplib.IMAP4.error) as exc:
        # One message for every network failure, so the form cannot be used to map internal ports.
        raise MailError("Could not connect to the mail server. Check the host, port, and security setting.", "connect") from exc
    try:
        if account.auth == MailAccount.Auth.OAUTH:
            from .mail_oauth import access_token

            token = access_token(account)
            connection.authenticate("XOAUTH2", lambda _: f"user={account.username}\x01auth=Bearer {token}\x01\x01".encode())
        else:
            connection.login(account.username, decrypt_secret(account.secret))
    except imaplib.IMAP4.error as exc:
        _close(connection)
        raise MailError("The server rejected the sign-in. Check the username and password." if account.auth == MailAccount.Auth.PASSWORD
                        else "The server rejected the sign-in. Remove the mailbox and connect it again.", "auth") from exc
    except (OSError, MailError):
        _close(connection)
        raise
    return connection


def _close(connection):
    try:
        connection.logout()
    except Exception:  # noqa: BLE001 - logout is best effort
        pass


def list_folders(account):
    connection = connect(account)
    try:
        status, rows = connection.list()
        if status != "OK":
            raise MailError("The server did not list its folders.")
        folders = []
        for row in rows or []:
            if not isinstance(row, bytes):
                continue
            match = re.match(rb'\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$', row)
            if not match or b"\\Noselect" in match["flags"]:
                continue
            name = match["name"].decode(errors="replace").strip()
            if name.startswith('"') and name.endswith('"'):
                name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            folders.append(decode_folder(name))
        return sorted(set(folders), key=lambda item: (item.upper() != "INBOX", item.casefold()))
    except (imaplib.IMAP4.error, OSError) as exc:
        raise MailError("The server stopped responding while listing folders.") from exc
    finally:
        _close(connection)


def _header(message, name):
    """Read a header as plain text, tolerating malformed or undecodable values."""
    try:
        raw = str(message.get(name, failobj=""))
    except Exception:  # noqa: BLE001 - the structured parser rejects some real-world headers
        raw = next((str(value) for key, value in message.raw_items() if key.lower() == name.lower()), "")
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:  # noqa: BLE001 - malformed headers fall back to raw text
        return str(raw).strip()


def _sender(message):
    value = _header(message, "From")
    try:
        name, address = getaddresses([value])[0]
    except Exception:  # noqa: BLE001
        return value[:300]
    return (f"{name} <{address}>" if name and address else address or value)[:300]


def _contains(haystack, needle):
    return not needle or needle.casefold() in (haystack or "").casefold()


def _body_text(message):
    try:
        part = message.get_body(preferencelist=("plain", "html"))
        return part.get_content() if part else ""
    except Exception:  # noqa: BLE001 - an unreadable body just fails the text filter
        return ""


def _attachments(message, pattern, include_inline):
    """Every file in the message tree, including signed, alternative, and forwarded parts."""
    for part in message.walk():
        if part.is_multipart():
            continue
        try:
            name = part.get_filename()
        except Exception:  # noqa: BLE001
            continue
        if not name:
            continue
        name = Path(str(name).replace("\\", "/")).name
        if Path(name).suffix.lower() not in ATTACHMENT_EXTENSIONS:
            continue
        disposition = (part.get_content_disposition() or "").lower()
        if not include_inline and part.get_content_maintype() == "image" and (disposition == "inline" or (part["Content-ID"] and disposition != "attachment")):
            continue  # Logos and other pictures embedded in the email body.
        if pattern and not fnmatch.fnmatch(name.casefold(), pattern.casefold()):
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(payload, bytes) and payload:
            yield name, payload


def _received_at(message):
    try:
        value = parsedate_to_datetime(_header(message, "Date")) or None
    except (TypeError, ValueError, IndexError):
        return None
    if value and timezone.is_naive(value):
        value = value.replace(tzinfo=dt_timezone.utc)
    return value


def _apply_filing(document, rule, tags, origin_values):
    """Idempotently give a document its rule filing and email origin (also repairs partial imports)."""
    updates = []
    if rule.correspondent_id and document.correspondent_origin == Document.FilingOrigin.NONE:
        document.correspondent_id, document.correspondent_origin = rule.correspondent_id, Document.FilingOrigin.SOURCE
        updates += ["correspondent", "correspondent_origin"]
    if rule.document_type_id and document.document_type_origin == Document.FilingOrigin.NONE:
        document.document_type_id, document.document_type_origin = rule.document_type_id, Document.FilingOrigin.SOURCE
        updates += ["document_type", "document_type_origin"]
    if updates:
        document.save(update_fields=updates)
    for tag in tags:
        link, created = DocumentTag.objects.get_or_create(document=document, tag=tag, defaults={"origin": DocumentTag.Origin.SOURCE})
        if not created and link.origin == DocumentTag.Origin.RULE:
            link.origin = DocumentTag.Origin.SOURCE  # A phrase rule must not later remove an email rule's tag.
            link.save(update_fields=["origin"])
    DocumentEmail.objects.get_or_create(document=document, defaults=origin_values)


def import_message(rule, raw, *, uid_validity, uid, folder):
    """Import one fetched message for a rule. Returns the number of new documents."""
    from .ingestion import ingest_document
    from .tasks import process_document

    message = email.message_from_bytes(raw, policy=policy.default)
    sender = _sender(message)
    subject = _header(message, "Subject")[:300]
    message_id = _header(message, "Message-ID")[:300]
    record = {"rule": rule, "folder": folder, "uid_validity": uid_validity, "uid": uid, "message_id": message_id, "subject": subject, "sender": sender}
    if not (_contains(_header(message, "From"), rule.filter_from) and _contains(subject, rule.filter_subject)
            and (not rule.filter_body or _contains(_body_text(message), rule.filter_body))):
        ProcessedMail.objects.create(**record, status=ProcessedMail.Status.NO_MATCH, detail="Did not match the rule filters")
        return 0
    attachments = []
    if rule.consume != MailRule.Consume.MESSAGE:
        attachments = list(_attachments(message, rule.filter_attachment, rule.include_inline))
    items = [(name, payload, False) for name, payload in attachments]
    if rule.consume != MailRule.Consume.ATTACHMENTS:
        stem = re.sub(r"[^\w\- ]+", "", subject).strip()[:80] or "email"
        items.insert(0, (f"{stem}.eml", raw, True))
    if not items:
        ProcessedMail.objects.create(**record, status=ProcessedMail.Status.NO_MATCH, detail="No PDF, image, email, or Office attachment")
        return 0
    # The same message seen through another mailbox, folder, or rule imports only once per owner.
    identity = message_id or f"{rule.account_id}:{folder}:{uid_validity}:{uid}"
    tags = list(rule.tags.all())
    origin_values = {"account": rule.account, "account_name": rule.account.name, "sender": sender, "subject": subject,
                     "received_at": _received_at(message), "message_id": message_id}
    created, skipped = 0, []
    for name, payload, whole_message in items:
        digest = hashlib.sha256(payload).hexdigest()
        source_ref = hashlib.sha256(f"{rule.owner_id}\0{identity}\0{digest}".encode()).hexdigest()
        existing = Document.objects.filter(owner_id=rule.owner_id, source=Document.Source.EMAIL, source_ref=source_ref).first()
        if existing:
            with transaction.atomic():
                _apply_filing(existing, rule, tags, origin_values)
            continue
        title = subject if rule.title_from == MailRule.Title.SUBJECT and subject else Path(name).stem
        if whole_message:
            title = subject or "Email"
        elif rule.title_from == MailRule.Title.SUBJECT and subject and len(items) > 1:
            title = f"{subject} – {Path(name).stem}"
        document = None
        try:
            with transaction.atomic():
                document = ingest_document(rule.owner, File(BytesIO(payload), name=name), source=Document.Source.EMAIL,
                                           source_ref=source_ref, title=title[:300], queue=False)
                _apply_filing(document, rule, tags, origin_values)
                # OCR starts only once the document and its filing are committed together.
                transaction.on_commit(lambda document_id=str(document.id): process_document.delay(document_id), robust=True)
            created += 1
        except InvalidDocument as exc:
            skipped.append(f"{name}: {exc}")
        except IntegrityError:
            if document is not None:
                (Path(settings.MEDIA_ROOT) / document.original_path).unlink(missing_ok=True)
            continue  # Another poll imported the same attachment first.
        except Exception:
            if document is not None:
                (Path(settings.MEDIA_ROOT) / document.original_path).unlink(missing_ok=True)
            raise
    status = ProcessedMail.Status.IMPORTED if created or not skipped else ProcessedMail.Status.SKIPPED
    ProcessedMail.objects.create(**record, status=status, documents=created, detail="; ".join(skipped)[:300])
    return created


def _after(connection, rule, uid, capabilities):
    uid = str(uid)
    if rule.after == MailRule.After.MARK_READ:
        status, _ = connection.uid("STORE", uid, "+FLAGS", "(\\Seen)")
    elif rule.after == MailRule.After.FLAG:
        status, _ = connection.uid("STORE", uid, "+FLAGS", "(\\Flagged)")
    elif rule.after == MailRule.After.MOVE and rule.move_to:
        if "MOVE" in capabilities:
            status, _ = connection.uid("MOVE", uid, _quote(rule.move_to))
        else:
            status, _ = connection.uid("COPY", uid, _quote(rule.move_to))
            if status == "OK":
                connection.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                if "UIDPLUS" in capabilities:
                    connection.uid("EXPUNGE", uid)
    else:
        return True
    return status == "OK"


def _uid_validity(connection):
    values = connection.untagged_responses.get("UIDVALIDITY") or []
    try:
        return int(values[-1])
    except (IndexError, TypeError, ValueError):
        return 0


def run_rule(connection, rule, capabilities):
    """Process up to MESSAGES_PER_POLL unhandled messages, oldest first. Returns (imported, problem)."""
    status, _ = connection.select(_quote(rule.folder))
    if status != "OK":
        raise MailError(f"Folder “{rule.folder}” was not found.")
    uid_validity = _uid_validity(connection)
    since = (timezone.now() - timedelta(days=rule.max_age_days)).strftime("%d-%b-%Y")
    criteria = ["SINCE", since]
    if rule.after == MailRule.After.MARK_READ:
        criteria.append("UNSEEN")
    status, data = connection.uid("SEARCH", None, *criteria)
    if status != "OK":
        raise MailError("The server could not search this folder.")
    uids = sorted(int(value) for value in (data[0] or b"").split())
    done = set(ProcessedMail.objects.filter(rule=rule, folder=rule.folder, uid_validity=uid_validity, uid__in=uids).values_list("uid", flat=True))
    pending = [uid for uid in uids if uid not in done][:MESSAGES_PER_POLL]
    imported, problem = 0, ""
    limit = settings.RIPIANO_MAX_UPLOAD_BYTES * 2
    for uid in pending:
        base = {"rule": rule, "folder": rule.folder, "uid_validity": uid_validity, "uid": uid}
        status, sized = connection.uid("FETCH", str(uid), "(RFC822.SIZE)")
        size_match = re.search(rb"RFC822\.SIZE (\d+)", b" ".join(item if isinstance(item, bytes) else b" ".join(item) for item in sized or [] if item))
        if status != "OK" or not size_match:
            continue
        if int(size_match[1]) > limit:
            ProcessedMail.objects.get_or_create(**base, defaults={"status": ProcessedMail.Status.SKIPPED, "detail": "Message is larger than the upload limit"})
            continue
        status, fetched = connection.uid("FETCH", str(uid), "(BODY.PEEK[])")
        raw = next((item[1] for item in fetched or [] if isinstance(item, tuple) and len(item) == 2), None)
        if status != "OK" or raw is None:
            continue
        try:
            imported += import_message(rule, raw, uid_validity=uid_validity, uid=uid, folder=rule.folder)
        except IntegrityError:
            continue  # Already recorded by a concurrent poll.
        except OSError:
            logger.exception("Mail rule %s could not store message uid %s", rule.id, uid)
            raise MailError("Ripiano could not save an attachment. Check free space on the NAS.", "storage")
        except Exception:
            logger.exception("Mail rule %s could not read message uid %s", rule.id, uid)
            ProcessedMail.objects.get_or_create(**base, defaults={"status": ProcessedMail.Status.FAILED, "detail": "Ripiano could not read this message"})
            problem = "Some messages could not be read. See Recent mail."
            continue
        if ProcessedMail.objects.filter(**base, status=ProcessedMail.Status.IMPORTED).exists():
            try:
                if not _after(connection, rule, uid, capabilities):
                    problem = f"Imported mail could not be {'moved' if rule.after == MailRule.After.MOVE else 'updated'}. Check the folder name."
            except (imaplib.IMAP4.error, OSError):
                logger.warning("Mail rule %s could not update message %s after import", rule.id, uid)
                problem = "Imported mail could not be updated on the server."
    return imported, problem


def _claim(account_id):
    now = timezone.now()
    until = now + timedelta(minutes=CLAIM_MINUTES)
    claimed = MailAccount.objects.filter(pk=account_id, enabled=True).filter(Q(polling_until__isnull=True) | Q(polling_until__lt=now)).update(polling_until=until)
    return until if claimed == 1 else None


def poll_account(account_id):
    """Run every enabled rule for one account. Returns imported document count, or None if busy."""
    claim = _claim(account_id)
    if claim is None:
        return None
    imported, error = 0, ""
    try:
        account = MailAccount.objects.get(pk=account_id)
        connection = connect(account)
        try:
            capabilities = {item.upper() for item in getattr(connection, "capabilities", ())}
            for rule in account.rules.filter(enabled=True).select_related("account", "owner").prefetch_related("tags"):
                try:
                    count, problem = run_rule(connection, rule, capabilities)
                    imported += count
                    error = error or (f"{rule.name}: {problem}" if problem else "")
                except MailError as exc:
                    error = error or f"{rule.name}: {exc}"
                    if exc.code == "storage":
                        break
        finally:
            _close(connection)
    except MailError as exc:
        error = str(exc)
    except (imaplib.IMAP4.error, OSError):
        logger.exception("Mail account %s failed during polling", account_id)
        error = "The mail server stopped responding. Ripiano will try again."
    except Exception:
        logger.exception("Mail account %s failed unexpectedly", account_id)
        error = "Checking this mailbox failed. Ripiano will try again."
    finally:
        # Release only our own claim, even after an unexpected error.
        MailAccount.objects.filter(pk=account_id, polling_until=claim).update(
            polling_until=None, last_checked_at=timezone.now(), last_error=error[:300], last_imported=imported,
        )
    return imported
