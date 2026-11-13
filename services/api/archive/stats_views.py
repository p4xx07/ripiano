"""Owner overview: archive statistics and the health of the things that run in the background."""

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import BackupRun, Document, DocumentTag, MailAccount, Workflow, WorkflowRun


@require_http_methods(["GET"])
def overview(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    owner = request.user
    documents = Document.objects.filter(owner=owner, trashed_at__isnull=True, is_split_source=False)
    totals = documents.aggregate(
        total=Count("id"),
        ready=Count("id", filter=Q(status=Document.Status.READY)),
        waiting=Count("id", filter=Q(status__in=[Document.Status.PENDING, Document.Status.PROCESSING])),
        failed=Count("id", filter=Q(status=Document.Status.FAILED)),
        needs_action=Count("id", filter=Q(action_status=Document.ActionStatus.OPEN)),
        overdue=Count("id", filter=Q(action_status=Document.ActionStatus.OPEN, action_due_date__lt=timezone.localdate())),
        duplicates=Count("id", filter=Q(duplicate_of__isnull=False, duplicate_reviewed_at__isnull=True)),
        bytes=Sum("original_size"),
    )
    # Counted on its own: joining tag links into the aggregate above would multiply the other totals.
    totals["untagged"] = documents.filter(tag_links__isnull=True).count()
    # The last 12 calendar months, empty months included, so the chart always reads as a year.
    today = timezone.localdate()
    months = []
    year, month = today.year, today.month
    for _ in range(12):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    months.reverse()
    since = timezone.make_aware(timezone.datetime(int(months[0][:4]), int(months[0][5:]), 1))
    counted = {
        row["month"].date().isoformat()[:7]: row["count"]
        for row in documents.filter(created_at__gte=since).annotate(month=TruncMonth("created_at")).values("month").annotate(count=Count("id"))
    }
    monthly = [{"month": value, "count": counted.get(value, 0)} for value in months]
    by_type = [
        {"name": row["document_type__name"] or "No type", "count": row["count"]}
        for row in documents.values("document_type__name").annotate(count=Count("id")).order_by("-count")[:8]
    ]
    by_source = {row["source"]: row["count"] for row in documents.values("source").annotate(count=Count("id"))}
    top_tags = [
        {"name": row["tag__name"], "count": row["count"]}
        for row in DocumentTag.objects.filter(document__in=documents).values("tag__name").annotate(count=Count("document")).order_by("-count")[:8]
    ]
    last_backup = BackupRun.objects.order_by("-created_at").first() if owner.is_superuser else None
    mailboxes = MailAccount.objects.filter(owner=owner)
    failed_runs = WorkflowRun.objects.filter(workflow__owner=owner, status=WorkflowRun.Status.FAILED, created_at__gte=timezone.now() - timedelta(days=7)).count()
    return JsonResponse({
        "documents": {key: value or 0 for key, value in totals.items()},
        "monthly": monthly, "by_type": by_type, "by_source": by_source, "top_tags": top_tags,
        "health": {
            "backup": {"status": last_backup.status, "at": (last_backup.completed_at or last_backup.created_at).isoformat()} if last_backup else None,
            "mailboxes": {"total": mailboxes.count(), "with_errors": mailboxes.exclude(last_error="").count()},
            "workflows": {"enabled": Workflow.objects.filter(owner=owner, enabled=True).count(), "failed_last_week": failed_runs},
        },
    })
