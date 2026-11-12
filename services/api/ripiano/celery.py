import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ripiano.settings")

app = Celery("ripiano")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "reconcile-pending-documents": {
        "task": "archive.tasks.reconcile_pending_documents",
        "schedule": 60.0,
    },
    "reconcile-purge-jobs": {
        "task": "archive.tasks.reconcile_purge_jobs",
        "schedule": 300.0,
    },
    "purge-expired-trash": {
        "task": "archive.tasks.purge_expired_trash",
        "schedule": crontab(hour=3, minute=0),
    },
    "reconcile-browse-exports": {
        "task": "archive.tasks.reconcile_browse_exports",
        "schedule": 300.0,
    },
    "scheduled-backup": {
        "task": "archive.tasks.backup_archive",
        "schedule": crontab(hour=settings.RIPIANO_BACKUP_HOUR, minute=settings.RIPIANO_BACKUP_MINUTE),
    },
}
