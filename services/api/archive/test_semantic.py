import json
import threading
import zlib
from http.client import HTTPConnection
from http.server import HTTPServer

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive import semantic
from archive.management.commands.semantic_embedder import ModelHolder, make_handler, parse_keep_alive
from archive.models import AgentGrant, Document, SemanticDocument, SemanticSettings, Tag, DocumentTag

WORDS = 64


def fake_vector(text):
    """A bag-of-words vector: texts sharing words are 'close in meaning'."""
    vector = [0.0] * WORDS
    for word in text.lower().replace(",", " ").replace(".", " ").split():
        vector[zlib.crc32(word.encode()) % WORDS] += 1.0
    return vector


@pytest.fixture
def ollama(monkeypatch):
    """Route the embedding client to an in-memory Ollama-compatible endpoint and record requests."""
    calls = []
    real_client = httpx.Client

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"model": body["model"], "embeddings": [fake_vector(text) for text in body["input"]]})

    monkeypatch.setattr(semantic.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    return calls


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_superuser("owner", password="secure-password-1")


@pytest.fixture
def vectors(db):
    """Tests that switch the feature on need pgvector when they run on PostgreSQL."""
    if not semantic.pgvector_available():
        pytest.skip("This PostgreSQL has no pgvector extension")


def doc(owner, title, text, **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path=f"originals/aa/{title}.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=10,
                                   status=Document.Status.READY, extracted_text=text, processed_at=timezone.now(), **values)


def enable(client, **body):
    return client.patch("/api/semantic-settings", {"mode": "ollama", "ollama_url": "http://192.168.1.30:11434", **body}, content_type="application/json")


@pytest.mark.django_db
def test_off_by_default_and_nothing_runs(owner, ollama):
    client = Client()
    client.force_login(owner)
    status = client.get("/api/semantic-settings").json()
    assert status["mode"] == "off" and status["storage_ready"] is False
    assert client.get("/api/semantic-search", {"q": "electricity"}).json() == {"enabled": False, "results": []}
    assert client.get("/api/semantic-search/available").json() == {"enabled": False}
    assert semantic.index_batch() == (0, 0) and ollama == []


@pytest.mark.django_db
def test_enable_index_and_search_by_meaning(vectors, owner, ollama, django_capture_on_commit_callbacks, monkeypatch):
    monkeypatch.setattr("archive.tasks.semantic_index.delay", lambda: None)
    bill = doc(owner, "March bill", "Electricity bill for March. Amount due 84 euro, payment by April 15.")
    doc(owner, "Holiday", "Photos from the beach holiday in Sardinia with friends.")
    doc(owner, "Binned bill", "Electricity bill for May.", trashed_at=timezone.now())
    stranger = get_user_model().objects.create_user("stranger", password="secure-password-2")
    doc(stranger, "Their bill", "Electricity bill for March, amount due.")
    client = Client()
    client.force_login(owner)
    response = enable(client, keep_loaded=True)
    assert response.status_code == 200 and response.json()["storage_ready"] is True
    assert semantic.index_batch()[0] == 3  # owner's two + stranger's one; the binned one is skipped
    assert ollama[0]["model"] == semantic.DEFAULT_OLLAMA_MODEL and ollama[0]["keep_alive"] == -1
    results = client.get("/api/semantic-search", {"q": "how much is the electricity payment"}).json()["results"]
    assert [item["document"]["title"] for item in results][:1] == ["March bill"]
    assert all(item["document"]["title"] not in ("Binned bill", "Their bill") for item in results)
    assert "Electricity bill" in results[0]["passage"]
    # Changed text is indexed again; unchanged documents are not.
    calls = len(ollama)
    assert semantic.index_batch() == (0, 0) and len(ollama) == calls
    Document.objects.filter(pk=bill.pk).update(processed_at=timezone.now() + timezone.timedelta(seconds=5))
    assert semantic.index_batch()[0] == 1
    # Switching the model rebuilds everything with the new model name.
    enable(client, model_name="nomic-embed-text")
    assert semantic.index_batch()[0] == 3 and ollama[-1]["model"] == "nomic-embed-text"
    assert set(SemanticDocument.objects.values_list("model_name", flat=True)) == {"nomic-embed-text"}


@pytest.mark.django_db
def test_endpoint_failures_are_recorded_and_retried_later(vectors, owner, monkeypatch):
    monkeypatch.setattr("archive.tasks.semantic_index.delay", lambda: None)
    doc(owner, "Bill", "Electricity bill")
    client = Client()
    client.force_login(owner)
    enable(client)
    real_client = httpx.Client

    def down(request):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(semantic.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(down), **kwargs))
    assert semantic.index_batch() == (0, 1)
    status = client.get("/api/semantic-settings").json()
    assert "could not be reached" in status["last_error"] and status["documents"]["waiting"] == 1
    assert client.post("/api/semantic-settings/test").status_code == 502
    search = client.get("/api/semantic-search", {"q": "bill"})
    assert search.status_code == 503 and "could not be reached" in search.json()["error"]


@pytest.mark.django_db
def test_settings_are_admin_only_and_validated(vectors, owner):
    person = get_user_model().objects.create_user("person", password="secure-password-2")
    client = Client()
    client.force_login(person)
    assert client.get("/api/semantic-settings").status_code == 403
    assert client.get("/api/semantic-search/available").status_code == 200
    client.force_login(owner)
    assert client.patch("/api/semantic-settings", {"mode": "ollama"}, content_type="application/json").status_code == 400
    assert enable(client, ollama_url="ftp://mac.local").status_code == 400
    assert enable(client, ollama_url="http://user:pw@mac.local:11434").status_code == 400
    assert client.patch("/api/semantic-settings", {"mode": "cloud"}, content_type="application/json").status_code == 400
    nas = client.patch("/api/semantic-settings", {"mode": "nas"}, content_type="application/json").json()
    assert nas["effective_model"] == semantic.DEFAULT_NAS_MODEL
    assert client.patch("/api/semantic-settings", {"mode": "off"}, content_type="application/json").json()["mode"] == "off"


@pytest.mark.django_db
def test_mcp_semantic_search_respects_the_grant_filter(vectors, owner, ollama, monkeypatch):
    from archive.mcp_server import _execute

    monkeypatch.setattr("archive.tasks.semantic_index.delay", lambda: None)
    work = Tag.objects.create(owner=owner, name="Work")
    payslip = doc(owner, "Payslip", "Salary payslip for October, net pay 2100 euro.")
    DocumentTag.objects.create(document=payslip, tag=work)
    doc(owner, "Private salary note", "Salary negotiation notes, net pay wishes.")
    client = Client()
    client.force_login(owner)
    enable(client)
    semantic.index_batch()
    grant = AgentGrant.objects.create(owner=owner, name="Work agent", scopes=["documents:read", "documents:text"], filter_tag=work)
    _, payload = _execute(grant, "semantic_search", {"query": "salary net pay"})
    assert [item["document"]["title"] for item in payload["results"]] == ["Payslip"]
    _, invalid = _execute(grant, "semantic_search", {"query": ""})
    assert "error" in invalid
    client.patch("/api/semantic-settings", {"mode": "off"}, content_type="application/json")
    _, off = _execute(grant, "semantic_search", {"query": "salary"})
    assert off == {"error": "Semantic search is off"}


def test_passages_overlap_and_are_capped():
    text = " ".join(f"Sentence number {i} about the archive." for i in range(400))
    pieces = semantic.passages(text)
    assert all(len(piece) <= semantic.PASSAGE_CHARS for piece in pieces)
    assert pieces[0][-30:] in pieces[1] or pieces[1].split(".")[0] in pieces[0]
    assert semantic.passages("") == [] and len(semantic.passages("x " * 200000)) == semantic.MAX_PASSAGES


def test_keep_alive_follows_ollama_conventions():
    assert parse_keep_alive(None) == 600 and parse_keep_alive("10m") == 600 and parse_keep_alive("1h") == 3600
    assert parse_keep_alive(-1) is None and parse_keep_alive("-1") is None and parse_keep_alive(0) == 0 and parse_keep_alive(30) == 30
    for bad in ("soon", True, "5d"):
        with pytest.raises(ValueError):
            parse_keep_alive(bad)


def test_embedder_loads_on_demand_unloads_when_idle_and_validates_requests():
    loads = []

    class FakeModel:
        def embed(self, texts, batch_size):
            return [fake_vector(text) for text in texts]

    holder = ModelHolder("/tmp/unused", 1, loader=lambda name: loads.append(name) or FakeModel())
    server = HTTPServer(("127.0.0.1", 0), make_handler(holder))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def post(body):
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        raw = json.dumps(body).encode()
        connection.request("POST", "/api/embed", raw, {"Content-Type": "application/json", "Content-Length": str(len(raw))})
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    try:
        status, body = post({"model": model, "input": ["a bill", "a holiday"], "keep_alive": "10m"})
        assert status == 200 and len(body["embeddings"]) == 2 and loads == [model]
        post({"model": model, "input": "another", "keep_alive": "10m"})
        assert loads == [model]  # still loaded
        holder.expires = 0
        holder.unload_if_idle()
        assert holder.model is None
        post({"model": model, "input": ["x"], "keep_alive": 0})
        assert holder.model is None and loads == [model, model]  # keep_alive 0 unloads right away
        assert post({"model": "some/other-model", "input": ["x"]})[0] == 400
        assert post({"model": model, "input": ["x" * 9000]})[0] == 400
        assert post({"model": model, "input": []})[0] == 400
    finally:
        server.shutdown()


@pytest.mark.django_db
def test_database_without_pgvector_refuses_clearly_and_stays_off(owner, monkeypatch):
    monkeypatch.setattr(semantic, "_postgres", lambda: True)
    monkeypatch.setattr(semantic, "pgvector_available", lambda: False)
    monkeypatch.setattr("archive.semantic_views.pgvector_available", lambda: False)
    client = Client()
    client.force_login(owner)
    refused = enable(client)
    assert refused.status_code == 409 and "pgvector/pgvector:pg17" in refused.json()["error"]
    assert SemanticSettings.current().mode == "off"
