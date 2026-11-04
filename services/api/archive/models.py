import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Document(models.Model):
    class Source(models.TextChoices):
        WEB = "web", "Web"
        TELEGRAM = "telegram", "Telegram"

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
    archive_path = models.CharField(max_length=500, blank=True)
    extracted_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["source", "source_ref"], condition=~Q(source_ref=""), name="unique_document_source_ref")]


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
