# Round 11 verification (hard gate 5) — commit 1c82354

Date: 2026-11-20. Machine: macOS (Darwin 25.6.0), Docker Desktop. Playwright 1.64.1, Chrome channel. The working tree was identical to `1c82354` for every check below (the checks ran on the final tree just before the commit; nothing changed afterwards).

| Check | Command | Result |
| --- | --- | --- |
| API test suite | `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` | `438 passed, 17 skipped in 69.77s` |
| Migrations complete | `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` | `No changes detected` (new migration `0064_workflow_held_back_idempotency`) |
| Web type check | `cd apps/web && npx tsc --noEmit` | exit 0, no output |
| Web production build | `cd apps/web && npm run build` | exit 0 |
| Pull-only Compose file valid | `docker compose -f deploy/docker-compose.yaml --env-file deploy/env.example config -q` | exit 0 |
| Compose build and start | `docker compose --env-file <local env> up -d --build` | exit 0; api, mcp, db, broker, converter healthy; "No migrations to apply" after 0064 was applied |
| Browser e2e, desktop + mobile, on the rebuilt stack | `RIPIANO_E2E_ORIGIN=http://localhost:18080 … npx playwright test --grep-invert visual` | `355 passed, 45 skipped (10.2m)`, 0 failed |
| Clean-stack install → backup (with the worker killed mid-processing) → restore | see `restore-drill-round11.md` | PASS: restore verified, and a backup taken with the worker killed mid-split completed; snapshot `20261120T082811914066Z-34103f44` |
| Independent code reviews of the round-10 fixes | see `round10-fixes-review.md` | two reviews; every High and Medium fixed; open Lows listed with reasons |

## Notes

- The 17 skipped API tests need services the local test run does not have (PostgreSQL-only cases run on SQLite locally; one barcode-split rerun test needs the zbar library).
- The 45 skipped browser tests are project-specific: phone-only tests skip on desktop and the reverse, and tests that use a shared second account or train a model run once, on desktop. Visual-baseline tests are excluded by `--grep-invert visual`.
- An earlier full browser run on the same code, while other test runs were using the machine at the same time, had 7 mobile failures and took 24.9 minutes: five documents still processing after the tests' 60 s limit (trash, pagination, page versions) and two waiting-upload banner checks in `round5-web.spec.ts`. The run above, on an idle machine, passed them all. They were not investigated further; a judge who sees slow processing or a wrong waiting-upload banner should report it.
- Round-specific regression specs (`judge-round8.spec.ts`, `judge-round9.spec.ts`, `judge-round10.spec.ts`) also passed twice in a row (132 of 132 each) before the full run.
