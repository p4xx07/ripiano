# Round-2 judge fixes: API side

- **Date:** 2026-11-18
- **Branch:** `codex/initial-implementation`. Not committed.
- **Base report:** `.omo/evidence/judge-2-round-2-report.md`
- **Scope:** `services/api` only. I did not edit `apps/web` or the docs. Docker was used only for a temporary `pgvector/pgvector:pg17` test container (`ripiano-pgtest2` on 127.0.0.1:55434), which has since been removed. Port 55433 was already in use by another project.

## Per-finding status

| Finding | Status | What changed |
| --- | --- | --- |
| M4: no Italian stemming | **Fixed** | Stored language-aware `tsvector` (simple + italian + english), filled by a trigger. Each query word matches in its written, Italian-stemmed or English-stemmed form. |
| M5: "No type" on the Overview | **Fixed (server-side)** | `by_type[].name` is "Nessun tipo" when the request is Italian. |
| M5: "Initial placement" in paper-copy history | **Fixed (server-side)** | Notes Ripiano wrote itself (the movement kind labels "Initial placement", "Move", "Marked missing", "Marked found") are returned in the request language. User notes are returned unchanged. |
| M5: raw `[Errno 13] … '/backup/staging'` | **Fixed (server-side)** | New runs already stored a readable message. The list now also sanitizes legacy rows and translates the message for Italian requests. |
| M5: "Subject" in email search snippets | **Not changed (deliberate)** | The text is the archived document's own content: the rendered email PDF and its OCR text. Translating it would change stored content, and a search for "Subject" would stop working. Only new emails could change. I recommend leaving it as is. |
| M5: trigger "schedule" / OAuth message | **Web-only** | The backend value is `schedule` (default in `BackupRun.trigger`). The web IT map uses the key `scheduled` and should add `schedule`. The OAuth message is hard-coded in `App.tsx:605`. |
| L1: Italian search field names | **Fixed** | See the alias table below. Field names are now case-insensitive (`Tag:` = `tag:`). |
| L2: printable labels served with `lang="en"` | **Fixed** | Sticker, location and tag labels use `lang="it"` and Italian title, brand and "Posizione non assegnata" for Italian requests. |
| L7: duplicate grant names allowed | **Fixed (part)** | Creating an agent whose name matches an active (not revoked, not expired) grant, ignoring case and surrounding spaces, now returns 409 "An active agent already uses this name" / "Un agente attivo usa già questo nome". A revoked name can be reused. Removing revoked grants still needs a UI, so it is not done. |

**JSON shapes:** none changed. All display text is translated on the server with `wants_italian(request)`, the same `Accept-Language` the PWA already sends. `archive/test_api_contract.py` passes, and I did not regenerate `api_contract_v1.json`. **The web needs no change** for M5 Overview, copy history, backup errors, or labels.

## Full-text search design (M4)

- **Before:** every search computed `to_tsvector('simple', …)` on the fly for every document row. There was no stored vector and no index.
- **Now:** migration `0055_document_search_tsv` does the following, on PostgreSQL only. On SQLite it is a no-op, and the dev/test `icontains` fallback is unchanged.
  - Adds column `archive_document.search_tsv tsvector`. It is not a Django model field, so ordinary document queries never load it.
  - Adds the IMMUTABLE function `ripiano_document_search_tsv(title, text, note)`. It builds `setweight(simple||italian||english, A/B/C)` for title, text and note, the same weights as before.
    - If PostgreSQL's 1 MB tsvector limit is hit, it retries with the text cut to 400k, then 100k, then 20k characters, so saving a document never fails. A test covers about 1.6 MB of unique words.
  - Adds a `BEFORE INSERT OR UPDATE` trigger. It re-stems only when `title`, `extracted_text` or `action_note` actually changed, so status, tag and date edits cost nothing extra.
  - Backfills existing rows once.
  - The reverse migration drops the column, trigger and functions; tested with `migrate archive 0054`.
- **Query** (`archive/fulltext.py`):
  - Built per word as `(simple(w) | italian(w) | english(w))`, ANDed across words.
  - The whole query is also ORed with `italian(q) | english(q)`, so stopwords such as "il" or "the" need not appear in the document.
  - Exact word forms match in more than one form, so they rank above stem-only matches. Tested: "tassa rifiuto" ranks the document containing "rifiuto" above the one containing "rifiuti".
  - `StoredSearchVector` is a column expression that relabels correctly inside subqueries (the hybrid keyword+semantic path). Tested.
- **Snippets:** when the typed form isn't in the text (a stemmed hit), the excerpt falls back to the word that shares its stem, so "rifiuto" shows "…rifiuti…".
- **MCP `search_documents`:** unchanged; it still uses `icontains`.
- **Pg dump/restore:** `pg_restore` loads the column data before it creates triggers, so a restore does not re-stem.

### NAS cost (measured on pg17, 5,000 documents of real Italian/English text, about 6.4k characters each, from Django's Italian `.po` catalogs)

| Measure | Before | After |
| --- | --- | --- |
| Keyword search query time (full scan) | 3.6 s (to_tsvector on the fly for every row) | **~30 ms** (stored vector) |
| Extra storage | none | **~13 KB per document** (about 2 bytes per character of text). The total was 62 MB for 5,000 docs, against 16 MB of text. A "simple"-only stored vector would have been 34 MB. |
| Indexes | none | **no new index.** A GIN index wouldn't be used, because the match is ORed with tag/sender/note `EXISTS` checks. |
| Insert/OCR save | none | about 1.8 ms per document of stemming. Updates that don't touch the text: ~0. |
| One-off migration backfill | — | about 1.8 ms per existing document (≈ 20 s per 10k documents) |

- **Always-on processes:** none added. No new image dependency and no RAM change.
- **Owner decision:** the real cost is disk, at about 130 MB per 10,000 average documents. That is small next to the PDFs themselves, but per AGENTS.md I am reporting it. To halve it, the 'english' form could be dropped. English plurals and other inflections would then no longer match, though exact English words still would.

## Italian search field names (L1)

`archive/search_syntax.py` `ALIASES`:

| Italian | Field |
| --- | --- |
| `titolo:` | `title:` |
| `testo:` | `text:` |
| `nota:` | `note:` |
| `etichetta:` | `tag:` |
| `mittente:` | `sender:` |
| `corrispondente:` | `sender:` |
| `tipo:` | `type:` |
| `adesivo:` | `sticker:` |
| `data:` | `date:` |
| `creato:` | `date:` |
| `aggiunto:` | `added:` |
| `campo:` | `field:` |

- Field names are case-insensitive.
- Values such as `is:tagged` keep their English form.
- The search date error message still names `date:`/`added:`.

### Text for docs/USER_GUIDE.md and FEATURE_PARITY (for whoever edits docs)

User guide, "Search" section. Add after the field list:

> **Italian field names.** Every field term also has an Italian name, and you can mix them freely: `titolo:` (title), `testo:` (text), `nota:` (note), `etichetta:` (tag), `mittente:` or `corrispondente:` (sender), `tipo:` (document type), `adesivo:` (sticker), `data:` or `creato:` (document date), `aggiunto:` (date added) and `campo:` (custom field). Field names are not case-sensitive. Example: `mittente:"Comune di Esempio" data:2026-11 -etichetta:Bozze`.
>
> **Word forms.** Plain search words match other forms of the same word in Italian and English: "rifiuto" also finds "rifiuti", "bolletta" finds "bollette", "invoice" finds "invoices". Documents containing the exact word you typed are listed first. Common words such as "il" or "the" don't have to appear in the document. (This needs PostgreSQL, the default for every install.)

Italian user guide / in-app search help (IT): "Puoi usare i nomi dei campi in italiano: `titolo:`, `testo:`, `nota:`, `etichetta:`, `mittente:`, `tipo:`, `adesivo:`, `data:`, `aggiunto:`, `campo:`. La ricerca trova anche le altre forme della parola (rifiuto → rifiuti, bolletta → bollette)."

FEATURE_PARITY search row. Add: "Full-text search is language-aware (Italian + English stemming on a stored tsvector; exact forms rank first); field terms accept Italian names."

**Web follow-up (not done here):** the Italian search help should teach the Italian names instead of `sender:`/`tag:`/`date:`.

## Files changed

- `services/api/archive/fulltext.py` (new): `StoredSearchVector` and `search_query`.
- `services/api/archive/migrations/0055_document_search_tsv.py` (new): column, function, trigger and backfill on PostgreSQL only; reversible.
- `services/api/archive/views.py`:
  - uses the stored vector and the language-aware query (2 places);
  - stem fallback for snippets;
  - `_backup_error` for the backup list.
- `services/api/archive/search_syntax.py`: Italian `ALIASES` and case-insensitive field names.
- `services/api/archive/api_language.py`: `display(request, text, *values)`.
- `services/api/archive/messages_it.py`:
  - new `DISPLAY` dict, appended at the end;
  - one `EXACT` entry for the duplicate agent name.
- `services/api/archive/stats_views.py`: "No type" goes through `display`.
- `services/api/archive/physical_views.py`:
  - copy-history default notes are translated;
  - label `lang`, title and brand follow the request language.
- `services/api/archive/metadata_views.py`: tag label `lang`, title and brand.
- `services/api/archive/agent_views.py`: 409 on a duplicate active agent name.
- `services/api/archive/test_round2_language.py` (new): 8 tests. 3 of them are PostgreSQL-only: stemming and ranking, trigger and subquery, oversized text.

## Verification

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q` (SQLite): **304 passed, 12 skipped**.
- The same suite on PostgreSQL 17 (pgvector image, temporary container): **308 passed, 8 skipped**.
- `manage.py makemigrations --check --dry-run`: **No changes detected**.
- On PostgreSQL, `migrate` forward and `migrate archive 0054` reverse both succeed.
- `archive/test_api_contract.py` passes, with no regeneration (no shape change).

## Independent review

Not done yet. Per AGENTS.md, this slice still needs an independent review recorded in `.omo/evidence/`.
