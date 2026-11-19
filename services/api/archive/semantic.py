"""Optional semantic search: passages, embeddings, and nearest-passage lookup.

Off by default. Ripiano never loads a model itself; it calls an embedding endpoint with Ollama's
`/api/embed` contract — either Ollama on another computer, or the optional `embedder` service on the NAS
(`manage.py semantic_embedder`). Ripiano only finds passages; the MCP client's own model writes answers.

Passages live in a table created when the feature is first enabled. On PostgreSQL it uses the pgvector
extension (exact cosine search, fine for a personal archive). SQLite (development and tests) stores
vectors as JSON and compares them in Python.
"""

import json
import logging
import math
import re

import httpx
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from .models import Document, SemanticDocument, SemanticSettings

logger = logging.getLogger(__name__)

TABLE = "ripiano_semantic_passage"
DEFAULT_NAS_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_OLLAMA_MODEL = "bge-m3"
PASSAGE_CHARS = 1000
PASSAGE_OVERLAP = 150
MAX_PASSAGES = 200
EMBED_BATCH = 16
IDLE_KEEP_ALIVE = "10m"


class SemanticError(Exception):
    """A user-presentable problem (endpoint unreachable, database lacks pgvector, …)."""


# --- configuration ---------------------------------------------------------------

def endpoint(config):
    if config.mode == SemanticSettings.Mode.OLLAMA:
        return config.ollama_url.rstrip("/")
    if config.mode == SemanticSettings.Mode.NAS:
        return settings.RIPIANO_EMBEDDER_URL.rstrip("/")
    return ""


def model_name(config):
    if config.model_name:
        return config.model_name
    return DEFAULT_OLLAMA_MODEL if config.mode == SemanticSettings.Mode.OLLAMA else DEFAULT_NAS_MODEL


def enabled():
    return SemanticSettings.current().mode != SemanticSettings.Mode.OFF


def record_error(message):
    SemanticSettings.objects.filter(pk=1).update(last_error=message[:300], last_error_at=timezone.now())


def clear_error():
    SemanticSettings.objects.filter(pk=1).exclude(last_error="").update(last_error="", last_error_at=None)


# --- passages ----------------------------------------------------------------------

def passages(text):
    """Split text into overlapping passages of about PASSAGE_CHARS characters, preferring sentence ends."""
    text = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text or "")).strip()
    result, start = [], 0
    while start < len(text) and len(result) < MAX_PASSAGES:
        end = min(len(text), start + PASSAGE_CHARS)
        if end < len(text):
            cut = max(text.rfind(". ", start + PASSAGE_CHARS // 2, end), text.rfind("\n", start + PASSAGE_CHARS // 2, end))
            if cut > start:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            result.append(piece)
        if end >= len(text):
            break
        start = max(end - PASSAGE_OVERLAP, start + 1)
    return result


# --- embedding endpoint -----------------------------------------------------------

def embed(config, texts, *, timeout=120):
    """Return one vector per text from the configured endpoint (Ollama `/api/embed` contract)."""
    url = endpoint(config)
    if not url:
        raise SemanticError("Semantic search is off")
    keep_alive = -1 if config.keep_loaded else IDLE_KEEP_ALIVE
    vectors = []
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=5), trust_env=False, follow_redirects=False) as client:
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start:start + EMBED_BATCH]
            try:
                response = client.post(f"{url}/api/embed", json={"model": model_name(config), "input": batch, "keep_alive": keep_alive})
            except httpx.HTTPError as exc:
                raise SemanticError(f"The embedding service at {url} could not be reached") from exc
            if response.status_code != 200:
                detail = ""
                try:
                    detail = str(response.json().get("error", ""))[:120]
                except ValueError:
                    pass
                raise SemanticError(f"The embedding service refused the request ({response.status_code}{': ' + detail if detail else ''})")
            try:
                received = response.json()["embeddings"]
            except (ValueError, KeyError, TypeError) as exc:
                raise SemanticError("The embedding service sent an unexpected answer") from exc
            if not isinstance(received, list) or len(received) != len(batch) or not all(isinstance(item, list) and item for item in received):
                raise SemanticError("The embedding service sent an unexpected answer")
            vectors.extend([[float(value) for value in item] for item in received])
    return vectors


# --- storage ------------------------------------------------------------------------

def _postgres():
    return connection.vendor == "postgresql"


def pgvector_available():
    if not _postgres():
        return True
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        return cursor.fetchone() is not None


def ensure_storage():
    """Create the passage table (and the pgvector extension) the first time the feature is enabled."""
    with connection.cursor() as cursor:
        if _postgres():
            if not pgvector_available():
                raise SemanticError("This PostgreSQL has no pgvector extension. Switch the database image to pgvector/pgvector:pg17 (see the README).")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
                id bigserial PRIMARY KEY,
                document_id uuid NOT NULL REFERENCES archive_document(id) ON DELETE CASCADE,
                owner_id integer NOT NULL,
                position integer NOT NULL,
                body text NOT NULL,
                model varchar(200) NOT NULL,
                embedding vector NOT NULL)""")
        else:
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
                id integer PRIMARY KEY AUTOINCREMENT,
                document_id char(32) NOT NULL REFERENCES archive_document(id) ON DELETE CASCADE,
                owner_id integer NOT NULL,
                position integer NOT NULL,
                body text NOT NULL,
                model varchar(200) NOT NULL,
                embedding text NOT NULL)""")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_owner_model ON {TABLE} (owner_id, model)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_document ON {TABLE} (document_id)")


def storage_ready():
    return TABLE in connection.introspection.table_names()


def _document_key(document_id):
    return document_id if _postgres() else document_id.hex


def _vector_literal(vector):
    return "[" + ",".join(f"{value:.7g}" for value in vector) + "]"


def replace_passages(document, model, pieces, vectors):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {TABLE} WHERE document_id = %s", [_document_key(document.id)])
        rows = [(_document_key(document.id), document.owner_id, position, body, model,
                 _vector_literal(vector) if _postgres() else json.dumps(vector))
                for position, (body, vector) in enumerate(zip(pieces, vectors))]
        if rows:
            placeholder = "(%s, %s, %s, %s, %s, %s::vector)" if _postgres() else "(%s, %s, %s, %s, %s, %s)"
            cursor.executemany(f"INSERT INTO {TABLE} (document_id, owner_id, position, body, model, embedding) VALUES {placeholder}", rows)
        SemanticDocument.objects.update_or_create(document=document, defaults={"model_name": model, "passages": len(rows), "indexed_at": timezone.now()})


def _cosine(left, right):
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


def nearest(owner_id, model, vector, limit):
    """[(document_id, position, body, similarity)] for one owner's passages, best first."""
    with connection.cursor() as cursor:
        if _postgres():
            cursor.execute(f"""
                SELECT p.document_id, p.position, p.body, 1 - (p.embedding <=> %s::vector) AS similarity
                FROM {TABLE} p JOIN archive_document d ON d.id = p.document_id
                WHERE p.owner_id = %s AND p.model = %s AND d.trashed_at IS NULL AND NOT d.is_split_source
                  AND vector_dims(p.embedding) = %s
                ORDER BY p.embedding <=> %s::vector LIMIT %s""",
                [_vector_literal(vector), owner_id, model, len(vector), _vector_literal(vector), limit])
            return [(row[0], row[1], row[2], float(row[3])) for row in cursor.fetchall()]
        cursor.execute(f"""
            SELECT p.document_id, p.position, p.body, p.embedding FROM {TABLE} p JOIN archive_document d ON d.id = p.document_id
            WHERE p.owner_id = %s AND p.model = %s AND d.trashed_at IS NULL AND NOT d.is_split_source""", [owner_id, model])
        import uuid

        scored = [(uuid.UUID(row[0]), row[1], row[2], _cosine(vector, json.loads(row[3]))) for row in cursor.fetchall()]
        return sorted(scored, key=lambda item: -item[3])[:limit]


# --- indexing -------------------------------------------------------------------------

def pending_documents(config):
    """Ready documents whose passages are missing, built with another model, or older than their text."""
    from django.db.models import F, Q

    return (Document.objects.filter(status=Document.Status.READY, trashed_at__isnull=True, is_split_source=False)
            .filter(Q(semantic_index__isnull=True) | ~Q(semantic_index__model_name=model_name(config))
                    | Q(semantic_index__indexed_at__lt=F("processed_at")))
            .order_by("processed_at", "id"))


def index_document(config, document):
    pieces = passages(f"{document.title}\n\n{document.extracted_text}")
    vectors = embed(config, pieces) if pieces else []
    replace_passages(document, model_name(config), pieces, vectors)
    return len(pieces)


def index_batch(limit=20):
    """Index up to ``limit`` waiting documents. Returns (indexed, remaining). Stops quietly when the endpoint is down."""
    config = SemanticSettings.current()
    if config.mode == SemanticSettings.Mode.OFF or not storage_ready():
        return 0, 0
    indexed = 0
    for document in pending_documents(config)[:limit]:
        try:
            index_document(config, document)
        except SemanticError as exc:
            record_error(str(exc))
            return indexed, pending_documents(config).count()
        indexed += 1
    if indexed:
        clear_error()
    return indexed, pending_documents(config).count()


# --- search ---------------------------------------------------------------------------

def search(owner, query, *, allowed=None, limit=10):
    """Best passage per document for a question, most similar first.

    ``allowed`` optionally narrows the documents (an agent grant's filter); it is a Document queryset.
    """
    config = SemanticSettings.current()
    if config.mode == SemanticSettings.Mode.OFF:
        raise SemanticError("Semantic search is off")
    if not storage_ready():
        raise SemanticError("Semantic search is not set up yet")
    vector = embed(config, [query[:2000]], timeout=60)[0]
    candidates = nearest(owner.id, model_name(config), vector, limit * 20)
    ids = {item[0] for item in candidates}
    visible = set((allowed if allowed is not None else Document.objects.filter(owner=owner)).filter(pk__in=ids).values_list("pk", flat=True))
    best = {}
    for document_id, position, body, similarity in candidates:
        if document_id in visible and document_id not in best:
            best[document_id] = (position, body, similarity)
    titles = dict(Document.objects.filter(pk__in=best).values_list("pk", "title"))
    ranked = sorted(best.items(), key=lambda item: -item[1][2])[:limit]
    def shown(body, title):
        # The first passage starts with the title (indexed for context); do not repeat it in results.
        return body[len(title):].lstrip() if title and body.startswith(title) else body

    return [{"document": {"id": str(document_id), "title": titles.get(document_id, "")},
             "passage": shown(body, titles.get(document_id, "")), "position": position, "similarity": round(similarity, 4)}
            for document_id, (position, body, similarity) in ranked]
