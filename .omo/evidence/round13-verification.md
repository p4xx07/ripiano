# Round 13 verification — 21 November 2026

Scope: the follow-up to the two medium findings in the three round-12 judge reports. Source branch `codex/initial-implementation`, code candidate `5afee4e` (based on `b51176c`). This is a test and scoped review record, **not** a fresh three-judge numeric score.

## Environment

- Isolated Compose project `ripiano-r13`, fresh PostgreSQL and media volumes for the final browser run; built API image `ripiano-r13-api:local` (`sha256:252a94df69dae12779a070771593c9f25d7ed2bec1d6507237795ef9bc0ae71a`) and current PWA `dist` mounted read-only into Nginx. Converter, OCR worker, maintenance worker, scheduler and MCP service were running.
- HTTP only on `localhost:18113` with `RIPIANO_DEBUG=1`, an ephemeral owner account and random setup/database secrets stored outside the repository under `/private/tmp/ripiano-round13`. The existing fake GreenMail server was temporarily attached to this project's network as `mailtest`; outbound document email used it with SMTP `none` security on port 3025. No real accounts or documents were used.
- Playwright 1.64.1, Google Chrome 157.0.8103.79, desktop 1440×900 and mobile emulation 390×844, two browser workers, one OCR worker.

## Results on the final candidate

| Check | Command / scenario | Result |
| --- | --- | --- |
| API | `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` | **458 passed, 17 skipped**, 73.95 s. Includes the API v1 contract suite. |
| Email suggestion regression | `pytest -q archive/test_classification.py` | **19 passed**. The new test shows that disabling the email filter brings back the wrong tag, sender and type, while the fix removes them and preserves a genuinely related suggestion. |
| Django | `manage.py makemigrations --check --dry-run`; `manage.py check` | No model changes; no system-check issues. |
| Web | `cd apps/web && npx tsc --noEmit -p . && npm run build` | Passed; PWA assets generated. |
| Focused browser | `npx playwright test e2e/judge-round8.spec.ts e2e/judge-round11.spec.ts -g 'offline and waiting-upload notices\|round 12'` | **6 passed** across desktop/mobile: worker down in Library and dialog, Italian member instruction, and the existing two-live-region accessibility contract. |
| Mail and SMTP prerequisites | `npx playwright test e2e/email-intake.spec.ts`; `npx playwright test e2e/sharing.spec.ts` | **2 passed** in each command, desktop/mobile. |
| Full browser, clean stack | `npx playwright test --reporter=line` with isolated origin and owner credentials supplied from a private temporary file | **407 passed, 49 skipped, 0 failed** out of 456, 9.7 min. |
| Real email text shape | Rendered `apps/web/e2e/fixtures/email-notice.eml` with `archive.email_render.render_html`, converted the HTML through Gotenberg/LibreOffice, then ran `pdftotext -layout` | Actual PDF text has `From`, `To`, `Date`, `Subject` labels beside values. The email comparison excludes `famiglia`, `example`, `subject` and keeps `tari`, `lampone`, `contribuente`. The original PDF/OCR path remains unchanged. |

Before the final run, exploratory runs exposed two problems that were resolved and rechecked:

1. A third Library live region broke the existing round-8 accessibility test. The status message now shares the existing first region; the targeted test and full clean run pass.
2. The isolated test stack initially could not reach GreenMail and later lacked the optional document-email SMTP settings. After attaching the fake mail server and enabling fake SMTP, both email journeys passed. The stack was then recreated with empty volumes before the full run.

The independent code review is [round13-fix-code-review.md](round13-fix-code-review.md): CLEAR, no remaining high or medium findings. It found and prompted the fix for a non-owner document dialog that had incorrectly shown an administrator instruction.

## Limits

The 49 browser skips and 17 API skips remain skips, not passes. The UI worker problem test uses a mocked `/api/jobs` response; round-12 judges separately tested a real stopped worker. This round did not repeat a clean-stack backup/restore or every Paperless parity row, nor did it test real phones, providers, a Synology NAS or published images. It does **not** establish a new 9.5 score: that requires three new independent judges on one committed candidate under `docs/QUALITY_JUDGES.md`.
