from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.models import Document, DocumentTag, DocumentType, Tag


def make(owner, title, **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path="originals/aa/x.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=1000, **values)


@pytest.mark.django_db
def test_overview_counts_only_the_owners_visible_documents():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    invoice = DocumentType.objects.create(owner=owner, name="Invoice")
    bills = Tag.objects.create(owner=owner, name="Bills")
    home = Tag.objects.create(owner=owner, name="Home")
    tagged = make(owner, "a", status="ready", document_type=invoice)
    DocumentTag.objects.create(document=tagged, tag=bills)
    DocumentTag.objects.create(document=tagged, tag=home)  # two tag links must not double any total
    make(owner, "b", status="failed", action_status="open", action_due_date=date.today() - timedelta(days=1))
    make(owner, "c", status="pending", duplicate_of=tagged)
    make(owner, "trashed", status="ready", trashed_at=timezone.now())
    make(owner, "hidden source", status="ready", is_split_source=True)
    make(other, "theirs", status="ready")
    assert Client().get("/api/overview").status_code == 401
    client = Client()
    client.force_login(owner)
    data = client.get("/api/overview").json()
    assert data["documents"] == {"total": 3, "ready": 1, "waiting": 1, "failed": 1, "needs_action": 1, "overdue": 1,
                                 "duplicates": 1, "bytes": 3000, "untagged": 2}
    assert data["by_type"][0] == {"name": "No type", "count": 2}
    assert {row["name"] for row in data["top_tags"]} == {"Bills", "Home"}
    assert len(data["monthly"]) == 12 and sum(row["count"] for row in data["monthly"]) == 3
    assert data["health"]["backup"] is None and data["health"]["mailboxes"] == {"total": 0, "with_errors": 0}
