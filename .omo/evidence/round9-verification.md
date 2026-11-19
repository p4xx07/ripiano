# Round 9 verification (hard gate 5) — commit 1a365f3

Date: 2026-11-19. Machine: macOS (Darwin 25.6.0), Docker Desktop. Playwright 1.64.1, Chrome channel.

| Check | Command | Result |
| --- | --- | --- |
| API test suite | `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` | `372 passed, 15 skipped in 65.74s` |
| Migrations complete | `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` | `No changes detected` |
| Migration 0061 down/up on a populated database | `manage.py migrate archive 0060` then `manage.py migrate` (local stack, port 18080) | `Unapplying archive.0061… OK`, `Applying archive.0061… OK` |
| Web type check | `cd apps/web && npx tsc --noEmit -p .` | exit 0, no output |
| Web production build | `cd apps/web && npm run build` | exit 0; PWA precache 8 entries (830.29 KiB) |
| Compose build and start | `docker compose --env-file <local env> up -d --build` | all services started; api healthy |
| Browser e2e, desktop + mobile | `RIPIANO_E2E_ORIGIN=http://localhost:18080 … npx playwright test --grep-invert visual` | `257 passed, 1 failed, 42 skipped (9.9m)` |
| Re-run of the one failure | `npx playwright test e2e/judge-round5-api.spec.ts:95` (twice) | `2 passed` both times |
| Clean-stack install → backup → restore | see `restore-drill-round9.md` | PASS, snapshot `20261119T142011471143Z-cfc7e57c` |

## The one e2e failure

`[mobile] judge-round5-api.spec.ts:95` ("resolving all exact copies asks first, then keeps originals and trashes copies") failed once in the full run and passed in both targeted re-runs (desktop and mobile). The config runs 2 workers and both projects use the same e2e account, so the desktop and mobile copies of this test can resolve each other's exact copies at the same time. This is a test-isolation flake, not an application defect; it is listed as an open low item (give each project its own account or serialise this file).

## Skipped tests

The 42 skipped tests are project-specific: tests that only apply to one layout skip on the other project (phone drawer, touch targets and phone layout run only on mobile; keyboard shortcuts and the desktop sidebar only on desktop), and tests that use a shared second account or train a model run once, on desktop. Visual-baseline tests are excluded by `--grep-invert visual`.
