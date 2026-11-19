"""Round-2 judge fixes: language-aware full-text search, Italian search field names, Italian display text."""

import json
import random
import string

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.utils import timezone

from archive.models import Correspondent, Document, DocumentTag, DocumentType, Tag
from archive.search_syntax import parse

postgres_only = pytest.mark.skipif(connection.vendor != "postgresql", reason="stored tsvector search runs on PostgreSQL")


def make(owner, title, text="", **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path=f"originals/{title}.pdf",
                                   original_mime="application/pdf", original_sha256="0" * 64, original_size=1,
                                   status=Document.Status.READY, processed_at=timezone.now(), extracted_text=text, **values)


def signed_in(username="owner"):
    owner = get_user_model().objects.create_user(username, password="secure-password-1")
    client = Client()
    client.force_login(owner)
    return owner, client


def titles(client, q, **extra):
    response = client.get("/api/documents", {"q": q, **extra})
    assert response.status_code == 200, response.json()
    return [item["title"] for item in response.json()["documents"]]


@pytest.mark.django_db
@postgres_only
def test_full_text_matches_italian_and_english_word_forms_and_ranks_exact_words_first():
    owner, client = signed_in()
    make(owner, "Avviso Comune", "Tassa rifiuti 2026: pagamento delle bollette entro marzo.")
    make(owner, "Utility letter", "Your invoices for March are attached.")
    make(owner, "Exact", "Tassa rifiuto per la seconda casa.")
    make(owner, "Unrelated", "Contratto di locazione.")
    assert sorted(titles(client, "tassa rifiuto")) == ["Avviso Comune", "Exact"]
    assert titles(client, "tassa rifiuto")[0] == "Exact"  # the exact word form ranks first
    assert titles(client, "tassa rifiuti")[0] == "Avviso Comune"
    assert titles(client, "bolletta") == ["Avviso Comune"]
    assert titles(client, "invoice") == ["Utility letter"]
    assert titles(client, "il contratto") == ["Unrelated"]  # an Italian stopword does not have to appear
    assert titles(client, "locazione") == ["Unrelated"]
    assert titles(client, "rifiuto", sort="relevance")  # relevance ordering works on the stored vector
    # The snippet shows the stem-sharing word even though the typed form is not in the text.
    response = client.get("/api/documents", {"q": "rifiuto bolletta"}).json()["documents"]
    assert [item["title"] for item in response] == ["Avviso Comune"] and "rifiuti" in response[0]["snippet"]


@pytest.mark.django_db
@postgres_only
def test_library_search_finds_italian_words_without_typed_accents_and_shows_the_phrase():
    owner, client = signed_in()
    make(owner, "Avviso città", "Perché la città richiede più qualità.")
    assert titles(client, "perche") == ["Avviso città"]
    assert titles(client, "citta qualita") == ["Avviso città"]
    assert titles(client, "perché") == ["Avviso città"]
    result = client.get("/api/documents", {"q": "perche"}).json()["documents"][0]
    assert "Perché" in result["snippet"]
    with connection.cursor() as cursor:
        cursor.execute("SELECT search_tsv_version FROM archive_document WHERE id = %s", [result["id"]])
        assert cursor.fetchone()[0] == 2


@pytest.mark.django_db
@postgres_only
def test_stored_vector_follows_text_edits_and_works_inside_subqueries():
    from archive.fulltext import StoredSearchVector, search_query

    owner, client = signed_in()
    document = make(owner, "Lettera", "pagamento affitto")
    assert titles(client, "affitti") == ["Lettera"]
    Document.objects.filter(pk=document.pk).update(extracted_text="ricevuta assicurazione")
    assert titles(client, "affitto") == [] and titles(client, "assicurazioni") == ["Lettera"]
    document.refresh_from_db()
    document.title = "Ricevute auto"
    document.save()
    assert titles(client, "ricevuta auto") == ["Ricevute auto"]
    # Saving without changing the text keeps the vector (and status edits do not drop it).
    Document.objects.filter(pk=document.pk).update(status=Document.Status.READY)
    assert titles(client, "assicurazione") == ["Ricevute auto"]
    inner = Document.objects.annotate(v=StoredSearchVector()).filter(v=search_query("assicurazione")).values("pk")
    assert list(Document.objects.filter(pk__in=inner).values_list("title", flat=True)) == ["Ricevute auto"]


@pytest.mark.django_db
@postgres_only
def test_enormous_text_never_blocks_saving():
    owner, client = signed_in()
    rng = random.Random(7)
    words = " ".join("".join(rng.choices(string.ascii_lowercase, k=10)) for _ in range(150_000))  # > 1 MB of lexemes
    document = make(owner, "Huge scan", "parolachiave " + words)
    with connection.cursor() as cursor:
        cursor.execute("SELECT length(search_tsv) > 0 FROM archive_document WHERE id = %s", [document.pk])
        assert cursor.fetchone()[0] is True
    assert titles(client, "parolachiave") == ["Huge scan"]


def test_italian_field_names_parse_like_english_ones():
    assert parse('mittente:"Comune di Esempio" etichetta:Bollette') == ("", [("sender", "Comune di Esempio"), ("tag", "Bollette")])
    assert parse("data:2026-11 -tipo:Fattura") == ("", [("date", ("2026-11-01", "2026-11-30")), ("-type", "Fattura")])
    assert parse("aggiunto:2026 titolo:affitto testo:rifiuti nota:urgente") == ("", [
        ("added", ("2026-01-01", "2026-12-31")), ("title", "affitto"), ("text", "rifiuti"), ("note", "urgente")])
    assert parse("Tag:Bills SENDER:Enel") == ("", [("tag", "Bills"), ("sender", "Enel")])
    assert parse("nota: parola") == ("nota: parola", [])  # no value: still ordinary words


@pytest.mark.django_db
def test_library_accepts_italian_field_names():
    owner, client = signed_in()
    bills = Tag.objects.create(owner=owner, name="Bollette")
    comune = Correspondent.objects.create(owner=owner, name="Comune di Esempio")
    fattura = DocumentType.objects.create(owner=owner, name="Fattura")
    first = make(owner, "Tassa rifiuti", "importo dovuto", correspondent=comune, document_date="2026-11-10", document_type=fattura)
    DocumentTag.objects.create(document=first, tag=bills)
    make(owner, "Altro", "importo", document_date="2025-01-01")
    assert titles(client, 'mittente:"Comune di Esempio"') == ["Tassa rifiuti"]
    assert titles(client, "etichetta:Bollette") == ["Tassa rifiuti"]
    assert titles(client, "data:2026-11") == ["Tassa rifiuti"]
    assert titles(client, "-tipo:Fattura") == ["Altro"]
    assert titles(client, "testo:dovuto") == ["Tassa rifiuti"]
    assert titles(client, "titolo:altro") == ["Altro"]


@pytest.mark.django_db
def test_display_text_follows_the_request_language():
    owner, client = signed_in()
    make(owner, "Senza tipo")
    english = client.get("/api/overview").json()["by_type"][0]
    italian = client.get("/api/overview", HTTP_ACCEPT_LANGUAGE="it").json()["by_type"][0]
    assert english["name"] == "No type" and italian["name"] == "Nessun tipo"

    document = make(owner, "Contratto")
    box = client.post("/api/locations", json.dumps({"name": "Scatola"}), content_type="application/json").json()
    copy = client.post(f"/api/documents/{document.id}/copies", json.dumps({"location_id": box["id"]}), content_type="application/json").json()
    assert client.get(f"/api/copies/{copy['id']}/history").json()["movements"][0]["note"] == "Initial placement"
    history = client.get(f"/api/copies/{copy['id']}/history", HTTP_ACCEPT_LANGUAGE="it").json()["movements"]
    assert history[0] == {**history[0], "kind": "placement", "note": "Prima collocazione"}
    client.patch(f"/api/copies/{copy['id']}/status", json.dumps({"missing": True}), content_type="application/json")
    assert client.get(f"/api/copies/{copy['id']}/history", HTTP_ACCEPT_LANGUAGE="it").json()["movements"][0]["note"] == "Segnalata come mancante"
    client.patch(f"/api/copies/{copy['id']}/status", json.dumps({"missing": False, "note": "Move"}), content_type="application/json")

    label = client.get(f"/api/copies/{copy['id']}/label", HTTP_ACCEPT_LANGUAGE="it-IT").content.decode()
    assert '<html lang="it">' in label and "Ripiano adesivo" in label
    assert '<html lang="en">' in client.get(f"/api/copies/{copy['id']}/label").content.decode()
    location_label = client.get(f"/api/locations/{box['id']}/label", HTTP_ACCEPT_LANGUAGE="it").content.decode()
    assert '<html lang="it">' in location_label and "ripiano · posizione" in location_label
    tag = client.post("/api/tags", {"name": "Bollette <casa>", "barcode_value": "BOLLETTE"}, content_type="application/json").json()
    tag_label = client.get(f"/api/tags/{tag['id']}/label", HTTP_ACCEPT_LANGUAGE="it").content.decode()
    assert '<html lang="it">' in tag_label and "ripiano · etichetta" in tag_label and "Bollette &lt;casa&gt;" in tag_label
    assert "<casa>" not in tag_label


@pytest.mark.django_db
def test_active_agent_names_are_unique_until_revoked():
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)

    def create(name):
        return client.post("/api/agents", json.dumps({"name": name, "scopes": ["documents:search"], "password": "secure-password-1"}), content_type="application/json",
                           HTTP_ACCEPT_LANGUAGE="it")

    first = create("Mac locale")
    assert first.status_code == 201
    duplicate = create(" mac LOCALE ")
    assert duplicate.status_code == 409 and duplicate.json()["error"] == "Un agente attivo usa già questo nome"
    assert client.delete(f"/api/agents/{first.json()['id']}").status_code == 200
    assert create("Mac locale").status_code == 201  # a revoked grant frees its name


@pytest.mark.django_db
def test_backup_list_never_shows_raw_os_errors_and_follows_the_language():
    from archive.models import BackupRun

    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    client = Client()
    client.force_login(owner)
    BackupRun.objects.create(status=BackupRun.Status.FAILED, error="[Errno 13] Permission denied: '/backup/staging'")
    english = client.get("/api/backups").json()["runs"][0]["error"]
    italian = client.get("/api/backups", HTTP_ACCEPT_LANGUAGE="it").json()["runs"][0]["error"]
    assert english.startswith("Ripiano cannot write to the backup folder") and "Errno" not in english
    assert italian.startswith("Ripiano non può scrivere nella cartella dei backup")


@pytest.mark.django_db(transaction=True)
@postgres_only
def test_documents_older_than_the_search_index_stay_searchable_and_are_indexed_in_the_background():
    """Review finding: after upgrading, existing documents had no stored vector and dropped out of text search."""
    from django.core.management import call_command

    from archive.fulltext import backfill
    from archive.tasks import index_search_text

    def stored(document):
        with connection.cursor() as cursor:
            cursor.execute("SELECT search_tsv IS NOT NULL FROM archive_document WHERE id = %s", [document.id])
            return cursor.fetchone()[0]

    try:
        call_command("migrate", "archive", "0054", verbosity=0)  # the schema before the stored search index
        owner, client = signed_in()
        # Rows written with the model as it was at 0054, so later Document fields do not break this upgrade test.
        from django.db.migrations.executor import MigrationExecutor

        OldDocument = MigrationExecutor(connection).loader.project_state(("archive", "0054_document_date_origin")).apps.get_model("archive", "Document")
        old = [OldDocument.objects.create(
            owner_id=owner.pk, title=f"Vecchia bolletta {index}", original_name="old.pdf", original_path=f"originals/old-{index}.pdf",
            original_mime="application/pdf", original_sha256="0" * 64, original_size=1, status="ready", processed_at=timezone.now(),
            extracted_text="tassa sui rifiuti del comune") for index in range(3)]
        call_command("migrate", "archive", verbosity=0)  # the upgrade to the current schema
        assert not any(stored(item) for item in old)  # migrations index nothing (no long lock on a NAS)
        # The concurrent index step can be retried after a process is interrupted between
        # index creation and Django recording the migration as applied.
        from importlib import import_module
        retry_index = import_module("archive.migrations.0057_accent_backfill_index").forward
        with connection.schema_editor(atomic=False) as schema_editor:
            retry_index(None, schema_editor)
        with connection.cursor() as cursor:
            cursor.execute("SELECT indisvalid FROM pg_index WHERE indexrelid = 'archive_document_search_tsv_old'::regclass")
            assert cursor.fetchone() == (True,)
        # Not indexed yet, but found all the same, including by another word form.
        assert sorted(titles(client, "rifiuto")) == sorted(item.title for item in old)
        new = make(owner, "Nuova bolletta", "tassa sui rifiuti")
        assert stored(new)  # new documents are indexed as they are saved
        # An ordinary edit of an old document indexes it too.
        Document.objects.filter(pk=old[0].pk).update(status=Document.Status.READY)
        assert stored(old[0])
        assert backfill(limit=1) == (1, True)
        assert index_search_text.apply().get() == 1  # the scheduled task finishes the rest
        assert all(stored(item) for item in old) and backfill() == (0, False)
        assert len(titles(client, "rifiuto")) == 4
    finally:
        call_command("migrate", "archive", verbosity=0)
