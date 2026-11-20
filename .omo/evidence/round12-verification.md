# Round 12 verification (hard gate 5) — commit 71315f4

Date: 2026-11-20. Machine: macOS (Darwin 25.6.0), Docker Desktop. Playwright 1.64.1, Chrome channel. The working tree was identical to `71315f4` for every check below (the checks ran on the final tree just before the commit; nothing changed afterwards).

| Check | Command | Result |
| --- | --- | --- |
| API test suite | `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` | `457 passed, 17 skipped in 71.06s` |
| Migrations complete | `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` | `No changes detected` (new migration `0065_worker_heartbeat_queued_at`) |
| Web type check | `cd apps/web && npx tsc --noEmit` | exit 0, no output |
| Web production build | `cd apps/web && npm run build` | exit 0 |
| Pull-only Compose file valid | `docker compose -f deploy/docker-compose.yaml --env-file deploy/env.example config -q` | exit 0 |
| Compose build and start | `docker compose --env-file <local env> up -d --build` | exit 0; api, mcp, db, broker, converter, worker, maintenance_worker healthy; 0065 applied |
| Browser e2e, desktop + mobile, on the rebuilt stack | `RIPIANO_E2E_ORIGIN=http://localhost:18080 … npx playwright test --grep-invert visual` | `402 passed, 48 skipped (11.1m)`, 0 failed |
| Clean-stack install → backup (with the worker killed mid-processing) → restore | see `restore-drill-round12.md` | PASS: restore verified, and a backup taken with the worker killed mid-split completed; snapshot `20261120T101022109306Z-a58bfa65` |
| Independent code reviews of the round-11 fixes (API and web) | see `round11-fixes-review.md` | two reviews; every High and Medium fixed; open Lows listed with reasons |

## Notes

- The 17 skipped API tests need services the local test run does not have (PostgreSQL-only cases run on SQLite locally; one barcode-split rerun test needs the zbar library).
- The 48 skipped browser tests are project-specific: phone-only tests skip on desktop and the reverse, and tests that use a shared second account or train a model run once, on desktop. Visual-baseline tests are excluded by `--grep-invert visual`.
- A live check on the rebuilt stack stopped the OCR worker and uploaded 3 documents: the OCR queue stayed at 3 messages for 5.5 minutes, `/api/jobs` reported `problem=worker_not_running` from 2 minutes on, and after the worker was started the 3 documents were ready in 10 s, each processed once.
- Round-specific regression specs (`judge-round11.spec.ts`, `judge-round10.spec.ts`) also passed twice in a row before the full run.
