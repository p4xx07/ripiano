# Round 10 verification (hard gate 5) — commit 5bc8c7d

Date: 2026-11-19. Machine: macOS (Darwin 25.6.0), Docker Desktop. Playwright 1.64.1, Chrome channel.

| Check | Command | Result |
| --- | --- | --- |
| API test suite | `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` | `400 passed, 17 skipped in 64.86s` |
| Migrations complete | `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` | `No changes detected` |
| Web type check | `cd apps/web && npx tsc --noEmit -p .` | exit 0, no output |
| Web production build | `cd apps/web && npm run build` | exit 0 |
| Pull-only Compose file valid | `docker compose -f deploy/docker-compose.yaml --env-file deploy/env.example config -q` | exit 0 |
| Compose build and start | `docker compose --env-file <local env> up -d --build` | exit 0; api healthy |
| Browser e2e, desktop + mobile, on the rebuilt stack | `RIPIANO_E2E_ORIGIN=http://localhost:18080 … npx playwright test --grep-invert visual` | `305 passed, 45 skipped (10.3m)`, 0 failed |
| Clean-stack install → backup → restore | see `restore-drill-round10.md` | PASS (13 of 13 checks), snapshot `20261119T220106551721Z-244358be` |
| Independent code review of the round-9 fixes | see `round9-fixes-review.md` | 0 High, 2 Medium, 10 Low; resolution table filled in |

## Notes

- The 17 skipped API tests need services that the local test run does not have (PostgreSQL-only cases run on SQLite locally; one barcode-split rerun test needs the zbar library). The PostgreSQL and barcode cases were exercised on a live stack by the fix agents (worker killed mid-OCR: requeued after about 3 minutes, one copy; agents answered again 4 s after a database restart without restarting `mcp`).
- The 45 skipped browser tests are project-specific: phone-only tests skip on desktop and the reverse, and tests that use a shared second account or train a model run once, on desktop. Visual-baseline tests are excluded by `--grep-invert visual`.
- A run on the working tree just before the commit had one failure (`judge-round8.spec.ts:201`, Inbox error focus). The cause was a real race in the app (focus requested before the message rendered); it was fixed in this commit and the three Inbox-related spec files then passed twice in a row (176 of 176) before the full run above.
- In the restore drill, `/healthz` and `/livez` were checked from inside the containers; the path through the published web port was not checked there.
