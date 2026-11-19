"""Who may open a document besides its owner.

The owner always has full control. A DocumentAccess grant lets one person, or every member of a
group, view the document; an "edit" grant also lets them change its details (title, date,
follow-up) and add notes. Filing, files, sharing, and Trash stay with the owner.
"""

from django.db.models import Exists, OuterRef, Q

from .models import Document, DocumentAccess

OWNER, EDIT, VIEW = "owner", DocumentAccess.Level.EDIT, DocumentAccess.Level.VIEW


def _grants_for(user):
    return DocumentAccess.objects.filter(Q(user=user) | Q(group__in=user.groups.all()))


def shared_with(user):
    """Documents someone else owns and shared with this user, directly or through a group."""
    if not user.is_active:
        return Document.objects.none()
    return Document.objects.filter(Exists(_grants_for(user).filter(document_id=OuterRef("pk")))).exclude(owner=user)


def edit_grant_exists(user):
    """An annotation: True when the user may edit the details of the outer document."""
    return Exists(_grants_for(user).filter(document_id=OuterRef("pk"), level=EDIT))


def level_for(user, document):
    if document.owner_id == user.pk:
        return OWNER
    if not user.is_active:
        return None
    levels = set(_grants_for(user).filter(document=document).values_list("level", flat=True))
    if EDIT in levels:
        return EDIT
    return VIEW if levels else None


def readable(user, document_id, queryset=None):
    """Return (document, level) for a document the user may at least view, or (None, None)."""
    queryset = queryset if queryset is not None else Document.objects
    document = queryset.filter(pk=document_id, trashed_at__isnull=True).first()
    if document is None:
        return None, None
    level = level_for(user, document)
    return (document, level) if level else (None, None)
