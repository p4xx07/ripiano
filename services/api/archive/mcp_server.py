"""Scoped MCP transport. Run with uvicorn mcp_asgi:app, never as a public standalone port."""

import hashlib
import json
from uuid import UUID

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from mcp.server import Server
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
from pydantic import AnyHttpUrl

from .models import AgentAudit, AgentGrant, Correspondent, Document, DocumentTag, DocumentType, Tag, TagOverride

TOOLS = {
    "search_documents": (
        "documents:search",
        Tool(name="search_documents", description="Find document titles and filing metadata. OCR text is searched only with the documents:text permission.", inputSchema={
            "type": "object", "properties": {
                "query": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "processing", "ready", "failed"]},
                "offset": {"type": "integer", "minimum": 0},
            }, "additionalProperties": False,
        }),
    ),
    "get_document_text": (
        "documents:text",
        Tool(name="get_document_text", description="Read a page of extracted OCR text from one document.", inputSchema={
            "type": "object", "properties": {
                "document_id": {"type": "string", "format": "uuid"},
                "offset": {"type": "integer", "minimum": 0},
            }, "required": ["document_id"], "additionalProperties": False,
        }),
    ),
    "list_tags": (
        "documents:tag",
        Tool(name="list_tags", description="List tags available for document filing.", inputSchema={"type": "object", "properties": {}, "additionalProperties": False}),
    ),
    "change_document_tags": (
        "documents:tag",
        Tool(name="change_document_tags", description="Add or remove specific tags on one document. Existing unrelated tags stay in place.", inputSchema={
            "type": "object", "properties": {
                "document_id": {"type": "string", "format": "uuid"},
                "add": {"type": "array", "items": {"type": "string", "format": "uuid"}, "maxItems": 20},
                "remove": {"type": "array", "items": {"type": "string", "format": "uuid"}, "maxItems": 20},
            }, "required": ["document_id"], "additionalProperties": False,
        }),
    ),
    "list_filing_options": (
        "documents:filing",
        Tool(name="list_filing_options", description="List existing senders and document types available for filing, 200 of each per page.", inputSchema={
            "type": "object", "properties": {"offset": {"type": "integer", "minimum": 0}}, "additionalProperties": False,
        }),
    ),
    "set_document_filing": (
        "documents:filing",
        Tool(name="set_document_filing", description="Set one existing sender or document type. Human and input-rule choices are protected.", inputSchema={
            "type": "object", "properties": {
                "document_id": {"type": "string", "format": "uuid"},
                "correspondent_id": {"type": "string", "format": "uuid"},
                "document_type_id": {"type": "string", "format": "uuid"},
            }, "required": ["document_id"], "oneOf": [{"required": ["correspondent_id"]}, {"required": ["document_type_id"]}], "additionalProperties": False,
        }),
    ),
}


def _active(grant):
    return bool(grant and grant.revoked_at is None and grant.expires_at and grant.expires_at > timezone.now() and grant.owner.is_active)


class GrantVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        if not token.startswith("rpa_") or len(token) > 100:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()

        @sync_to_async
        def lookup():
            grant = AgentGrant.objects.select_related("owner").filter(token_hash=digest).first()
            if not _active(grant):
                return None
            AgentGrant.objects.filter(pk=grant.pk).update(last_used_at=timezone.now())
            return grant

        grant = await lookup()
        if grant is None:
            return None
        return AccessToken(
            token=token,
            client_id=str(grant.id),
            subject=str(grant.owner_id),
            scopes=grant.scopes,
            expires_at=int(grant.expires_at.timestamp()),
            resource=f"{settings.PUBLIC_ORIGIN.rstrip('/')}/mcp",
        )


def _grant():
    access = get_access_token()
    if access is None:
        return None
    grant = AgentGrant.objects.select_related("owner").filter(pk=access.client_id).first()
    return grant if _active(grant) else None


def _documents(grant):
    queryset = Document.objects.filter(owner=grant.owner, trashed_at__isnull=True, is_split_source=False)
    if grant.filter_tag_id:
        queryset = queryset.filter(tag_links__tag_id=grant.filter_tag_id)
    return queryset


def _uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _result(payload, *, error=False):
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(payload))], structuredContent=payload, isError=error)


def _execute(grant, name, args):
    if not isinstance(args, dict):
        return None, {"error": "Invalid arguments"}
    if name == "search_documents":
        query = args.get("query", "")
        status = args.get("status")
        offset = args.get("offset", 0)
        if not isinstance(query, str) or len(query) > 200 or status not in (None, *Document.Status.values) or not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= 1_000_000:
            return None, {"error": "Invalid query, status, or offset"}
        docs = _documents(grant).select_related("correspondent", "document_type").prefetch_related("tag_links__tag")
        if query:
            if "documents:text" in grant.scopes:
                docs = docs.filter(Q(title__icontains=query) | Q(extracted_text__icontains=query))
            else:
                docs = docs.filter(title__icontains=query)
        if status:
            docs = docs.filter(status=status)
        page = list(docs[offset:offset + 20])
        return None, {"documents": [{
            "id": str(doc.id), "title": doc.title, "status": doc.status,
            "document_date": doc.document_date.isoformat() if doc.document_date else None,
            "tags": [{"id": str(link.tag_id), "name": link.tag.name} for link in doc.tag_links.all()],
            "correspondent": {"id": str(doc.correspondent_id), "name": doc.correspondent.name} if doc.correspondent_id else None,
            "document_type": {"id": str(doc.document_type_id), "name": doc.document_type.name} if doc.document_type_id else None,
        } for doc in page], "next_offset": offset + 20 if len(page) == 20 else None}

    if name == "list_tags":
        return None, {"tags": [{"id": str(tag.id), "name": tag.name, "description": tag.description} for tag in Tag.objects.filter(owner=grant.owner)[:200]]}

    if name == "list_filing_options":
        offset = args.get("offset", 0)
        if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= 1_000_000:
            return None, {"error": "Invalid offset"}
        correspondents = list(Correspondent.objects.filter(owner=grant.owner)[offset:offset + 201])
        types = list(DocumentType.objects.filter(owner=grant.owner)[offset:offset + 201])
        return None, {
            "correspondents": [{"id": str(item.id), "name": item.name} for item in correspondents[:200]],
            "document_types": [{"id": str(item.id), "name": item.name} for item in types[:200]],
            "next_offset": offset + 200 if len(correspondents) > 200 or len(types) > 200 else None,
        }

    document_id = _uuid(args.get("document_id"))
    if document_id is None:
        return None, {"error": "Valid document_id required"}
    document = _documents(grant).filter(pk=document_id).first()
    if document is None:
        return None, {"error": "Document not found within this grant"}

    if name == "get_document_text":
        offset = args.get("offset", 0)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or offset > 10_000_000:
            return document, {"error": "Invalid offset"}
        text = document.extracted_text
        return document, {
            "document_id": str(document.id), "title": document.title,
            "status": document.status, "offset": offset,
            "text": text[offset:offset + 20_000],
            "next_offset": offset + 20_000 if len(text) > offset + 20_000 else None,
        }

    if name == "change_document_tags":
        raw_add, raw_remove = args.get("add", []), args.get("remove", [])
        if not isinstance(raw_add, list) or not isinstance(raw_remove, list) or len(raw_add) > 20 or len(raw_remove) > 20:
            return document, {"error": "Add and remove must be lists of up to 20 IDs"}
        add, remove = {_uuid(value) for value in raw_add}, {_uuid(value) for value in raw_remove}
        if None in add | remove or add & remove:
            return document, {"error": "Invalid or conflicting tag IDs"}
        tags = {tag.id: tag for tag in Tag.objects.filter(owner=grant.owner, pk__in=add | remove)}
        if len(tags) != len(add | remove):
            return document, {"error": "Tag not found"}
        with transaction.atomic():
            document = _documents(grant).select_for_update(of=("self",)).filter(pk=document_id).first()
            if document is None:
                return None, {"error": "Document no longer within this grant"}
            for tag_id in remove:
                DocumentTag.objects.filter(document=document, tag_id=tag_id).delete()
                TagOverride.objects.get_or_create(document=document, tag_id=tag_id)
            suppressed = set(TagOverride.objects.filter(document=document, tag_id__in=add).values_list("tag_id", flat=True))
            for tag_id in add - suppressed:
                DocumentTag.objects.get_or_create(document=document, tag_id=tag_id, defaults={"origin": DocumentTag.Origin.MODEL})
        return document, {"document_id": str(document.id), "added": [str(x) for x in add - suppressed], "suppressed": [str(x) for x in suppressed], "removed": [str(x) for x in remove]}

    if name == "set_document_filing":
        choices = {"correspondent_id": ("correspondent", Correspondent), "document_type_id": ("document_type", DocumentType)}
        provided = [key for key in choices if key in args]
        if len(provided) != 1:
            return document, {"error": "Choose exactly one sender or document type"}
        key = provided[0]
        field, model = choices[key]
        choice_id = _uuid(args[key])
        choice = model.objects.filter(pk=choice_id, owner=grant.owner).first() if choice_id else None
        if choice is None:
            return document, {"error": f"{field.replace('_', ' ').title()} not found"}
        with transaction.atomic():
            document = _documents(grant).select_for_update(of=("self",)).filter(pk=document_id).first()
            if document is None:
                return None, {"error": "Document no longer within this grant"}
            origin_field = f"{field}_origin"
            if getattr(document, origin_field) in (Document.FilingOrigin.MANUAL, Document.FilingOrigin.SOURCE):
                return document, {"error": "A human or input rule already chose this field"}
            setattr(document, field, choice)
            setattr(document, origin_field, Document.FilingOrigin.MODEL)
            document.save(update_fields=[field, origin_field])
        return document, {"document_id": str(document.id), key: str(choice.id), "origin": Document.FilingOrigin.MODEL}

    return None, {"error": "Unknown tool"}


@sync_to_async
def _list_allowed():
    grant = _grant()
    if grant is None:
        return []
    return [tool for scope, tool in TOOLS.values() if scope in grant.scopes]


@sync_to_async
def _call(name, args):
    grant = _grant()
    if grant is None:
        return _result({"error": "Grant expired or revoked"}, error=True)
    required = TOOLS.get(name)
    if required is None or required[0] not in grant.scopes:
        AgentAudit.objects.create(grant=grant, action=name[:60], outcome="denied")
        return _result({"error": "Tool is not permitted for this agent"}, error=True)
    document, payload = _execute(grant, name, args)
    failure = "error" in payload
    AgentAudit.objects.create(grant=grant, action=name, document=document, outcome="error" if failure else "ok")
    return _result(payload, error=failure)


async def list_tools(_ctx, _params):
    return ListToolsResult(tools=await _list_allowed())


async def call_tool(_ctx, params):
    return await _call(params.name, params.arguments or {})


server = Server("ripiano", version="0.1.0", on_list_tools=list_tools, on_call_tool=call_tool)
hosts = [host for host in settings.ALLOWED_HOSTS if host != "*"]
security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=hosts + [f"{host}:*" for host in hosts] + ["mcp", "mcp:*"],
    allowed_origins=[settings.PUBLIC_ORIGIN],
)
app = server.streamable_http_app(
    stateless_http=True,
    json_response=True,
    token_verifier=GrantVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(settings.PUBLIC_ORIGIN),
        resource_server_url=AnyHttpUrl(f"{settings.PUBLIC_ORIGIN.rstrip('/')}/mcp"),
        required_scopes=[],
        validate_token_resource=True,
    ),
    transport_security=security,
)
