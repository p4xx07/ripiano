# Share-link code review — 12 November 2026

## Decision

**APPROVE**

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- `blockers`: none

## Scope inspected

- `services/api/archive/models.py`
- `services/api/archive/migrations/0025_sharelink.py`
- `services/api/archive/share_views.py`
- `services/api/archive/views.py`
- `services/api/ripiano/urls.py`
- `services/api/archive/test_share_links.py`
- `apps/web/src/ShareLinksPanel.tsx`
- `apps/web/e2e/share-links.spec.ts`

## Independent checks

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_share_links.py archive/test_trash.py` — **7 passed, 1 skipped** (the lock-order test correctly skips on SQLite).
- `docker compose --env-file .env.example exec -T api .venv/bin/pytest -q archive/test_share_links.py` — **3 passed** on the local PostgreSQL container, including the concurrent authorization/revocation test.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` — no changes detected.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py check` — no issues.
- `git diff --check` — clean.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None. The previous authorization/revocation race is fixed. `shared_original()` now locks the document then share in a short atomic transaction, validates both states, checks the checksum, and opens the file before the lock is released ([share_views.py:91](/Users/debotta/dbrepos/ripiano/services/api/archive/share_views.py:91)). Revocation locks the document then share in the same order ([share_views.py:69](/Users/debotta/dbrepos/ripiano/services/api/archive/share_views.py:69)); Trash already obtains the document lock before updating matching shares. The PostgreSQL-only test pauses the public request at the file-open boundary and proves revocation waits, then confirms future access receives 404 ([test_share_links.py:96](/Users/debotta/dbrepos/ripiano/services/api/archive/test_share_links.py:96)). A response whose file descriptor was opened before revocation remains an in-flight download, which is the normal, unavoidable boundary for revocation.

### LOW

None.

## Security and scope observations

- Tokens use 32 random bytes, only a SHA-256 digest is persisted, and the raw URL is returned only on creation. Listing intentionally omits it.
- Owner and active-document filtering correctly protects management endpoints. Expired, revoked, trashed, malformed, foreign, and checksum-mismatched cases are covered.
- The existing `_media_path` validator and original checksum verification prevent path traversal and accidental alternate-file sharing. The public response also sets `no-store`, `no-referrer`, and `nosniff`.
- The selection cap (20 active links) is serialized by the document lock during creation.
- The browser test is user-observable and validates anonymous download bytes and revocation; it is not a brittle implementation-mirroring test. The API tests exercise meaningful authorization/integrity boundaries.

## Skill-perspective check

I searched the configured local skill roots for `remove-ai-slops` and `programming`; neither skill was available, and `omo ulw-loop status --json` could not run because its local runtime target is missing. I applied the requested criteria directly. The production code does not contain needless data extraction, speculative abstraction, untyped escape hatches, or unnecessary parsing beyond the JSON boundary and fixed token grammar. The tests are not deletion-only, tautological, or merely asserting implementation constants. The PostgreSQL concurrency test is narrowly scoped to the authorization boundary and is not implementation-mirroring test noise.
