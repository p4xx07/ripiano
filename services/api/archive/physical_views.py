import io
import json
import re
import secrets
from uuid import UUID

import segno
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_http_methods

from .api_language import display, wants_italian
from .models import Document, Location, Movement, PhysicalCopy

STICKER_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _body(request):
    try:
        value = json.loads(request.body)
        return value if isinstance(value, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _unauthorized(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sign in required"}, status=401)
    return None


def location_path(location):
    names = []
    while location:
        names.append(location.name)
        location = location.parent
    return list(reversed(names))


def location_json(location):
    return {
        "id": str(location.id), "name": location.name,
        "sticker_code": location.sticker_code,
        "parent_id": str(location.parent_id) if location.parent_id else None,
        "path": location_path(location), "description": location.description,
    }


def copy_json(copy):
    return {
        "id": str(copy.id), "document_id": str(copy.document_id),
        "sticker_code": copy.sticker_code,
        "location_id": str(copy.location_id) if copy.location_id else None,
        "location_path": location_path(copy.location),
        "missing_at": copy.missing_at.isoformat() if copy.missing_at else None,
        "created_at": copy.created_at.isoformat(),
    }


def _location(owner, raw_id):
    if raw_id is None:
        return None
    try:
        return Location.objects.filter(pk=UUID(str(raw_id)), owner=owner).first()
    except ValueError:
        return None


def _locked_copy(owner, copy_id):
    """Lock parent before copy, matching the document Trash lock order."""
    document_id = PhysicalCopy.objects.filter(pk=copy_id, document__owner=owner).values_list("document_id", flat=True).first()
    if document_id is None or not Document.objects.select_for_update().filter(pk=document_id, owner=owner, trashed_at__isnull=True).exists():
        return None
    return PhysicalCopy.objects.select_for_update(of=("self",)).filter(pk=copy_id, document_id=document_id).first()


@require_http_methods(["GET", "POST"])
def locations(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "GET":
        return JsonResponse({"locations": [location_json(item) for item in Location.objects.filter(owner=request.user).select_related("parent__parent")]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = body.get("name", "")
    description = body.get("description", "")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100 or not isinstance(description, str) or len(description) > 500:
        return JsonResponse({"error": "Invalid location name or description"}, status=400)
    parent = _location(request.user, body.get("parent_id"))
    if body.get("parent_id") and parent is None:
        return JsonResponse({"error": "Parent location not found"}, status=400)
    if Location.objects.filter(owner=request.user, parent=parent, name__iexact=name.strip()).exists():
        return JsonResponse({"error": "Location already exists here"}, status=409)
    location = Location.objects.create(owner=request.user, name=name.strip(), description=description.strip(), parent=parent)
    return JsonResponse(location_json(location), status=201)


def _descendant_ids(owner, root_id):
    children = {}
    for child_id, parent_id in Location.objects.filter(owner=owner).values_list("id", "parent_id"):
        children.setdefault(parent_id, []).append(child_id)
    ids, pending = set(), [root_id]
    while pending:
        current = pending.pop()
        if current not in ids:
            ids.add(current)
            pending.extend(children.get(current, []))
    return ids


def _update_location(request, location_id):
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if "name" not in body and "parent_id" not in body:
        return JsonResponse({"error": "Choose a new name or parent location"}, status=400)
    name = body.get("name")
    if "name" in body and (not isinstance(name, str) or not name.strip() or len(name.strip()) > 100):
        return JsonResponse({"error": "Invalid location name or description"}, status=400)
    with transaction.atomic():
        # Lock every location of this owner so two concurrent moves cannot create a cycle.
        list(Location.objects.select_for_update().filter(owner=request.user).values_list("id", flat=True))
        location = Location.objects.filter(pk=location_id, owner=request.user).first()
        if location is None:
            return JsonResponse({"error": "Location not found"}, status=404)
        parent = location.parent
        if "parent_id" in body:
            raw_parent = body["parent_id"]
            parent = _location(request.user, raw_parent) if raw_parent not in (None, "") else None
            if raw_parent not in (None, "") and parent is None:
                return JsonResponse({"error": "Parent location not found"}, status=400)
            if parent is not None and parent.id in _descendant_ids(request.user, location.id):
                return JsonResponse({"error": "A location cannot go inside itself or a location it contains"}, status=400)
        new_name = name.strip() if "name" in body else location.name
        if Location.objects.filter(owner=request.user, parent=parent, name__iexact=new_name).exclude(pk=location.id).exists():
            return JsonResponse({"error": "Location already exists here"}, status=409)
        # Paper copies keep their location id and movement history; only the displayed path changes.
        location.name = new_name
        location.parent = parent
        location.save(update_fields=["name", "parent"])
    return JsonResponse(location_json(location))


@require_http_methods(["PATCH", "DELETE"])
def location_detail(request, location_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    if request.method == "PATCH":
        return _update_location(request, location_id)
    with transaction.atomic():
        location = Location.objects.select_for_update().filter(pk=location_id, owner=request.user).first()
        if location is None:
            return JsonResponse({"error": "Location not found"}, status=404)
        if location.children.exists():
            return JsonResponse({"error": "Move or delete the locations inside this one first"}, status=409)
        stored = location.physical_copies.all()
        if stored.filter(document__trashed_at__isnull=True).exists():
            return JsonResponse({"error": "Move the paper copies stored here to another location first"}, status=409)
        if stored.exists():
            return JsonResponse({"error": "Paper copies of documents in Trash are still recorded here. Restore and move them, or empty Trash, first"}, status=409)
        try:
            location.delete()
        except ProtectedError:
            return JsonResponse({"error": "Move copies or child locations first"}, status=409)
    return JsonResponse({"deleted": True})


def _code_filter(typed, prefix):
    """Match a sticker code as printed, or typed without its "R-" / "L-" prefix or the hyphen ("MUD3PLDT", "RMUD3PLDT")."""
    typed = typed.strip()
    bare = typed.replace("-", "").replace(" ", "")
    choices = Q(sticker_code__iexact=typed) | Q(sticker_code__iexact=prefix + bare)
    if bare[:1].casefold() == prefix[0].casefold():
        choices |= Q(sticker_code__iexact=prefix + bare[1:])
    return choices


@require_http_methods(["GET"])
def location_lookup(request, sticker_code):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    location = Location.objects.filter(_code_filter(sticker_code, "L-"), owner=request.user).select_related("parent__parent").first()
    if location is None:
        return JsonResponse({"error": "Location sticker not found"}, status=404)
    ids = _descendant_ids(request.user, location.id)
    copies = PhysicalCopy.objects.filter(location_id__in=ids, document__owner=request.user, document__trashed_at__isnull=True)
    counts = copies.aggregate(
        total=Count("id", filter=Q(missing_at__isnull=True)),
        missing_count=Count("id", filter=Q(missing_at__isnull=False)),
    )
    present = copies.filter(missing_at__isnull=True).select_related("document", "location__parent__parent").order_by("sticker_code")
    missing = copies.filter(missing_at__isnull=False).select_related("document", "location__parent__parent").order_by("sticker_code")
    cursor = request.GET.get("cursor", "")
    missing_cursor = request.GET.get("missing_cursor", "")
    if any(value and not re.fullmatch(r"R-[A-Z0-9]{8}", value) for value in (cursor, missing_cursor)):
        return JsonResponse({"error": "Invalid container page cursor"}, status=400)
    if cursor:
        present = present.filter(sticker_code__gt=cursor)
    if missing_cursor:
        missing = missing.filter(sticker_code__gt=missing_cursor)
    page = list(present[:51])
    visible = page[:50]
    missing_page = list(missing[:51])
    missing_visible = missing_page[:50]
    return JsonResponse({
        "location": location_json(location),
        "copies": [{"copy": copy_json(copy), "document": {"id": str(copy.document_id), "title": copy.document.title}} for copy in visible],
        "next_cursor": visible[-1].sticker_code if len(page) > 50 else None,
        "missing_copies": [{"copy": copy_json(copy), "document": {"id": str(copy.document_id), "title": copy.document.title}} for copy in missing_visible],
        "missing_next_cursor": missing_visible[-1].sticker_code if len(missing_page) > 50 else None,
        **counts,
    })


LABEL_PATH_LIMIT = 60
DEFAULT_NOTES = set(Movement.Kind.labels)

# Sticker sheet geometry: 70 x 40 mm, 3 mm padding, 30 mm QR code, 3 mm gap -> 31 mm wide text column.
# The code never wraps: its font size is computed from Arial Bold advance widths so it fits the column.
LABEL_CSS = (
    "@page{size:70mm 40mm;margin:0}"
    "body{margin:0;font-family:Arial,Helvetica,sans-serif;color:#183e32}"
    ".label{box-sizing:border-box;width:70mm;height:40mm;padding:3mm;display:flex;gap:3mm;border:1px solid #bbb;overflow:hidden}"
    "svg{width:30mm;height:30mm;flex:none}"
    ".text{flex:1;min-width:0;display:flex;flex-direction:column;overflow:hidden}"
    ".brand{font-size:7pt;line-height:1.2;font-weight:bold}"
    "h1{font-size:10pt;line-height:1.2;margin:1mm 0 .5mm;overflow:hidden;overflow-wrap:anywhere;"
    "display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3}"
    ".code{line-height:1.2;font-weight:bold;letter-spacing:.02em;white-space:nowrap;flex:none}"
    ".path{font-size:7pt;line-height:1.25;margin-top:1.5mm;overflow:hidden;overflow-wrap:anywhere;"
    "display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3}"
    "@media print{.label{border:0}}"
)


# Arial/Helvetica Bold advance widths (1/1000 em) for sticker code characters; unknown characters count as "W".
_CODE_WIDTHS = {"-": 333, **{digit: 556 for digit in "0123456789"}, **dict(zip(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    (722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611),
))}
LABEL_CODE_WIDTH_MM = 29.0  # 31 mm column minus a safety margin for font substitution


def code_font_pt(code, width_mm=LABEL_CODE_WIDTH_MM, max_pt=12.0):
    ems = sum(_CODE_WIDTHS.get(char, 944) for char in code.upper()) / 1000 + 0.02 * len(code)
    return round(min(max_pt, width_mm / (ems * 0.3528)), 1) if ems else max_pt


def label_path(names, limit=LABEL_PATH_LIMIT):
    """Join a location path for a sticker, dropping outer locations first so the innermost stay readable."""
    if not names:
        return ""
    kept = [names[-1]]
    for name in reversed(names[:-1]):
        if len(" / ".join([name, *kept])) + 4 > limit:
            break
        kept.insert(0, name)
    text = " / ".join(kept)
    if len(text) > limit:
        text = text[-(limit - 1):]
        return "…" + text
    return ("… / " if len(kept) < len(names) else "") + text


def _label_html(title, brand, svg, heading, code, path_names, lang="en"):
    return (
        f'<!doctype html><html lang="{lang}"><meta charset="utf-8"><title>{escape(title)}</title>'
        f"<style>{LABEL_CSS}</style>"
        f'<div class="label">{svg}<div class="text"><div class="brand">{escape(brand)}</div>'
        f'<h1>{escape(heading[:120])}</h1><div class="code" style="font-size:{code_font_pt(code)}pt">{escape(code)}</div>'
        f'<div class="path">{escape(label_path(path_names))}</div></div></div></html>'
    )


@require_http_methods(["GET"])
def location_label(request, location_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    location = Location.objects.filter(pk=location_id, owner=request.user).select_related("parent__parent").first()
    if location is None:
        return JsonResponse({"error": "Location not found"}, status=404)
    address = f"{settings.PUBLIC_ORIGIN.rstrip('/')}/?location={location.sticker_code}"
    qr = segno.make_qr(address, error="m")
    output = io.BytesIO()
    qr.save(output, kind="svg", scale=3, border=2, dark="#183e32")
    svg = output.getvalue().decode("utf-8")
    html = _label_html(display(request, "Ripiano location {0}", location.sticker_code), "ripiano · " + display(request, "location"), svg, location.name,
                       location.sticker_code, location_path(location), lang="it" if wants_italian(request) else "en")
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return response


@transaction.atomic
@require_http_methods(["GET", "POST"])
def document_copies(request, document_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    queryset = Document.objects.select_for_update() if request.method == "POST" else Document.objects
    document = queryset.filter(pk=document_id, owner=request.user, trashed_at__isnull=True).first()
    if document is None:
        return JsonResponse({"error": "Document not found"}, status=404)
    if request.method == "GET":
        return JsonResponse({"copies": [copy_json(copy) for copy in document.physical_copies.select_related("location__parent__parent")]})
    body = _body(request)
    if body is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    location = _location(request.user, body.get("location_id"))
    if body.get("location_id") and location is None:
        return JsonResponse({"error": "Location not found"}, status=400)
    for _ in range(5):
        code = "R-" + "".join(secrets.choice(STICKER_ALPHABET) for _ in range(8))
        try:
            with transaction.atomic():
                copy = PhysicalCopy.objects.create(document=document, sticker_code=code, location=location)
                if location:
                    Movement.objects.create(physical_copy=copy, kind=Movement.Kind.PLACEMENT, to_location=location, moved_by=request.user, note="Initial placement")
                else:
                    Movement.objects.create(physical_copy=copy, kind=Movement.Kind.CREATED, moved_by=request.user, note="Sticker created")
            return JsonResponse(copy_json(copy), status=201)
        except IntegrityError:
            continue
    return JsonResponse({"error": "Could not allocate a sticker code"}, status=503)


@require_http_methods(["PATCH"])
def copy_detail(request, copy_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    body = _body(request)
    if body is None or "location_id" not in body:
        return JsonResponse({"error": "Choose a location or null"}, status=400)
    location = _location(request.user, body["location_id"])
    if body["location_id"] is not None and location is None:
        return JsonResponse({"error": "Location not found"}, status=400)
    note = body.get("note", "")
    if not isinstance(note, str) or len(note) > 300:
        return JsonResponse({"error": "Movement note is too long"}, status=400)
    with transaction.atomic():
        copy = _locked_copy(request.user, copy_id)
        if copy is None:
            return JsonResponse({"error": "Physical copy not found"}, status=404)
        if copy.missing_at:
            return JsonResponse({"error": "Mark this paper copy found before moving it"}, status=409)
        if copy.location_id != (location.id if location else None):
            Movement.objects.create(physical_copy=copy, kind=Movement.Kind.MOVE, from_location=copy.location, to_location=location, moved_by=request.user, note=note.strip())
            copy.location = location
            copy.save(update_fields=["location"])
    return JsonResponse(copy_json(copy))


@require_http_methods(["PATCH"])
def copy_status(request, copy_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    body = _body(request)
    if body is None or not isinstance(body.get("missing"), bool):
        return JsonResponse({"error": "Choose whether the copy is missing"}, status=400)
    note = body.get("note", "")
    if not isinstance(note, str) or len(note.strip()) > 300:
        return JsonResponse({"error": "Status note is too long"}, status=400)
    with transaction.atomic():
        copy = _locked_copy(request.user, copy_id)
        if copy is None:
            return JsonResponse({"error": "Physical copy not found"}, status=404)
        if bool(copy.missing_at) == body["missing"]:
            return JsonResponse({"error": "Paper copy already has this status"}, status=409)
        copy.missing_at = timezone.now() if body["missing"] else None
        copy.save(update_fields=["missing_at"])
        kind = Movement.Kind.MISSING if body["missing"] else Movement.Kind.FOUND
        Movement.objects.create(
            physical_copy=copy, kind=kind,
            from_location=copy.location, to_location=copy.location,
            moved_by=request.user, note=note.strip() or kind.label,
        )
    return JsonResponse(copy_json(copy))


@require_http_methods(["GET"])
def copy_history(request, copy_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    copy = PhysicalCopy.objects.filter(pk=copy_id, document__owner=request.user, document__trashed_at__isnull=True).first()
    if copy is None:
        return JsonResponse({"error": "Physical copy not found"}, status=404)
    return JsonResponse({"movements": [{
        "kind": move.kind,
        "from": location_path(move.from_location),
        "to": location_path(move.to_location),
        # Notes Ripiano wrote itself (the movement kind's label) are shown in the request's language.
        "note": display(request, move.note) if move.note in DEFAULT_NOTES else move.note,
        "at": move.created_at.isoformat(),
        "by": move.moved_by.get_username(),
    } for move in copy.movements.select_related("from_location", "to_location", "moved_by")[:50]]})


@require_http_methods(["GET"])
def sticker_lookup(request, sticker_code):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    copy = PhysicalCopy.objects.filter(_code_filter(sticker_code, "R-"), document__owner=request.user).select_related("document", "location__parent__parent").first()
    if copy is None:
        return JsonResponse({"error": "Sticker not found"}, status=404)
    if copy.document.trashed_at:
        return JsonResponse({"error": "This sticker belongs to a document in Trash. Restore the document to use it again."}, status=410)
    return JsonResponse({"copy": copy_json(copy), "document": {"id": str(copy.document_id), "title": copy.document.title}})


@require_http_methods(["GET"])
def printable_label(request, copy_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    copy = PhysicalCopy.objects.filter(pk=copy_id, document__owner=request.user, document__trashed_at__isnull=True).select_related("document", "location__parent__parent").first()
    if copy is None:
        return JsonResponse({"error": "Physical copy not found"}, status=404)
    address = f"{settings.PUBLIC_ORIGIN.rstrip('/')}/?sticker={copy.sticker_code}"
    qr = segno.make_qr(address, error="m")
    output = io.BytesIO()
    qr.save(output, kind="svg", scale=3, border=2, dark="#183e32")
    svg = output.getvalue().decode("utf-8")
    html = _label_html(display(request, "Ripiano sticker {0}", copy.sticker_code), "ripiano", svg, copy.document.title, copy.sticker_code,
                       location_path(copy.location) or [display(request, "Location not assigned")], lang="it" if wants_italian(request) else "en")
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return response
