"""A document's audit history: who or what changed its details, and when.

Call ``snapshot(document)`` before a change and ``record(document, before, ...)`` after it; one
``DocumentEvent`` is written only if a tracked detail actually changed. Values are stored readably
(tag, sender, type, and storage path names; ISO dates) so the history survives renames and deletions.
Document text, OCR, and notes are never recorded.
"""

from .models import CustomFieldValue, Document, DocumentEvent, DocumentTag

Action = DocumentEvent.Action
Kind = DocumentEvent.ActorKind

SCALARS = (
    ("title", "title"),
    ("document_date", "document_date"),
    ("correspondent", "correspondent__name"),
    ("document_type", "document_type__name"),
    ("storage_path", "storage_path__name"),
    ("asn", "asn"),
)
# Details someone the owner shared one document with does not see.
OWNER_ONLY_FIELDS = {"storage_path", "asn", "custom_field"}
DIFF_ACTIONS = {Action.UPDATED, Action.FILED_AUTOMATICALLY}


def _text(value):
    if value is None or value == "":
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def snapshot(document):
    """The tracked details of a document as stored now (three small queries)."""
    document_id = getattr(document, "pk", document)
    row = Document.objects.filter(pk=document_id).values(*(lookup for _, lookup in SCALARS)).first() or {}
    tags = sorted(DocumentTag.objects.filter(document_id=document_id).values_list("tag__name", flat=True), key=str.casefold)
    custom = dict(CustomFieldValue.objects.filter(document_id=document_id).values_list("field__name", "value"))
    state = {field: _text(row.get(lookup)) for field, lookup in SCALARS}
    state["tags"] = tags
    state["custom_fields"] = custom
    return state


def diff(before, after):
    changes = [{"field": field, "from": before.get(field), "to": after.get(field)}
               for field, _ in SCALARS if before.get(field) != after.get(field)]
    if before.get("tags", []) != after.get("tags", []):
        changes.append({"field": "tags", "from": before.get("tags", []), "to": after.get("tags", [])})
    old, new = before.get("custom_fields", {}), after.get("custom_fields", {})
    for name in sorted(set(old) | set(new), key=str.casefold):
        if old.get(name) != new.get(name):
            changes.append({"field": "custom_field", "name": name, "from": old.get(name), "to": new.get(name)})
    return changes


def record(document, before, actor_user=None, actor_label="", action=Action.UPDATED, *, actor_kind=None):
    """Write one event if a tracked detail changed since ``before``; return it, or None."""
    changes = diff(before, snapshot(document))
    if not changes:
        return None
    return DocumentEvent.objects.create(
        document_id=document.pk, actor_user=actor_user, actor_kind=actor_kind or Kind.USER,
        actor_label=(actor_label or "")[:200], action=action, changes=changes,
    )


def log(document, action, actor_user=None, actor_label="", *, actor_kind=None, changes=()):
    """Write an event that does not depend on a diff (added, Trash, restore, new version)."""
    return DocumentEvent.objects.create(
        document_id=getattr(document, "pk", document), actor_user=actor_user, actor_kind=actor_kind or Kind.USER,
        actor_label=(actor_label or "")[:200], action=action, changes=list(changes),
    )


def log_many(document_ids, action, actor_user=None):
    DocumentEvent.objects.bulk_create([
        DocumentEvent(document_id=document_id, actor_user=actor_user, actor_kind=Kind.USER, action=action)
        for document_id in document_ids
    ])


def created(document):
    """The first event of every document, naming its input channel."""
    person = document.source in (Document.Source.WEB, Document.Source.ANDROID)
    kind = Kind.USER if person else Kind.EMAIL_RULE if document.source == Document.Source.EMAIL else Kind.SOURCE
    return log(document, Action.CREATED, actor_user=document.owner if person else None, actor_kind=kind,
               changes=[{"field": "source", "from": None, "to": document.source}])


def event_json(event, owner_view=True):
    changes = event.changes if owner_view else [item for item in event.changes if item.get("field") not in OWNER_ONLY_FIELDS]
    return {
        "id": str(event.id),
        "created_at": event.created_at.isoformat(),
        "action": event.action,
        "actor": {
            "kind": event.actor_kind,
            "name": event.actor_label,
            "user": event.actor_user.get_username() if event.actor_user_id else None,
        },
        "changes": changes,
    }
