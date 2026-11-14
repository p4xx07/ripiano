import uuid
import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


def new_location_code():
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "L-" + "".join(secrets.choice(alphabet) for _ in range(8))


class Document(models.Model):
    class Source(models.TextChoices):
        WEB = "web", "Web"
        TELEGRAM = "telegram", "Telegram"
        ANDROID = "android", "Android scanner"
        FOLDER = "folder", "Watched folder"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    class ActionStatus(models.TextChoices):
        NONE = "none", "No follow-up"
        OPEN = "open", "Needs action"
        DONE = "done", "Completed"

    class FilingOrigin(models.TextChoices):
        NONE = "none", "Unassigned"
        RULE = "rule", "Matching phrase"
        MODEL = "model", "Agent suggestion"
        LEARNED = "learned", "Local learned filing"
        MANUAL = "manual", "Set by user"
        SOURCE = "source", "Input rule"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents")
    source = models.CharField(max_length=30, choices=Source.choices, default=Source.WEB)
    source_ref = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=300)
    original_name = models.CharField(max_length=500)
    original_path = models.CharField(max_length=500)
    original_mime = models.CharField(max_length=100)
    original_sha256 = models.CharField(max_length=64)
    original_size = models.PositiveBigIntegerField()
    duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="exact_copies")
    duplicate_reviewed_at = models.DateTimeField(null=True, blank=True)
    archive_path = models.CharField(max_length=500, blank=True)
    extracted_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    trashed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    document_date = models.DateField(null=True, blank=True)
    correspondent = models.ForeignKey("Correspondent", null=True, blank=True, on_delete=models.PROTECT, related_name="documents")
    document_type = models.ForeignKey("DocumentType", null=True, blank=True, on_delete=models.PROTECT, related_name="documents")
    correspondent_origin = models.CharField(max_length=10, choices=FilingOrigin.choices, default=FilingOrigin.NONE)
    document_type_origin = models.CharField(max_length=10, choices=FilingOrigin.choices, default=FilingOrigin.NONE)
    action_status = models.CharField(max_length=10, choices=ActionStatus.choices, default=ActionStatus.NONE, db_index=True)
    action_due_date = models.DateField(null=True, blank=True)
    action_note = models.CharField(max_length=500, blank=True)
    action_completed_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField("Tag", through="DocumentTag", related_name="documents")
    # Archive serial number: the owner's own running number, often printed as a barcode label.
    asn = models.PositiveIntegerField(null=True, blank=True)
    # A scan split at separator sheets stays as the hidden source of its parts.
    split_parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="split_parts")
    is_split_source = models.BooleanField(default=False)
    # Folder template for the NAS browse copy; managed originals never move.
    storage_path = models.ForeignKey("StoragePath", null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")
    # The original_* fields always describe the current version; older files live in DocumentVersion.
    version_number = models.PositiveIntegerField(default=1)
    version_note = models.CharField(max_length=200, default="Original upload")
    version_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "source", "source_ref"], condition=~Q(source_ref=""), name="unique_document_source_ref"),
            models.UniqueConstraint(fields=["owner", "asn"], condition=Q(asn__isnull=False), name="unique_document_asn_per_owner"),
        ]
        indexes = [models.Index(fields=["owner", "original_sha256"], name="document_owner_sha_idx")]


class ShareLink(models.Model):
    """An expiring bearer link to one preserved original; only its hash is stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="share_links")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="share_links")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "document", "-created_at"], name="share_owner_doc_recent_idx")]


class DocumentNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["document", "-created_at"], name="document_note_recent_idx")]


class DocumentLink(models.Model):
    """One reciprocal relationship, stored in stable UUID order."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    left = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="links_from")
    right = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="links_to")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["left", "right"], name="unique_document_link_pair"),
            models.CheckConstraint(condition=~Q(left=models.F("right")), name="document_link_no_self"),
        ]


class CustomField(models.Model):
    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        DATE = "date", "Date"
        BOOLEAN = "boolean", "Yes or no"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="custom_fields")
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(Lower("name"), "owner", name="unique_custom_field_owner_name_ci")]


class CustomFieldValue(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="custom_values")
    field = models.ForeignKey(CustomField, on_delete=models.PROTECT, related_name="values")
    value = models.CharField(max_length=500)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "field"], name="unique_document_custom_field")]


class InputCursor(models.Model):
    source = models.CharField(max_length=30, unique=True)
    next_offset = models.BigIntegerField(default=0)


class BackupRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    retry_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="retry_run")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    trigger = models.CharField(max_length=20, default="schedule")
    snapshot_name = models.CharField(max_length=100, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class BrowseExportRun(models.Model):
    """One owner-scoped, rebuildable NAS browse copy."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    retry_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="retry_run")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="browse_exports")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    folder_name = models.CharField(max_length=100, blank=True)
    document_count = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#5d8b66")
    description = models.CharField(max_length=500, blank=True)
    barcode_value = models.CharField(max_length=100, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_tag_name_per_owner"),
            models.UniqueConstraint(Lower("barcode_value"), "owner", condition=~Q(barcode_value=""), name="unique_tag_barcode_owner_ci"),
        ]


class Correspondent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="correspondents")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), "owner", name="unique_correspondent_owner_name_ci")]


class DocumentType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_types")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), "owner", name="unique_document_type_owner_name_ci")]


class SavedView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_views")
    name = models.CharField(max_length=100)
    query = models.CharField(max_length=200, blank=True)
    tag = models.ForeignKey(Tag, null=True, blank=True, on_delete=models.SET_NULL)
    correspondent = models.ForeignKey(Correspondent, null=True, blank=True, on_delete=models.SET_NULL)
    document_type = models.ForeignKey(DocumentType, null=True, blank=True, on_delete=models.SET_NULL)
    copy_status = models.CharField(max_length=7, blank=True)
    custom_field = models.ForeignKey(CustomField, null=True, blank=True, on_delete=models.PROTECT)
    custom_value = models.CharField(max_length=500, blank=True)
    custom_min = models.CharField(max_length=500, blank=True)
    custom_max = models.CharField(max_length=500, blank=True)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), "owner", name="unique_saved_view_owner_name_ci")]


class FilingRule(models.Model):
    class Kind(models.TextChoices):
        CORRESPONDENT = "correspondent", "Correspondent"
        DOCUMENT_TYPE = "document_type", "Document type"

    class Field(models.TextChoices):
        TITLE = "title", "Title"
        TEXT = "text", "Document text"
        EITHER = "either", "Title or text"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="filing_rules")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    correspondent = models.ForeignKey(Correspondent, null=True, blank=True, on_delete=models.CASCADE, related_name="rules")
    document_type = models.ForeignKey(DocumentType, null=True, blank=True, on_delete=models.CASCADE, related_name="rules")
    pattern = models.CharField(max_length=200)
    field = models.CharField(max_length=10, choices=Field.choices, default=Field.EITHER)
    # phrase | any (word) | all (words) | regex | fuzzy — see classification.text_matches
    match = models.CharField(max_length=10, default="phrase")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(kind="correspondent", correspondent__isnull=False, document_type__isnull=True) | Q(kind="document_type", correspondent__isnull=True, document_type__isnull=False), name="filing_rule_exactly_one_target"),
            models.UniqueConstraint(fields=["owner", "correspondent", "pattern", "field"], condition=Q(kind="correspondent"), name="unique_correspondent_phrase"),
            models.UniqueConstraint(fields=["owner", "document_type", "pattern", "field"], condition=Q(kind="document_type"), name="unique_document_type_phrase"),
        ]


class DocumentTag(models.Model):
    class Origin(models.TextChoices):
        MANUAL = "manual", "Manual"
        RULE = "rule", "Rule"
        MODEL = "model", "Model"
        LEARNED = "learned", "Local learned filing"
        SOURCE = "source", "Input rule"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="tag_links")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="document_links")
    origin = models.CharField(max_length=20, choices=Origin.choices, default=Origin.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "tag"], name="unique_document_tag")]


class ClassificationRule(models.Model):
    class Field(models.TextChoices):
        TITLE = "title", "Title"
        TEXT = "text", "Document text"
        EITHER = "either", "Title or text"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="classification_rules")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="rules")
    pattern = models.CharField(max_length=200)
    field = models.CharField(max_length=10, choices=Field.choices, default=Field.EITHER)
    # phrase | any (word) | all (words) | regex | fuzzy — see classification.text_matches
    match = models.CharField(max_length=10, default="phrase")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["owner", "tag", "pattern", "field"], name="unique_tag_rule")]


class TagOverride(models.Model):
    """A user rejected this tag for this document; rules must respect that correction."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="tag_overrides")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="overrides")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "tag"], name="unique_tag_override")]


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="physical_locations")
    name = models.CharField(max_length=100)
    sticker_code = models.CharField(max_length=10, unique=True, default=new_location_code)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    description = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]


class PhysicalCopy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="physical_copies")
    sticker_code = models.CharField(max_length=12, unique=True)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT, related_name="physical_copies")
    missing_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Movement(models.Model):
    class Kind(models.TextChoices):
        PLACEMENT = "placement", "Initial placement"
        MOVE = "move", "Move"
        MISSING = "missing", "Marked missing"
        FOUND = "found", "Marked found"

    physical_copy = models.ForeignKey(PhysicalCopy, on_delete=models.CASCADE, related_name="movements")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.MOVE)
    from_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="moves_from")
    to_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="moves_to")
    moved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TrashRetentionPolicy(models.Model):
    """Per-owner opt-in to remove documents left in Trash for a chosen age."""

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trash_retention_policy")
    enabled = models.BooleanField(default=False)
    days = models.PositiveSmallIntegerField(default=90)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(days__gte=30, days__lte=3650), name="trash_retention_days_range"),
        ]


class PurgeJob(models.Model):
    """Retryable cleanup record retained after its document row is deleted."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purge_jobs")
    document_id = models.UUIDField(unique=True)
    title = models.CharField(max_length=300, blank=True)
    original_path = models.CharField(max_length=500, blank=True)
    archive_path = models.CharField(max_length=500, blank=True)
    original_sha256 = models.CharField(max_length=64, blank=True)
    # Older version files: [{"path": ..., "sha256": ...}]
    version_files = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AgentGrant(models.Model):
    """A named, revocable bearer grant; only the hash is persisted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_grants")
    name = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)
    filter_tag = models.ForeignKey(Tag, null=True, blank=True, on_delete=models.PROTECT, related_name="agent_grants")
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AgentAudit(models.Model):
    grant = models.ForeignKey(AgentGrant, on_delete=models.CASCADE, related_name="audit_events")
    action = models.CharField(max_length=60)
    document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL)
    outcome = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class MailAccount(models.Model):
    """An owner's IMAP mailbox. The secret is encrypted at rest and never returned."""

    class Security(models.TextChoices):
        SSL = "ssl", "SSL/TLS"
        STARTTLS = "starttls", "STARTTLS"
        NONE = "none", "None (local networks only)"

    class Auth(models.TextChoices):
        PASSWORD = "password", "Password"
        OAUTH = "oauth", "OAuth"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mail_accounts")
    name = models.CharField(max_length=100)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=993)
    security = models.CharField(max_length=10, choices=Security.choices, default=Security.SSL)
    username = models.CharField(max_length=255)
    auth = models.CharField(max_length=10, choices=Auth.choices, default=Auth.PASSWORD)
    oauth_provider = models.CharField(max_length=20, blank=True)
    secret = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    polling_until = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)
    last_imported = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(Lower("name"), "owner", name="unique_mail_account_name_per_owner")]


class MailRule(models.Model):
    """Which messages to import from one folder, and what to do with them afterwards."""

    class After(models.TextChoices):
        MARK_READ = "mark_read", "Mark as read"
        FLAG = "flag", "Flag"
        MOVE = "move", "Move to folder"
        NOTHING = "nothing", "Leave unchanged"

    class Title(models.TextChoices):
        SUBJECT = "subject", "Email subject"
        FILENAME = "filename", "Attachment name"

    class Consume(models.TextChoices):
        ATTACHMENTS = "attachments", "Attachments"
        MESSAGE = "message", "The email itself"
        BOTH = "both", "Email and attachments"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mail_rules")
    account = models.ForeignKey(MailAccount, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)
    folder = models.CharField(max_length=200, default="INBOX")
    filter_from = models.CharField(max_length=200, blank=True)
    filter_subject = models.CharField(max_length=200, blank=True)
    filter_body = models.CharField(max_length=200, blank=True)
    filter_attachment = models.CharField(max_length=200, blank=True)
    include_inline = models.BooleanField(default=False)
    consume = models.CharField(max_length=12, choices=Consume.choices, default=Consume.ATTACHMENTS)
    max_age_days = models.PositiveIntegerField(default=30)
    after = models.CharField(max_length=10, choices=After.choices, default=After.MARK_READ)
    move_to = models.CharField(max_length=200, blank=True)
    title_from = models.CharField(max_length=10, choices=Title.choices, default=Title.SUBJECT)
    tags = models.ManyToManyField("Tag", blank=True, related_name="mail_rules")
    correspondent = models.ForeignKey("Correspondent", null=True, blank=True, on_delete=models.SET_NULL, related_name="mail_rules")
    document_type = models.ForeignKey("DocumentType", null=True, blank=True, on_delete=models.SET_NULL, related_name="mail_rules")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at", "id"]


class ProcessedMail(models.Model):
    """One handled message per rule, so a mailbox is never imported twice."""

    class Status(models.TextChoices):
        IMPORTED = "imported", "Imported"
        NO_MATCH = "no_match", "No usable attachments"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    rule = models.ForeignKey(MailRule, on_delete=models.CASCADE, related_name="processed")
    folder = models.CharField(max_length=200)
    uid_validity = models.BigIntegerField()
    uid = models.BigIntegerField()
    message_id = models.CharField(max_length=300, blank=True)
    subject = models.CharField(max_length=300, blank=True)
    sender = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    detail = models.CharField(max_length=300, blank=True)
    documents = models.PositiveIntegerField(default=0)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-processed_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["rule", "folder", "uid_validity", "uid"], name="unique_processed_mail")]


class DocumentEmail(models.Model):
    """Where an emailed document came from; kept even if the account is removed."""

    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name="email")
    account = models.ForeignKey(MailAccount, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")
    account_name = models.CharField(max_length=100)
    sender = models.CharField(max_length=300, blank=True)
    subject = models.CharField(max_length=300, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    message_id = models.CharField(max_length=300, blank=True)


class DocumentVersion(models.Model):
    """An earlier file of a document, kept unchanged when a new version replaces it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    note = models.CharField(max_length=200)
    original_name = models.CharField(max_length=500)
    original_path = models.CharField(max_length=500)
    original_mime = models.CharField(max_length=100)
    original_sha256 = models.CharField(max_length=64)
    original_size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField()
    replaced_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["document", "number"], name="unique_document_version_number")]



class Workflow(models.Model):
    """An owner's automation: when a trigger fires and the conditions match, apply the actions once."""

    class Trigger(models.TextChoices):
        ADDED = "added", "Document added"
        UPDATED = "updated", "Document updated"
        SCHEDULED = "scheduled", "Days after a date"

    class DateField(models.TextChoices):
        CREATED = "created", "Added date"
        DOCUMENT_DATE = "document_date", "Document date"
        DUE_DATE = "action_due_date", "Follow-up due date"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workflows")
    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    trigger = models.CharField(max_length=10, choices=Trigger.choices)
    schedule_field = models.CharField(max_length=20, choices=DateField.choices, default=DateField.CREATED)
    schedule_days = models.IntegerField(default=30)
    # Conditions (all optional; every set condition must match)
    filter_sources = models.JSONField(default=list, blank=True)
    filter_filename = models.CharField(max_length=200, blank=True)
    filter_text = models.CharField(max_length=200, blank=True)
    filter_tag = models.ForeignKey("Tag", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    filter_correspondent = models.ForeignKey("Correspondent", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    filter_document_type = models.ForeignKey("DocumentType", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # Actions
    add_tags = models.ManyToManyField("Tag", blank=True, related_name="workflows_adding")
    remove_tags = models.ManyToManyField("Tag", blank=True, related_name="workflows_removing")
    set_correspondent = models.ForeignKey("Correspondent", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    set_document_type = models.ForeignKey("DocumentType", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    set_needs_action = models.BooleanField(default=False)
    action_note = models.CharField(max_length=500, blank=True)
    add_note = models.TextField(blank=True)
    webhook_url = models.URLField(max_length=500, blank=True)
    email_to = models.CharField(max_length=500, blank=True)
    email_attach = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at", "id"]


class WorkflowRun(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="runs")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="workflow_runs")
    trigger = models.CharField(max_length=10, choices=Workflow.Trigger.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPLIED)
    detail = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # "Added" and scheduled workflows act once per document; "updated" may run on every change.
            models.UniqueConstraint(fields=["workflow", "document", "trigger"], condition=~Q(trigger="updated"), name="workflow_runs_once"),
        ]


class AccountSecurity(models.Model):
    """Per-person sign-in protection. Secrets are encrypted; recovery codes are stored hashed."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security")
    totp_secret = models.TextField(blank=True)
    pending_secret = models.TextField(blank=True)
    enabled_at = models.DateTimeField(null=True, blank=True)
    last_step = models.BigIntegerField(default=0)
    recovery_hashes = models.JSONField(default=list, blank=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)


class ShareBundle(models.Model):
    """An expiring bearer link to a ZIP of several originals; only its hash is stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="share_bundles")
    title = models.CharField(max_length=200)
    documents = models.ManyToManyField(Document, related_name="share_bundles")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    downloads = models.PositiveIntegerField(default=0)
    # The ZIP is built once, verified, and served as a file; it is deleted when the link ends.
    zip_status = models.CharField(max_length=10, default="building")
    zip_path = models.CharField(max_length=500, blank=True)
    zip_size = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-id"]


class DocumentEmailSend(models.Model):
    """A record of the owner emailing a document, kept for the history and rate limit."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="email_sends")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    recipients = models.TextField()
    attachment = models.CharField(max_length=12)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ApiToken(models.Model):
    """A personal REST API token. Only its hash is stored; it acts with its owner's access."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class StoragePath(models.Model):
    """A named folder template for the NAS browse copy, e.g. "{correspondent}/{year}"."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="storage_paths")
    name = models.CharField(max_length=100)
    template = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(Lower("name"), "owner", name="unique_storage_path_name_per_owner")]


class DocumentAccess(models.Model):
    """The owner lets another person, or everyone in a group, see (or also edit the details of) one document."""

    class Level(models.TextChoices):
        VIEW = "view", "Can view"
        EDIT = "edit", "Can edit details"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="access_grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="shared_documents")
    group = models.ForeignKey("auth.Group", null=True, blank=True, on_delete=models.CASCADE, related_name="shared_documents")
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.VIEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(user__isnull=False, group__isnull=True) | Q(user__isnull=True, group__isnull=False), name="document_access_one_target"),
            models.UniqueConstraint(fields=["document", "user"], condition=Q(user__isnull=False), name="unique_document_access_user"),
            models.UniqueConstraint(fields=["document", "group"], condition=Q(group__isnull=False), name="unique_document_access_group"),
        ]


class FilingModel(models.Model):
    """A person's learned filing model, rebuilt from their own manual filing. Never shared or exported."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        TRAINING = "training", "Training"
        READY = "ready", "Ready"
        NOT_ENOUGH = "not_enough", "Not enough examples"
        FAILED = "failed", "Failed"

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="filing_model")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    payload = models.BinaryField(blank=True, default=b"")
    metrics = models.JSONField(default=dict, blank=True)
    examples = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    trained_at = models.DateTimeField(null=True, blank=True)


class AutoFilingPolicy(models.Model):
    """Owner opt-in for conservative local model filing; exported with account settings."""

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auto_filing_policy")
    enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
