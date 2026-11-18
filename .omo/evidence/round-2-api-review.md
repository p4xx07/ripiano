# Round 2 API review (independent)

Date: 2026-11-18. Reviewer: independent agent. No repository files were edited apart from this report.

## Scope

Uncommitted changes under `services/api` (`git diff -- services/api` plus new files `archive/fulltext.py`,
`archive/migrations/0055_document_search_tsv.py`, `archive/test_round2_language.py`), and the two `App.tsx` lines that send
`X-Ripiano-Client: web` (App.tsx:1218, :1272). Other `apps/web` changes are out of scope.

## Commands and results

| Command | Result |
|---|---|
| `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q -x` (SQLite) | 305 passed, 12 skipped |
| `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_api_contract.py` (SQLite) | 3 passed; `api_contract.py`/`test_api_contract.py` unchanged |
| Disposable `pgvector/pgvector:pg17` on 127.0.0.1:55437, `ALTER USER ripiano CREATEDB`, `RIPIANO_DB_HOST=127.0.0.1 RIPIANO_DB_PORT=55437 ... pytest -q` | 309 passed, 8 skipped |
| Same PG: `pytest -q archive/test_semantic.py` (hybrid search with the stored vector inside subqueries) | 14 passed |
| PG: `manage.py migrate archive 0054`, insert one document, `manage.py migrate`, `select search_tsv is null` | **`t` — existing row NOT backfilled** (see H1) |
| PG: migrate back to 0054 then forward again | column, trigger and functions dropped and recreated cleanly (reversible) |
| PG: Library search probe via test client with `&|!():*'\`, `'`, `\`, `!!`, `a & b`, `foo:*`, `(`, `)`, `<->`, `:`, `*`, 3000-char word, `%`, `_`, `&&&`, `|||`, unicode, 100 words | all 200, no 500 (queries go through `plainto_tsquery` with bound parameters) |
| PG: stemming probe | `rifiuto` finds "rifiuti", `invoice` finds "invoices", `TITOLO:fattura` / `Titolo:Fattura` work |
| PG: 1.95 MB random-word OCR text insert | saved in 0.49 s; tsvector 37 468 lexemes / 780 KB (text truncated, tail word unsearchable — by design) |
| PG: 130 documents, cursor paging for `rifiuto`, `invoice`, `rifiuti luce` × sort relevance/newest/title_asc | every page set complete, no duplicates, matches `counts.total` |
| `docker rm -f ripiano-review-pg` | removed |

## Findings

### High

**H1. Migration 0055 never backfills existing documents; they stay out of full-text search indefinitely.**
`archive/migrations/0055_document_search_tsv.py:51-53` creates the `BEFORE UPDATE` trigger first and then runs
`UPDATE archive_document SET search_tsv = ripiano_document_search_tsv(...)`. That UPDATE does not change title/text/note, so the
trigger takes the branch at line 39 (`NEW.search_tsv := OLD.search_tsv`) and overwrites the computed value with the old NULL.
Verified on PostgreSQL 17: after migrating a database with one existing document, `search_tsv IS NULL` is true. Afterwards only a
change of title, text, or action note fixes a row (status/tag edits and OCR retries that produce the same text keep NULL).
Failure scenario: the owner upgrades the NAS; every document archived before the upgrade stops matching Library free-text
search on title and OCR text (only tag/note/sender/type `icontains` hits remain), and MCP/semantic paths are unaffected, so it
looks like random missing results. Tests did not catch it because the test DB has no rows when migrations run.
Fix: run the backfill `UPDATE` before `CREATE TRIGGER`, or make the trigger recompute when `OLD.search_tsv IS NULL`; add a
migrate-from-0054-with-data test (e.g. `MigrationExecutor` or a `TransactionTestCase` that migrates back and forth).

### Medium

**M1. Migration runs as one transaction holding an ACCESS EXCLUSIVE lock while stemming every document three times.**
Same file, lines 49-53 (after H1 is fixed the backfill actually does work): `ALTER TABLE ... ADD COLUMN` takes an exclusive
lock that is held until the whole `UPDATE` (3 × `to_tsvector` per text, plus a plpgsql exception sub-transaction per row) commits,
and the UPDATE rewrites every row (table temporarily ~doubles until autovacuum). On a NAS with tens of thousands of OCR'd
documents this is minutes of API/worker downtime and a noticeable disk/CPU spike, and the stored vector permanently adds roughly
1–2× the OCR text size to the database. Per AGENTS.md this NAS-load change should be reported to the owner; consider a batched
backfill (management command or `atomic = False` migration with chunks) and noting the expected size growth in the release notes.

### Low

- **L1. Italian/case-insensitive field names turn pasted text into errors.** `archive/search_syntax.py:28,92`. `Data:12/03/2026`
  (an Italian date as it appears in OCR) now returns 400 "Use a date after date:" instead of searching the words; `IS:foo` now
  400s too. Previously both were free text. Consider falling back to free text when an alias-or-uppercase field has an invalid value.
- **L2. No GIN index on `search_tsv`.** The `@@` filter is OR-ed with EXISTS subqueries so an index would not be used today anyway;
  still a sequential scan with TOAST detoasting per row. Much cheaper than the previous on-the-fly `to_tsvector`, so not a regression.
- **L3. Huge OCR text is silently truncated** (`0055:18`, caps 400 000/100 000/20 000 chars): words after the cap are unsearchable,
  with no flag on the document. Acceptable; previously such a document made every PostgreSQL search 500 at query time.
  `EXCEPTION WHEN OTHERS` also hides unrelated errors (e.g. a missing text-search config) as an empty vector.
- **L4. NUL byte in `q` still 500s on PostgreSQL** (`DataError: text fields cannot contain NUL`), in `queryset.aggregate`
  (views.py:581). Pre-existing (the old `icontains`/`SearchQuery` path had the same issue), not introduced here.
- **L5. `os.access` pre-check (folder_source.py:119)** uses the real UID and can be wrong on some CIFS/NFS mounts (ACLs,
  `noperm`, root-squash): a writable share could be reported read-only, so files would import but never move. The no-copy
  guarantee itself is correct (`os.rename` first; EXDEV copy is removed if the unlink fails).
- **L6. Duplicate active agent name check (agent_views.py:73)** has no DB constraint, so two simultaneous POSTs can both pass.
  Cosmetic.
- **L7. MCP guard (mcp_server.py:231)** is checked outside the transaction and still counts expired-but-not-revoked grants;
  both harmless (a grant created mid-call is a race only the owner can cause; expired grants make it stricter).

## Specific questions answered

- **to_tsquery injection / malformed input:** none. `fulltext.search_query` builds only `SearchQuery(..., search_type="plain")`
  → `plainto_tsquery(config, %s)` with bound parameters; all probe strings returned 200. Stopword-only words are handled
  (the `simple` config never drops them and empty sub-queries collapse).
- **Ranking/filters/pagination:** `search_score` is still `SearchRank × 1e6` cast to bigint and used consistently by ordering and
  the signed cursor; paging verified complete/duplicate-free on PG; hybrid tests pass with `StoredSearchVector` relabeled inside
  `pk__in` subqueries. Exact-form hits rank above stem-only hits (more forms match). Filters are applied before the keyword filter
  as before.
- **(d) bypasses:** `set_document_filing` changes only sender/type, writes no tags, and does not run workflows; no MCP tool creates
  tags; `_documents` uses the exact filter tag (no descendants), so child tags do not matter; a second grant sharing the caller's
  own filter tag is still guarded (only the caller's own row is excluded). The caller can remove its own filter tag (narrows only
  itself). No bypass found.
- **(e) member agents:** every MCP query is `owner=grant.owner` (`_documents`, tags, correspondents, types); shared documents
  (DocumentAccess/ObjectAccess) are never included; semantic search filters `owner_id` and is re-checked against `_documents(grant)`;
  audit probe lookups and `/api/agents/events` are owner-scoped; `grant_detail` returns 404 for another person's grant. No
  cross-user leak found. `rip_` API tokens still cannot reach `/api/agents`.
- **(f)** `/api/object-access` is now in `BLOCKED_PREFIXES` (api_tokens.py:18-19), covered by a test.
- **(g) X-Ripiano-Client spoofing:** lookups and the unique constraint are `(owner, source, source_ref)`, so another user's scan IDs
  are unreachable. A client claiming `web` with the same user's Android scan ID just creates a separate WEB document (no collision,
  no data exposure); omitting the header keeps the Android behaviour. Harmless.
- **API contract:** `test_api_contract.py` green on SQLite and PostgreSQL; changes only translate display values (stats "No type",
  copy-history default notes, label pages) and add a 409 for duplicate agent names. No field removed or renamed.

## Verdict

**Not ready to commit as is: fix H1** (one-line reorder in migration 0055 plus a migration-with-existing-data test) and report M1
(migration lock time and DB growth) to the owner. All other changes look correct; no security issue found in (d)–(g), and
full-text query construction is injection-safe and never 500s on malformed operators.

## Resolution (main session, 2026-11-18)

- **H1 fixed:** existing documents never drop out of search. Migration 0055 no longer backfills at all; `fulltext.StoredSearchVector` reads `coalesce(search_tsv, ripiano_document_search_tsv(...))`, so a row without a stored vector is matched on the fly exactly as before the change. The trigger also fills a missing vector on any later edit of the row. Regression test on PostgreSQL: `test_documents_older_than_the_search_index_stay_searchable_and_are_indexed_in_the_background` (migrates back to 0054, creates documents, migrates forward, searches, backfills).
- **M1 fixed:** no long lock and no startup delay. The migration only adds the column, trigger, and a partial index on un-indexed rows (instant on any archive size). `archive.tasks.index_search_text` (maintenance queue, every 5 minutes and self-requeuing) stores vectors 200 documents at a time with `FOR UPDATE SKIP LOCKED`; it is a no-op once done. The disk cost (about twice the text size, roughly 130 MB per 10,000 typical documents) is reported to the owner and documented in docs/USER_GUIDE.md.
- **Verified:** full API suite on SQLite (305 passed, 13 skipped) and PostgreSQL 17 + pgvector (310 passed, 8 skipped: barcode tests without zbar).
- **Low, not changed:** `Data:`/`IS:` now parsed as field names (intended: field names are case-insensitive); no GIN index (the match is OR-combined with tag/sender/note checks, so it would not be used); very large OCR text is truncated for indexing; NUL byte in search text (pre-existing); `os.access` on unusual CIFS/NFS mounts; duplicate agent-name race; MCP tag guard outside the transaction.
