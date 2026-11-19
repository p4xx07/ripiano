"""Sharing of filing objects (tags, senders, document types, saved views) with people and groups.

Each person keeps their own filing vocabulary; sharing never moves an object to someone else. A shared
object can be *used* by the recipient on the owner's documents they may edit, and seen in their lists.
Grants are removed when the object is deleted (see the post_delete handlers in apps.py).
"""

from django.db.models import Q

from .models import Correspondent, DocumentType, ObjectAccess, SavedView, Tag

MODELS = {
    ObjectAccess.Kind.TAG: Tag,
    ObjectAccess.Kind.CORRESPONDENT: Correspondent,
    ObjectAccess.Kind.DOCUMENT_TYPE: DocumentType,
    ObjectAccess.Kind.SAVED_VIEW: SavedView,
}
KIND_OF = {model: kind for kind, model in MODELS.items()}
VIEW, EDIT = ObjectAccess.Level.VIEW, ObjectAccess.Level.EDIT


def grants_for(user, kind=None):
    if not user.is_authenticated or not user.is_active:
        return ObjectAccess.objects.none()
    grants = ObjectAccess.objects.filter(Q(user=user) | Q(group__in=user.groups.all())).exclude(owner=user)
    return grants.filter(kind=kind) if kind else grants


def shared_objects(user, kind):
    """{object: level} for objects of one kind that others shared with this user (edit wins over view)."""
    levels = {}
    for object_id, level in grants_for(user, kind).values_list("object_id", "level"):
        if levels.get(object_id) != EDIT:
            levels[object_id] = level
    objects = MODELS[kind].objects.filter(pk__in=levels).select_related("owner")
    return {item: levels[item.pk] for item in objects}


def level_for(user, item):
    """"owner", "edit", "view", or None."""
    if item.owner_id == user.pk:
        return "owner"
    levels = set(grants_for(user, KIND_OF[type(item)]).filter(object_id=item.pk).values_list("level", flat=True))
    if EDIT in levels:
        return EDIT
    return VIEW if levels else None


def usable_ids(user, kind, owner):
    """IDs of the owner's objects of this kind the user may use (all of them if the user is the owner)."""
    if owner.pk == user.pk:
        return set(MODELS[kind].objects.filter(owner=owner).values_list("pk", flat=True))
    return set(grants_for(user, kind).filter(owner=owner).values_list("object_id", flat=True))


def forget(kind, object_id):
    ObjectAccess.objects.filter(kind=kind, object_id=object_id).delete()
