"""Owner-scoped mailbox and mail-rule management."""

import json
import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.utils.http import urlencode
from django.views.decorators.http import require_http_methods

from . import mail_oauth
from .mail import MailError, encrypt_secret, list_folders
from .models import Correspondent, DocumentType, MailAccount, MailRule, ProcessedMail, Tag

HOST = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,253}[A-Za-z0-9])?$")
FOLDER = re.compile(r"^[\x20-\x7e]{1,200}$")


def _signed_in(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def _body(request):
    try:
        value = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _text(body, key, limit, *, required=False, default=""):
    value = body.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be text")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} is required")
    if len(value) > limit:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} is too long")
    return value


def _account_json(account):
    return {
        "id": str(account.id), "name": account.name, "host": account.host, "port": account.port,
        "security": account.security, "username": account.username, "auth": account.auth,
        "oauth_provider": account.oauth_provider, "has_secret": bool(account.secret), "enabled": account.enabled,
        "checking": account.polling_until is not None,
        "last_checked_at": account.last_checked_at.isoformat() if account.last_checked_at else None,
        "last_error": account.last_error, "last_imported": account.last_imported,
    }


def _rule_json(rule):
    return {
        "id": str(rule.id), "account_id": str(rule.account_id), "name": rule.name, "order": rule.order,
        "enabled": rule.enabled, "folder": rule.folder, "filter_from": rule.filter_from,
        "filter_subject": rule.filter_subject, "filter_body": rule.filter_body,
        "filter_attachment": rule.filter_attachment, "include_inline": rule.include_inline, "consume": rule.consume, "max_age_days": rule.max_age_days,
        "after": rule.after, "move_to": rule.move_to, "title_from": rule.title_from,
        "tag_ids": [str(tag.id) for tag in rule.tags.all()],
        "correspondent_id": str(rule.correspondent_id) if rule.correspondent_id else None,
        "document_type_id": str(rule.document_type_id) if rule.document_type_id else None,
    }


def _processed_json(item):
    return {
        "id": item.id, "rule": item.rule.name, "account": item.rule.account.name, "subject": item.subject,
        "sender": item.sender, "status": item.status, "detail": item.detail, "documents": item.documents,
        "processed_at": item.processed_at.isoformat(),
    }


def _apply_account(account, body, *, creating):
    account.name = _text(body, "name", 100, required=True, default=account.name)
    if account.auth == MailAccount.Auth.PASSWORD:
        host = _text(body, "host", 255, required=True, default=account.host)
        if not HOST.match(host):
            raise ValueError("Enter a host name such as imap.example.com")
        port = body.get("port", account.port)
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        security = body.get("security", account.security)
        if security not in MailAccount.Security.values:
            raise ValueError("Choose a connection security option")
        account.host, account.port, account.security = host, port, security
        account.username = _text(body, "username", 255, required=True, default=account.username)
        password = body.get("password", "")
        if not isinstance(password, str) or len(password) > 500:
            raise ValueError("Password is too long")
        if password:
            account.secret = encrypt_secret(password)
        elif creating:
            raise ValueError("Password is required")
    enabled = body.get("enabled", account.enabled)
    if not isinstance(enabled, bool):
        raise ValueError("Enabled must be true or false")
    account.enabled = enabled


@require_http_methods(["GET"])
def mail_overview(request):
    denied = _signed_in(request)
    if denied:
        return denied
    accounts = MailAccount.objects.filter(owner=request.user)
    rules = MailRule.objects.filter(owner=request.user).prefetch_related("tags")
    recent = ProcessedMail.objects.filter(rule__owner=request.user).select_related("rule__account")[:20]
    return JsonResponse({
        "accounts": [_account_json(item) for item in accounts],
        "rules": [_rule_json(item) for item in rules],
        "recent": [_processed_json(item) for item in recent],
        "oauth_providers": mail_oauth.enabled_providers(),
    })


@require_http_methods(["POST"])
def mail_accounts(request):
    denied = _signed_in(request)
    if denied:
        return denied
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    account = MailAccount(owner=request.user)
    try:
        _apply_account(account, body, creating=True)
        account.save()
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "You already have a mailbox with this name"}, status=409)
    return JsonResponse(_account_json(account), status=201)


@require_http_methods(["PATCH", "DELETE"])
def mail_account_detail(request, account_id):
    denied = _signed_in(request)
    if denied:
        return denied
    account = MailAccount.objects.filter(pk=account_id, owner=request.user).first()
    if account is None:
        return JsonResponse({"error": "Mailbox not found"}, status=404)
    if request.method == "DELETE":
        account.delete()
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    secret = account.secret
    try:
        _apply_account(account, body, creating=False)
        fields = ["name", "host", "port", "security", "username", "enabled"]
        if account.secret != secret:
            fields += ["secret", "last_error"]
            account.last_error = ""
        # Never write back a stale secret: an OAuth poll may have rotated it meanwhile.
        account.save(update_fields=fields)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "You already have a mailbox with this name"}, status=409)
    return JsonResponse(_account_json(account))


@require_http_methods(["POST"])
def mail_account_test(request, account_id):
    denied = _signed_in(request)
    if denied:
        return denied
    account = MailAccount.objects.filter(pk=account_id, owner=request.user).first()
    if account is None:
        return JsonResponse({"error": "Mailbox not found"}, status=404)
    try:
        folders = list_folders(account)
    except MailError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=200)
    return JsonResponse({"ok": True, "folders": folders[:500]})


@require_http_methods(["POST"])
def mail_account_check(request, account_id):
    denied = _signed_in(request)
    if denied:
        return denied
    from .tasks import poll_mail_account

    account = MailAccount.objects.filter(pk=account_id, owner=request.user).first()
    if account is None:
        return JsonResponse({"error": "Mailbox not found"}, status=404)
    if not account.enabled:
        return JsonResponse({"error": "Turn the mailbox on first"}, status=409)
    poll_mail_account.delay(str(account.id))
    return JsonResponse({"queued": True}, status=202)


def _owned(model, owner, value, label):
    if value in (None, ""):
        return None
    try:
        item = model.objects.filter(pk=value, owner=owner).first() if isinstance(value, str) else None
    except ValidationError:
        item = None
    if item is None:
        raise ValueError(f"{label} not found")
    return item


def _apply_rule(rule, body, owner):
    if "account_id" in body or rule.account_id is None:
        rule.account = _owned(MailAccount, owner, body.get("account_id"), "Mailbox")
        if rule.account is None:
            raise ValueError("Choose a mailbox")
    rule.name = _text(body, "name", 100, required=True, default=rule.name)
    rule.folder = _text(body, "folder", 200, required=True, default=rule.folder)
    if not FOLDER.match(rule.folder):
        raise ValueError("Folder names must use plain letters, numbers, and punctuation")
    for key in ("filter_from", "filter_subject", "filter_body", "filter_attachment"):
        setattr(rule, key, _text(body, key, 200, default=getattr(rule, key)))
    age = body.get("max_age_days", rule.max_age_days)
    if not isinstance(age, int) or isinstance(age, bool) or not 1 <= age <= 3650:
        raise ValueError("Maximum age must be 1–3650 days")
    rule.max_age_days = age
    after = body.get("after", rule.after)
    if after not in MailRule.After.values:
        raise ValueError("Choose what happens to imported messages")
    rule.after = after
    rule.move_to = _text(body, "move_to", 200, default=rule.move_to)
    if after == MailRule.After.MOVE and not FOLDER.match(rule.move_to or ""):
        raise ValueError("Choose the folder to move imported messages to")
    consume = body.get("consume", rule.consume)
    if consume not in MailRule.Consume.values:
        raise ValueError("Choose what to import from each email")
    rule.consume = consume
    title_from = body.get("title_from", rule.title_from)
    if title_from not in MailRule.Title.values:
        raise ValueError("Choose where the document title comes from")
    rule.title_from = title_from
    for key in ("enabled", "include_inline"):
        value = body.get(key, getattr(rule, key))
        if not isinstance(value, bool):
            raise ValueError(f"{key.replace('_', ' ').capitalize()} must be true or false")
        setattr(rule, key, value)
    order = body.get("order", rule.order)
    if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= 10000:
        raise ValueError("Order must be 0–10000")
    rule.order = order
    if "correspondent_id" in body:
        rule.correspondent = _owned(Correspondent, owner, body["correspondent_id"], "Sender")
    if "document_type_id" in body:
        rule.document_type = _owned(DocumentType, owner, body["document_type_id"], "Document type")
    tags = None
    if "tag_ids" in body:
        ids = body["tag_ids"]
        if not isinstance(ids, list) or len(ids) > 50 or not all(isinstance(item, str) for item in ids):
            raise ValueError("Tags must be a list")
        try:
            tags = list(Tag.objects.filter(owner=owner, pk__in=ids))
        except ValidationError:
            tags = []
        if len(tags) != len(set(ids)):
            raise ValueError("Tag not found")
    return tags


@require_http_methods(["POST"])
def mail_rules(request):
    denied = _signed_in(request)
    if denied:
        return denied
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    rule = MailRule(owner=request.user)
    try:
        with transaction.atomic():
            tags = _apply_rule(rule, body, request.user)
            rule.save()
            if tags is not None:
                rule.tags.set(tags)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_rule_json(rule), status=201)


@require_http_methods(["PATCH", "DELETE"])
def mail_rule_detail(request, rule_id):
    denied = _signed_in(request)
    if denied:
        return denied
    rule = MailRule.objects.filter(pk=rule_id, owner=request.user).first()
    if rule is None:
        return JsonResponse({"error": "Rule not found"}, status=404)
    if request.method == "DELETE":
        rule.delete()
        return JsonResponse({"deleted": True})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    scope = (rule.account_id, rule.folder)
    filters = (rule.filter_from, rule.filter_subject, rule.filter_body, rule.filter_attachment, rule.include_inline, rule.consume, rule.max_age_days)
    try:
        with transaction.atomic():
            tags = _apply_rule(rule, body, request.user)
            rule.save()
            if tags is not None:
                rule.tags.set(tags)
            if (rule.account_id, rule.folder) != scope:
                # A different mailbox or folder has its own messages; start fresh.
                rule.processed.all().delete()
            elif (rule.filter_from, rule.filter_subject, rule.filter_body, rule.filter_attachment, rule.include_inline, rule.consume, rule.max_age_days) != filters:
                # Look again at messages the old filters passed over. Imports stay recorded.
                rule.processed.exclude(status=ProcessedMail.Status.IMPORTED).delete()
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_rule_json(rule))


@require_http_methods(["POST"])
def mail_oauth_start(request, provider):
    denied = _signed_in(request)
    if denied:
        return denied
    try:
        return JsonResponse({"url": mail_oauth.authorization_url(request.user, provider)})
    except MailError as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@require_http_methods(["GET"])
def mail_oauth_callback(request):
    def back(**params):
        return HttpResponseRedirect("/?" + urlencode({"view": "integrations", **params}))

    if not request.user.is_authenticated:
        return back(mail_error="signin")
    if request.GET.get("error"):
        return back(mail_error="cancelled")
    try:
        state = mail_oauth.read_state(request.GET.get("state", ""))
        if state["user"] != request.user.pk:
            raise MailError("This sign-in belongs to another account.", "other_user")
        address, refresh = mail_oauth.exchange_code(state["provider"], request.GET.get("code", ""))
    except MailError as exc:
        return back(mail_error=exc.code)
    provider = state["provider"]
    config = mail_oauth.PROVIDERS[provider]
    account = MailAccount.objects.filter(owner=request.user, auth=MailAccount.Auth.OAUTH, oauth_provider=provider, username__iexact=address).first()
    if account is None:
        account = MailAccount(owner=request.user, auth=MailAccount.Auth.OAUTH, oauth_provider=provider, username=address,
                              host=config["host"], port=993, security=MailAccount.Security.SSL)
        base = f"{config['label']} {address}"[:100]
        name, suffix = base, 2
        while MailAccount.objects.filter(owner=request.user, name__iexact=name).exists():
            name, suffix = f"{base[:95]} {suffix}", suffix + 1
        account.name = name
    account.secret = encrypt_secret(refresh)
    account.last_error = ""
    account.save()
    return back(mail_connected=account.name)
