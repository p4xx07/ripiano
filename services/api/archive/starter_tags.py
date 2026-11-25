"""Starter tags: a small English set every new account begins with, renamable like any other tag.

Each top-level tag (except Warranties) lines up with a default paper category, so choosing tags is enough for
Ripiano to propose the paper code prefix (see apps/web/src/paperCategorySuggestion.ts).
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Tag

# (top-level name, colour, children). Names are unique per account, so children never repeat a word on their own.
STARTER_TAGS = (
    ("Home", "#3b7a57", ("Rent or mortgage", "Utilities", "Home insurance")),
    ("Finance and taxes", "#2e7f86", ("Bank", "Taxes", "Work and pay")),
    ("Health", "#b8434d", ("Medical reports", "Pharmacy")),
    ("Vehicles", "#5b6b7a", ("Car insurance", "Vehicle tax", "Maintenance")),
    ("Personal", "#7a4fa3", ("Identity documents", "School")),
    ("Events and travel", "#c46a2c", ("Tickets", "Bookings")),
    ("Warranties", "#8a7a2e", ()),
)


def ensure_starter_tags(owner):
    """Add the starter tags the account does not have yet (matched by name, any case). Returns how many were added.

    Existing tags are never renamed, moved, or recoloured; a child whose name is already used elsewhere is skipped.
    """
    added = 0
    with transaction.atomic():
        get_user_model().objects.select_for_update(no_key=True).get(pk=owner.pk)
        existing = {name.lower(): tag_id for tag_id, name in Tag.objects.filter(owner=owner).values_list("id", "name")}
        for name, color, children in STARTER_TAGS:
            parent_id = existing.get(name.lower())
            if parent_id is None:
                parent_id = Tag.objects.create(owner=owner, name=name, color=color).id
                existing[name.lower()] = parent_id
                added += 1
            for child in children:
                if child.lower() not in existing:
                    existing[child.lower()] = Tag.objects.create(owner=owner, name=child, color=color, parent_id=parent_id).id
                    added += 1
    return added
