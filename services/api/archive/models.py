import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Document(models.Model):
    class Source(models.TextChoices):
        WEB = "web", "Web"
        TELEGRAM = "telegram", "Telegram"
        ANDROID = "android", "Android scanner"
        FOLDER = "folder", "Watched folder"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

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
    archive_path = models.CharField(max_length=500, blank=True)
    extracted_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    document_date = models.DateField(null=True, blank=True)
    tags = models.ManyToManyField("Tag", through="DocumentTag", related_name="documents")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["owner", "source", "source_ref"], condition=~Q(source_ref=""), name="unique_document_source_ref")]
        indexes = [models.Index(fields=["owner", "original_sha256"], name="document_owner_sha_idx")]


class InputCursor(models.Model):
    source = models.CharField(max_length=30, unique=True)
    next_offset = models.BigIntegerField(default=0)


class BackupRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    trigger = models.CharField(max_length=20, default="schedule")
    snapshot_name = models.CharField(max_length=100, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#5d8b66")
    description = models.CharField(max_length=500, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_tag_name_per_owner")]


class DocumentTag(models.Model):
    class Origin(models.TextChoices):
        MANUAL = "manual", "Manual"
        RULE = "rule", "Rule"
        MODEL = "model", "Model"

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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Movement(models.Model):
    physical_copy = models.ForeignKey(PhysicalCopy, on_delete=models.CASCADE, related_name="movements")
    from_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="moves_from")
    to_location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="moves_to")
    moved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
