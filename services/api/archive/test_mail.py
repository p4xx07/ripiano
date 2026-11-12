import imaplib
from urllib.parse import parse_qs, urlsplit
from email.message import EmailMessage
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from PIL import Image

from archive import mail
from archive.classification import apply_rules
from archive.models import Correspondent, Document, DocumentEmail, DocumentTag, MailAccount, MailRule, ProcessedMail, Tag


def pdf_bytes(color="white"):
    output = BytesIO()
    Image.new("RGB", (16, 16), color).save(output, format="PDF")
    return output.getvalue()


def message(sender="Acme Energy <billing@acme.test>", subject="Your May bill", attachments=(("bill.pdf", pdf_bytes()),), body="Invoice attached", message_id=None):
    item = EmailMessage()
    item["From"] = sender
    item["To"] = "me@example.test"
    item["Subject"] = subject
    item["Date"] = "Tue, 10 Nov 2026 09:30:00 +0100"
    if message_id:
        item["Message-ID"] = message_id
    item.set_content(body)
    for name, payload in attachments:
        maintype, subtype = ("application", "pdf") if name.endswith(".pdf") else ("application", "octet-stream")
        item.add_attachment(payload, maintype=maintype, subtype=subtype, filename=name)
    return item.as_bytes()


class FakeMailbox:
    """A small in-memory IMAP server keyed by folder, recording flag and move commands."""

    def __init__(self, folders, *, password="app-password", capabilities=("IMAP4REV1", "MOVE")):
        self.folders = folders
        self.flags = {}
        self.password = password
        self.capabilities = capabilities
        self.commands = []
        self.selected = None
        self.untagged_responses = {}

    def __call__(self, *args, **kwargs):
        return self

    def login(self, username, password):
        if password != self.password:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED secret server detail")
        return "OK", [b"Logged in"]

    def authenticate(self, mechanism, callback):
        self.commands.append(("AUTH", mechanism, callback(b"")))
        return "OK", [b"Logged in"]

    def logout(self):
        return "BYE", []

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\Noselect) "/" "[Gmail]"', b'(\\HasNoChildren) "/" "Archive/Bills"']

    def select(self, folder):
        name = folder.strip('"')
        if name not in self.folders:
            return "NO", [b"missing"]
        self.selected = name
        self.untagged_responses = {"UIDVALIDITY": [b"7"]}
        return "OK", [str(len(self.folders[name])).encode()]

    def uid(self, command, *args):
        command = command.upper()
        messages = self.folders[self.selected]
        if command == "SEARCH":
            unseen = "UNSEEN" in args
            uids = [uid for uid in messages if not (unseen and "\\Seen" in self.flags.get(uid, set()))]
            return "OK", [" ".join(str(uid) for uid in uids).encode()]
        uid = int(args[0])
        if command == "FETCH" and "RFC822.SIZE" in args[1]:
            return "OK", [f"1 (UID {uid} RFC822.SIZE {len(messages[uid])})".encode()]
        if command == "FETCH":
            return "OK", [(f"1 (UID {uid} BODY[] {{{len(messages[uid])}}}".encode(), messages[uid]), b")"]
        self.commands.append((command, *args))
        if command == "STORE":
            self.flags.setdefault(uid, set()).add(args[2].strip("()"))
        return "OK", []


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user("owner", password="secure-password-1")


def account_for(owner, **values):
    return MailAccount.objects.create(owner=owner, name="Home", host="imap.example.test", port=993, username="me@example.test", secret=mail.encrypt_secret("app-password"), **values)


def poll(fake, account, tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path), patch("imaplib.IMAP4_SSL", fake), patch("archive.ingestion.process_document.delay"):
        return mail.poll_account(account.id)


@pytest.mark.django_db
def test_matching_attachments_import_once_with_rule_filing_and_mark_read(owner, tmp_path):
    account = account_for(owner)
    tag = Tag.objects.create(owner=owner, name="Utilities")
    sender = Correspondent.objects.create(owner=owner, name="Acme Energy")
    rule = MailRule.objects.create(owner=owner, account=account, name="Bills", filter_from="acme.test", correspondent=sender)
    rule.tags.add(tag)
    fake = FakeMailbox({"INBOX": {
        1: message(message_id="<bill-1@acme.test>"),
        2: message(sender="Friend <friend@example.test>", subject="Holiday", attachments=(("photo.pdf", pdf_bytes("red")),)),
        3: message(subject="Two files", attachments=(("a.pdf", pdf_bytes("blue")), ("b.pdf", pdf_bytes("green")), ("notes.txt", b"plain"))),
    }})

    assert poll(fake, account, tmp_path) == 3
    documents = Document.objects.filter(owner=owner, source=Document.Source.EMAIL).order_by("title")
    assert [item.title for item in documents] == ["Two files – a", "Two files – b", "Your May bill"]
    bill = documents.get(title="Your May bill")
    assert bill.correspondent == sender and bill.correspondent_origin == Document.FilingOrigin.SOURCE
    assert DocumentTag.objects.get(document=bill).origin == DocumentTag.Origin.SOURCE
    origin = DocumentEmail.objects.get(document=bill)
    assert (origin.account_name, origin.sender, origin.subject) == ("Home", "Acme Energy <billing@acme.test>", "Your May bill")
    assert fake.flags == {1: {"\\Seen"}, 3: {"\\Seen"}}
    assert ProcessedMail.objects.get(uid=2).status == ProcessedMail.Status.NO_MATCH

    fake.flags.clear()  # Even if the server forgets the read flag, nothing is imported twice.
    assert poll(fake, account, tmp_path) == 0
    assert Document.objects.filter(owner=owner, source=Document.Source.EMAIL).count() == 3
    account.refresh_from_db()
    assert account.last_error == "" and account.polling_until is None and account.last_checked_at


@pytest.mark.django_db
def test_rule_filing_survives_phrase_rules_and_moves_or_copies_mail(owner, tmp_path):
    account = account_for(owner)
    tag = Tag.objects.create(owner=owner, name="Mail")
    rule = MailRule.objects.create(owner=owner, account=account, name="Archive", after=MailRule.After.MOVE, move_to="Archive/Bills", title_from=MailRule.Title.FILENAME)
    rule.tags.add(tag)
    fake = FakeMailbox({"INBOX": {5: message()}, "Archive/Bills": {}})
    assert poll(fake, account, tmp_path) == 1
    assert ("MOVE", "5", '"Archive/Bills"') in fake.commands
    document = Document.objects.get(owner=owner, source=Document.Source.EMAIL)
    assert document.title == "bill"
    apply_rules(document)
    assert DocumentTag.objects.filter(document=document, tag=tag, origin=DocumentTag.Origin.SOURCE).exists()

    fallback = FakeMailbox({"INBOX": {9: message(subject="Other", attachments=(("other.pdf", pdf_bytes("black")),))}, "Archive/Bills": {}}, capabilities=("IMAP4REV1",))
    assert poll(fallback, account, tmp_path) == 1
    assert ("COPY", "9", '"Archive/Bills"') in fallback.commands
    assert fallback.flags[9] == {"\\Deleted"}


@pytest.mark.django_db
def test_failed_sign_in_reports_a_safe_message_and_busy_accounts_are_skipped(owner, tmp_path):
    account = account_for(owner)
    MailRule.objects.create(owner=owner, account=account, name="All")
    fake = FakeMailbox({"INBOX": {1: message()}}, password="different")
    assert poll(fake, account, tmp_path) == 0
    account.refresh_from_db()
    assert account.last_error == "The server rejected the sign-in. Check the username and password."
    assert "secret server detail" not in account.last_error

    MailAccount.objects.filter(pk=account.pk).update(polling_until="2999-01-01T00:00:00Z")
    assert poll(FakeMailbox({"INBOX": {1: message()}}), account, tmp_path) is None
    assert not Document.objects.exists()


@pytest.mark.django_db
def test_mail_api_keeps_secrets_private_and_owner_scoped(owner, tmp_path):
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    foreign_tag = Tag.objects.create(owner=other, name="Theirs")
    client = Client()
    client.force_login(owner)
    payload = {"name": "Home", "host": "imap.example.test", "port": 993, "security": "ssl", "username": "me@example.test"}
    assert client.post("/api/mail/accounts", payload, content_type="application/json").json()["error"] == "Password is required"
    assert client.post("/api/mail/accounts", {**payload, "host": "bad host!", "password": "x"}, content_type="application/json").status_code == 400
    created = client.post("/api/mail/accounts", {**payload, "password": "app-password"}, content_type="application/json")
    assert created.status_code == 201
    body = created.json()
    assert "password" not in body and "secret" not in body and body["has_secret"] is True
    stored = MailAccount.objects.get(pk=body["id"])
    assert "app-password" not in stored.secret and mail.decrypt_secret(stored.secret) == "app-password"
    assert client.patch(f"/api/mail/accounts/{body['id']}", {"name": "Family"}, content_type="application/json").status_code == 200
    assert mail.decrypt_secret(MailAccount.objects.get(pk=body["id"]).secret) == "app-password"

    rule_payload = {"account_id": body["id"], "name": "Bills", "folder": "INBOX", "after": "move", "move_to": ""}
    assert client.post("/api/mail/rules", rule_payload, content_type="application/json").status_code == 400
    assert client.post("/api/mail/rules", {**rule_payload, "after": "mark_read", "tag_ids": [str(foreign_tag.id)]}, content_type="application/json").json()["error"] == "Tag not found"
    assert client.post("/api/mail/rules", {**rule_payload, "after": "mark_read", "correspondent_id": "not-a-uuid"}, content_type="application/json").json()["error"] == "Sender not found"
    rule = client.post("/api/mail/rules", {**rule_payload, "after": "mark_read"}, content_type="application/json")
    assert rule.status_code == 201

    with patch("imaplib.IMAP4_SSL", FakeMailbox({"INBOX": {}})):
        tested = client.post(f"/api/mail/accounts/{body['id']}/test").json()
    assert tested == {"ok": True, "folders": ["INBOX", "Archive/Bills"]}
    with patch("archive.tasks.poll_mail_account.delay") as queued:
        assert client.post(f"/api/mail/accounts/{body['id']}/check").status_code == 202
    queued.assert_called_once_with(body["id"])

    intruder = Client()
    intruder.force_login(other)
    assert intruder.get("/api/mail").json()["accounts"] == []
    assert intruder.patch(f"/api/mail/accounts/{body['id']}", {"name": "Mine"}, content_type="application/json").status_code == 404
    assert intruder.post(f"/api/mail/accounts/{body['id']}/test").status_code == 404
    assert intruder.delete(f"/api/mail/rules/{rule.json()['id']}").status_code == 404
    assert intruder.post("/api/mail/rules", {**rule_payload, "after": "mark_read"}, content_type="application/json").json()["error"] == "Mailbox not found"


@pytest.mark.django_db
@override_settings(RIPIANO_MAIL_OAUTH={"gmail": ("client-id", "client-secret"), "outlook": ("", "")}, PUBLIC_ORIGIN="https://ripiano.test")
def test_oauth_connects_a_mailbox_for_the_signed_in_owner_only(owner, tmp_path):
    from archive import mail_oauth

    other = get_user_model().objects.create_user("other", password="secure-password-2")
    client = Client()
    client.force_login(owner)
    overview = client.get("/api/mail").json()
    assert overview["oauth_providers"] == [{"id": "gmail", "label": "Gmail"}]
    assert client.post("/api/mail/oauth/outlook/start").status_code == 400
    url = client.post("/api/mail/oauth/gmail/start").json()["url"]
    assert url.startswith("https://accounts.google.com/") and "redirect_uri=https%3A%2F%2Fripiano.test%2Fapi%2Fmail%2Foauth%2Fcallback" in url
    state = parse_qs(urlsplit(url).query)["state"][0]

    with patch.object(mail_oauth, "exchange_code", return_value=("me@gmail.test", "refresh-1")):
        stolen = Client()
        stolen.force_login(other)
        assert "mail_error=other_user" in stolen.get("/api/mail/oauth/callback", {"state": state, "code": "abc"})["Location"]
        response = client.get("/api/mail/oauth/callback", {"state": state, "code": "abc"})
    assert "mail_connected" in response["Location"]
    account = MailAccount.objects.get(owner=owner)
    assert (account.auth, account.host, account.username) == ("oauth", "imap.gmail.com", "me@gmail.test")
    assert mail.decrypt_secret(account.secret) == "refresh-1"
    assert not MailAccount.objects.filter(owner=other).exists()
    assert "mail_error=expired" in client.get("/api/mail/oauth/callback", {"state": "tampered", "code": "abc"})["Location"]

    class Response:
        status_code = 200

        def json(self):
            return {"access_token": "access-1", "refresh_token": "refresh-2"}

    MailRule.objects.create(owner=owner, account=account, name="All")
    fake = FakeMailbox({"INBOX": {}})
    with patch("httpx.post", return_value=Response()):
        assert poll(fake, account, tmp_path) == 0
    assert fake.commands[0] == ("AUTH", "XOAUTH2", b"user=me@gmail.test\x01auth=Bearer access-1\x01\x01")
    account.refresh_from_db()
    assert mail.decrypt_secret(account.secret) == "refresh-2"


def nested_messages():
    """Real-world layouts where the PDF is not a top-level attachment."""
    from email.mime.application import MIMEApplication
    from email.mime.image import MIMEImage
    from email.mime.message import MIMEMessage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    def pdf(name, color):
        part = MIMEApplication(pdf_bytes(color), "pdf")
        part.add_header("Content-Disposition", "attachment", filename=name)
        return part

    signed = MIMEMultipart("signed", protocol="application/pkcs7-signature")
    inner = MIMEMultipart("mixed")
    inner.attach(MIMEText("Fattura allegata"))
    inner.attach(pdf("fattura.pdf", "red"))
    signed.attach(inner)
    signature = MIMEApplication(b"signature", "pkcs7-signature")
    signature.add_header("Content-Disposition", "attachment", filename="smime.p7s")
    signed.attach(signature)

    apple = MIMEMultipart("alternative")
    apple.attach(MIMEText("See attached"))
    related = MIMEMultipart("mixed")
    related.attach(MIMEText("<p>See attached</p>", "html"))
    inline_pdf = MIMEApplication(pdf_bytes("blue"), "pdf")
    inline_pdf.add_header("Content-Disposition", "inline", filename="statement.pdf")
    related.attach(inline_pdf)
    apple.attach(related)

    original = MIMEMultipart("mixed")
    original["Subject"] = "Original"
    original.attach(MIMEText("Forwarded body"))
    original.attach(pdf("forwarded.pdf", "green"))
    forwarded = MIMEMultipart("mixed")
    forwarded.attach(MIMEText("FYI"))
    forwarded.attach(MIMEMessage(original))

    newsletter = MIMEMultipart("related")
    newsletter.attach(MIMEText('<img src="cid:logo">', "html"))
    logo = MIMEImage(pdf_bytes("black"), "png")
    logo.add_header("Content-ID", "<logo>")
    logo.add_header("Content-Disposition", "inline", filename="logo.png")
    newsletter.attach(logo)

    result = {}
    for uid, (item, subject) in enumerate([(signed, "Signed"), (apple, "Apple"), (forwarded, "Forwarded"), (newsletter, "Newsletter")], start=1):
        item["From"] = "Sender <s@example.test>"
        item["Subject"] = subject
        item["Message-ID"] = f"<{subject}@example.test>"
        result[uid] = item.as_bytes()
    return result


@pytest.mark.django_db
def test_attachments_inside_signed_alternative_and_forwarded_mail_are_found_but_inline_logos_are_not(owner, tmp_path):
    account = account_for(owner)
    MailRule.objects.create(owner=owner, account=account, name="All", title_from=MailRule.Title.FILENAME)
    assert poll(FakeMailbox({"INBOX": nested_messages()}), account, tmp_path) == 3
    assert sorted(Document.objects.filter(owner=owner).values_list("title", flat=True)) == ["fattura", "forwarded", "statement"]
    assert ProcessedMail.objects.get(uid=4).status == ProcessedMail.Status.NO_MATCH

    inline_rule = MailRule.objects.create(owner=owner, account=account, name="Images too", include_inline=True)
    account.rules.exclude(pk=inline_rule.pk).update(enabled=False)
    assert poll(FakeMailbox({"INBOX": nested_messages()}), account, tmp_path) == 1
    assert Document.objects.filter(owner=owner, original_name="logo.png").exists()


@pytest.mark.django_db
def test_a_broken_message_is_recorded_and_never_blocks_the_rest_of_the_mailbox(owner, tmp_path):
    account = account_for(owner)
    MailRule.objects.create(owner=owner, account=account, name="All")
    weird = message(subject="placeholder", message_id="<weird@example.test>")
    weird = weird.replace(b"From: Acme Energy <billing@acme.test>", b'From: =Z:Z; [")[><<:').replace(b"Subject: placeholder", b"Subject: =?utf-8?q?Fattura_=E2=82=AC?=")
    fake = FakeMailbox({"INBOX": {1: b"not really an email", 2: weird, 3: message(message_id="<ok@example.test>")}})
    real_import = mail.import_message

    def flaky(rule, raw, **kwargs):
        if kwargs["uid"] == 1:
            raise AttributeError("parser bug")
        return real_import(rule, raw, **kwargs)

    with patch.object(mail, "import_message", side_effect=flaky):
        assert poll(fake, account, tmp_path) == 2
    assert ProcessedMail.objects.get(uid=1).status == ProcessedMail.Status.FAILED
    assert Document.objects.filter(owner=owner, title="Fattura €").exists()
    account.refresh_from_db()
    assert account.polling_until is None
    assert account.last_error == "All: Some messages could not be read. See Recent mail."
    assert fake.flags == {2: {"\\Seen"}, 3: {"\\Seen"}}

    with patch.object(mail, "connect", side_effect=RuntimeError("boom")):
        assert poll(fake, account, tmp_path) == 0
    account.refresh_from_db()
    assert account.polling_until is None and account.last_error == "Checking this mailbox failed. Ripiano will try again."


@pytest.mark.django_db
def test_a_backlog_is_imported_oldest_first_across_polls(owner, tmp_path):
    account = account_for(owner)
    MailRule.objects.create(owner=owner, account=account, name="All", after=MailRule.After.NOTHING)
    fake = FakeMailbox({"INBOX": {uid: message(subject=f"Bill {uid}", attachments=((f"bill{uid}.pdf", pdf_bytes((uid * 40, 0, 0))),), message_id=f"<{uid}@x>") for uid in range(1, 6)}})
    with patch.object(mail, "MESSAGES_PER_POLL", 2):
        assert poll(fake, account, tmp_path) == 2
        assert sorted(Document.objects.values_list("title", flat=True)) == ["Bill 1", "Bill 2"]
        assert poll(fake, account, tmp_path) == 2
        assert poll(fake, account, tmp_path) == 1
        assert poll(fake, account, tmp_path) == 0
    assert Document.objects.count() == 5


@pytest.mark.django_db
def test_editing_filters_reconsiders_passed_over_mail_and_imports_repair_missing_filing(owner, tmp_path):
    account = account_for(owner)
    tag = Tag.objects.create(owner=owner, name="Bills")
    client = Client()
    client.force_login(owner)
    rule_id = client.post("/api/mail/rules", {"account_id": str(account.id), "name": "Bills", "folder": "INBOX", "filter_from": "typo.test", "after": "nothing", "tag_ids": [str(tag.id)]}, content_type="application/json").json()["id"]
    fake = FakeMailbox({"INBOX": {1: message(message_id="<bill@acme.test>")}})
    assert poll(fake, account, tmp_path) == 0
    assert ProcessedMail.objects.get(uid=1).status == ProcessedMail.Status.NO_MATCH
    assert client.patch(f"/api/mail/rules/{rule_id}", {"filter_from": "acme.test"}, content_type="application/json").status_code == 200
    assert poll(fake, account, tmp_path) == 1
    document = Document.objects.get(owner=owner)

    # Simulate a crash that lost the filing: the next sighting repairs it without a duplicate.
    DocumentEmail.objects.filter(document=document).delete()
    DocumentTag.objects.filter(document=document).delete()
    second = MailRule.objects.create(owner=owner, account=account, name="Again", after=MailRule.After.NOTHING)
    second.tags.add(tag)
    assert poll(fake, account, tmp_path) == 0
    assert Document.objects.filter(owner=owner).count() == 1
    assert DocumentEmail.objects.filter(document=document).exists()
    assert DocumentTag.objects.get(document=document).origin == DocumentTag.Origin.SOURCE


def test_folder_names_round_trip_through_modified_utf7():
    for name in ["INBOX", "Fatture/2026", "Bollette & Fatture", "Ricevute già pagate", "日本語"]:
        assert mail.decode_folder(mail.encode_folder(name)) == name
    assert mail.encode_folder("Ricevute già") == "Ricevute gi&AOA-"


@pytest.mark.django_db
def test_a_rule_can_import_the_email_itself_with_or_without_its_attachments(owner, tmp_path):
    account = account_for(owner)
    rule = MailRule.objects.create(owner=owner, account=account, name="Whole mail", consume=MailRule.Consume.MESSAGE, after=MailRule.After.NOTHING)
    letter = message(subject="Avviso di pagamento", attachments=(), body="Pagare entro il 30", message_id="<letter@x>")
    with_file = message(subject="Bolletta", message_id="<bill@x>")
    assert poll(FakeMailbox({"INBOX": {1: letter}}), account, tmp_path) == 1
    document = Document.objects.get(owner=owner)
    assert (document.title, document.original_mime) == ("Avviso di pagamento", "message/rfc822")
    assert (tmp_path / document.original_path).read_bytes() == letter

    rule.consume = MailRule.Consume.BOTH
    rule.save()
    assert poll(FakeMailbox({"INBOX": {2: with_file}}), account, tmp_path) == 2
    assert sorted(Document.objects.filter(owner=owner).values_list("title", flat=True)) == ["Avviso di pagamento", "Bolletta", "Bolletta – bill"]
