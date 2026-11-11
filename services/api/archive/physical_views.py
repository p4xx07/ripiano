import io
import json
import secrets
from uuid import UUID

import segno
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from django.views.decorators.http import require_http_methods

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
        "parent_id": str(location.parent_id) if location.parent_id else None,
        "path": location_path(location), "description": location.description,
    }


def copy_json(copy):
    return {
        "id": str(copy.id), "document_id": str(copy.document_id),
        "sticker_code": copy.sticker_code,
        "location_id": str(copy.location_id) if copy.location_id else None,
        "location_path": location_path(copy.location),
        "created_at": copy.created_at.isoformat(),
    }


def _location(owner, raw_id):
    if raw_id is None:
        return None
    try:
        return Location.objects.filter(pk=UUID(str(raw_id)), owner=owner).first()
    except ValueError:
        return None


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


@require_http_methods(["DELETE"])
def location_detail(request, location_id):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    location = Location.objects.filter(pk=location_id, owner=request.user).first()
    if location is None:
        return JsonResponse({"error": "Location not found"}, status=404)
    try:
        location.delete()
    except ProtectedError:
        return JsonResponse({"error": "Move copies or child locations first"}, status=409)
    return JsonResponse({"deleted": True})


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
                    Movement.objects.create(physical_copy=copy, to_location=location, moved_by=request.user, note="Initial placement")
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
        document_id = PhysicalCopy.objects.filter(pk=copy_id, document__owner=request.user).values_list("document_id", flat=True).first()
        if document_id is None or not Document.objects.select_for_update().filter(pk=document_id, owner=request.user, trashed_at__isnull=True).exists():
            return JsonResponse({"error": "Physical copy not found"}, status=404)
        copy = PhysicalCopy.objects.select_for_update(of=("self",)).filter(pk=copy_id, document__owner=request.user, document__trashed_at__isnull=True).first()
        if copy is None:
            return JsonResponse({"error": "Physical copy not found"}, status=404)
        if copy.location_id != (location.id if location else None):
            Movement.objects.create(physical_copy=copy, from_location=copy.location, to_location=location, moved_by=request.user, note=note.strip())
            copy.location = location
            copy.save(update_fields=["location"])
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
        "from": location_path(move.from_location),
        "to": location_path(move.to_location),
        "note": move.note,
        "at": move.created_at.isoformat(),
    } for move in copy.movements.select_related("from_location", "to_location")[:50]]})


@require_http_methods(["GET"])
def sticker_lookup(request, sticker_code):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    copy = PhysicalCopy.objects.filter(sticker_code__iexact=sticker_code, document__owner=request.user).select_related("document", "location__parent__parent").first()
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
    title = escape(copy.document.title[:70])
    code = escape(copy.sticker_code)
    location = escape(" / ".join(location_path(copy.location)) or "Location not assigned")
    html = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Ripiano sticker {code}</title>
<style>@page{{size:70mm 40mm;margin:0}}body{{margin:0;font-family:Arial,sans-serif;color:#183e32}}.label{{box-sizing:border-box;width:70mm;height:40mm;padding:3mm;display:flex;gap:3mm;border:1px solid #bbb}}svg{{width:30mm;height:30mm;flex:none}}.text{{overflow:hidden}}.brand{{font-size:8pt;font-weight:bold}}h1{{font-size:11pt;margin:2mm 0 1mm;overflow:hidden}}.code{{font-size:13pt;font-weight:bold;letter-spacing:1px}}.location{{font-size:7pt;margin-top:2mm}}</style>
<div class="label">{svg}<div class="text"><div class="brand">ripiano</div><h1>{title}</h1><div class="code">{code}</div><div class="location">{location}</div></div></div></html>"""
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return response
