# Job controls — final gate review

- `recommendation`: **APPROVE**
- `blockers`: **none**
- `scope`: queued cancellation and linked retry for checksum backups and NAS browse copies only; this is not approval of Ripiano as a whole
- `reportPath`: `.omo/evidence/job-controls-gate-review.md`

## Original intent

Continue Ripiano from Claude's clean checkpoint by closing the declared monitoring gap in a safe, reviewable slice. The selected outcome was to let the archive owner cancel backup and NAS browse-copy work before a worker claims it, and retry failed or cancelled work without rewriting history or presenting a partial output as complete.

## Desired outcome and criteria

| Criterion | Required user-visible / system outcome | Gate result |
| --- | --- | --- |
| JC-1 | Only the instance owner can control these maintenance jobs; NAS browse records remain owner-scoped. | PASS |
| JC-2 | A queued backup or browse copy can be cancelled, and a worker receiving the old message must perform no work. | PASS |
| JC-3 | Running and completed jobs cannot be cancelled or retried through these controls. | PASS |
| JC-4 | A failed or cancelled run can be retried once as a new linked run, preserving the prior record. | PASS |
| JC-5 | A second active NAS browse copy is rejected and concurrent retries cannot create duplicate descendants. | PASS |
| JC-6 | Queue outage and stale-worker states remain visible instead of silently disappearing. | PASS |
| JC-7 | Desktop and mobile controls are readable, keyboard operable, have distinct accessible names, preserve focus after state replacement, and expose full failure details. | PASS |
| JC-8 | Migration, scheduler, docs, and existing backup/browse behavior remain coherent. | PASS |

## User outcome review

The Backups screen now gives the owner `Cancel queued` for work still waiting and `Try again` for failed or cancelled work. The UI explicitly states that active jobs finish safely and cannot be stopped. A retry appears as a separate run, while the API retains its `retry_of` relation. This matches the intended safety model: no attempt is made to interrupt a snapshot or browse tree after it has begun writing.

The reviewed desktop and mobile captures show the failed NAS-copy message in full and a reachable retry action without clipping. The focused browser journey asserts cancellation, retry-row creation, distinct accessible names, focus restoration, and wrapped error text. Its API responses are intentionally mocked for deterministic UI state; backend integration has separate API/worker tests and a recorded local PostgreSQL proof.

## Independent evidence reproduced

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_job_controls.py archive/test_backup.py archive/test_browse_export.py` in `services/api` → **10 passed**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py check` → **no issues**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` → **no changes detected**.
- `npm run build` in `apps/web` → production TypeScript/Vite/PWA build completed successfully.
- Direct inspection confirmed the claim-before-work locks in `archive.tasks.backup_archive` and `archive.tasks.build_browse_export`, owner and run locks in `archive.job_views`, one-to-one retry lineage in migration 0035, and the five-minute backup reconciler registration.
- The executor's separate PostgreSQL check is documented in the QA artifact and UX report: synthetic cancellation, worker no-op, and linked retry passed and the records were removed. This was not rerun because the gate is read-only.
- The executor's final Playwright result is documented as **2 passed** (desktop and mobile). This was not rerun per the gate assignment.

## Artifacts checked

- Production: `services/api/archive/job_views.py`, `models.py`, `tasks.py`, `views.py`, `browse_views.py`, `services/api/ripiano/celery.py`, `urls.py`, `apps/web/src/App.tsx`, `style.css`.
- Migration: `services/api/archive/migrations/0035_backuprun_retry_of_browseexportrun_retry_of_and_more.py`.
- Tests: `services/api/archive/test_job_controls.py`, existing `test_backup.py` and `test_browse_export.py`, `apps/web/e2e/job-controls.spec.ts`.
- Reviews: `.omo/evidence/job-controls-code-review.md`, `.omo/evidence/job-controls-ux-review.md`.
- QA: `qa-artifacts/20261113-job-controls/README.md`, desktop and mobile `browse-job-controls.png`.
- Contract/docs: `README.md`, `docs/FEATURE_PARITY.md`, `docs/CONTINUATION_2026-11-12.md`.

## Direct overfit, slop, and maintenance pass

The unavailable `remove-ai-slops` and `programming` skills were applied directly using the required criteria. The focused tests are behavior-driven: permission boundaries, persisted state transitions, old-message no-op, retry lineage, active-copy exclusion, broker failure, stale reconciliation, focus, and responsive presentation. They are not deletion-only, tautological, or assertions that merely mirror constants. Existing backup and browse tests are reused rather than duplicated.

Production additions are scoped to the two job types in the declared slice. The small duplication between backup and browse action endpoints reflects their different ownership and one-active-copy rules; extracting a generic parser or state machine would add indirection without satisfying another criterion. No untyped escape hatch, speculative normalization, compatibility shim, or unrelated refactor was introduced. The code review report explicitly records the same skill-perspective and overfit/slop coverage.

## Notes and exact evidence gaps

- NOTE: The accessible action name uses a short UUID. It is unique but less friendly than date/time plus a short identifier; no stated criterion requires different wording.
- NOTE: The gate independently reproduced all 10 scoped backend cases. The parent subsequently reran the full API suite after the added running-state test: **167 passed, 6 skipped**.
- NOTE: The browser journey mocks job-control API responses, so it is UI evidence rather than end-to-end backend evidence. Backend behavior is covered separately by the focused Django tests and recorded PostgreSQL proof.
- NOTE: `omo ulw-loop status --json` could not run because the local OMO runtime target is missing. No ULW attempt directory could be resolved, so this report correctly falls back to `.omo/evidence/job-controls-gate-review.md`.
