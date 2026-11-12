# Ripiano handoff for Claude — 12 November 2026

## Where to work

- Repository: `/Users/debotta/dbrepos/ripiano`. Do all project work here; the old temporary checkout is obsolete.
- Branch: `codex/initial-implementation`, tracking `origin/codex/initial-implementation`.
- Draft PR: https://github.com/p4xx07/ripiano/pull/1. Last pushed checkpoint is `39da90c` (`Add verified NAS browse copies grouped by year and tag`).
- **Do not merge into `main` yet.** The user wants the full Paperless-ngx parity contract and a 9.5 judge result before merge. The PR remains draft.
- The user asked Codex to stop after preparing this handoff. Resume implementation only when the user asks Claude to proceed.

## Product intent and scope

Ripiano is an independent, simpler Paperless-ngx substitute for a Synology NAS/Portainer Compose stack, with an installable PWA, Android native scanning option, searchable tagged documents, physical stickers and locations, scheduled NAS backup output, optional Telegram intake, and named MCP agent grants. A local Mac worker/model can classify through MCP. The user handles Synology Hyper Backup and Backblaze B2 configuration. Keep originals private and preserved; do not make cloud models mandatory. See `docs/PRODUCT_SPEC.md`, `docs/FEATURE_PARITY.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/QUALITY_JUDGES.md`, and `docs/CONTINUATION_2026-11-12.md` for the contract and prior evidence.

## Current working tree: filing suggestions in progress

The working tree has **uncommitted** changes in:

- `services/api/archive/classification.py`, `views.py`, `test_classification.py`; `services/api/ripiano/urls.py`
- `apps/web/src/DocumentPanel.tsx`, `api.ts`, `style.css`; new `apps/web/e2e/filing-suggestions.spec.ts`

The slice adds `GET /api/documents/<id>/filing-suggestions`. It compares a ready document with up to 300 recent documents the same owner filed manually, using bounded title/OCR tokens. It suggests manual tags, correspondents, and document types, shows the source document and shared words, and requires the user to tap a suggestion **and save** before anything changes. It excludes trashed/foreign documents, existing or rejected tags, and fields the owner explicitly set or cleared. No model, cloud request, migration, or automatic change is involved. The similarity value is **not a calibrated confidence score**. The current algorithm requires three shared tokens, divides overlap by the larger token set, and excludes candidates scoring below 80% of the best candidate for that category.

This was tightened after browser screenshots showed generic OCR words causing unrelated suggestions in a reused test account. Inspect the **latest** `apps/web/test-results/*filing-suggestions*/filing-suggestions.png` captures before calling the UX acceptable; they were regenerated after the final scoring change but not yet visually reviewed. The PWA build and API tests passed. A dedicated synthetic local owner named `e2e-filing-suggestions` was used for desktop/mobile browser checks. Do not commit test credentials to the repository.

## Fresh verification from this handoff turn

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q` in `services/api`: **78 passed, 1 skipped**. The skip is an existing PostgreSQL-only concurrency case under SQLite.
- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_classification.py`: **11 passed**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py check`: no issues; `makemigrations --check --dry-run`: no changes detected (run before the final scoring change, which did not change models).
- `npm run build` in `apps/web`: production build passed.
- `npx playwright test e2e/filing-suggestions.spec.ts --workers=2` against the local stack at `http://localhost:18080`: **2 passed** (desktop and mobile) after the final API scoring change.
- `git diff --check` passed before the last scoring/query edits. Re-run before committing.

The **full Playwright suite and scoped code/UX/gate judges have not run on this uncommitted slice**. Do those before treating it as a checkpoint. Do not run separate Playwright commands concurrently: both clear `apps/web/test-results` and have caused trace-file failures in the past.

## Suggested immediate continuation

1. Inspect the uncommitted diff and latest desktop/mobile suggestion screenshots. If generic or unrelated suggestions remain, improve ranking or presentation before accepting the slice. Keep suggestions review-only until reliability is measured on representative documents.
2. Run the full browser suite in isolation, Django migration/system checks, production PWA build, and both Compose config validations. Use a disposable owner account for browser tests; they create documents and metadata.
3. Request the established scoped code, UX, and gate judge review for this slice, record findings under `.omo/evidence`, and fix material issues. The judge system must not be treated as a score for the whole app.
4. Update the relevant parity/continuation docs, capture clean screenshots if useful, then commit and push a checkpoint to the existing draft PR. User authorized periodic commits/pushes. Review CI, including the existing GitGuardian failure for a historical Compose environment placeholder.
5. Continue the open Paperless parity rows and release gates. Current major gaps include incoming email/OAuth, legacy Office/email conversion, barcode/ASN/splitting, file versions/PDF page tools, workflows, broad human permissions/2FA/OIDC, share bundles/email, full export/import, localization, calibrated classification, cross-client hardware and restore validation. Do not claim full completion or merge while these remain.

## Local environment notes

- The local Compose stack is running on port `18080` with synthetic test data. Its API, web, worker, maintenance worker, scheduler, MCP, converter, PostgreSQL, and Valkey containers were running during this handoff. `RIPIANO_PUBLIC_ORIGIN` must match `http://localhost:18080` for browser sign-in; otherwise CSRF origin checks fail.
- `compose.yaml` requires secret environment values. Reuse the existing local environment securely; do not print or commit secrets. Media, database, and backup mounts use the existing named volumes (`ripiano_ripiano_media`, `ripiano_ripiano_postgres`, `ripiano_ripiano_backup`).
- The current PWA/browser screenshots are test output and generally ignored by Git. Prior committed visual evidence lives in `qa-artifacts/` and `.omo/evidence/`.
- For API tests use the project's `services/api/.venv/bin/pytest`, or `uv run pytest`; plain global `pytest` lacks Django here.
