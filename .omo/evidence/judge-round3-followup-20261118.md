# Round-three judge follow-up — 2026-11-18

Baseline: `d8724ff` on `codex/initial-implementation`. This is a scoped fix and verification record, **not** a 9.5 release score. Claude's available round-three reports: Judge 2 8.48, Judge 3 8.67; Judge 1 report absent.

## Fixed findings and evidence

| Finding | Change | Direct evidence |
| --- | --- | --- |
| J2 M1: accents hide Italian documents | Accent-folded PostgreSQL vector and matching snippets; old vectors searched on demand then backfilled; retryable concurrent index migration | Isolated PostgreSQL accent and 0054→0057 upgrade/retry tests passed; full PG suite 312 passed, 9 skipped |
| J3 M1: ended-session upload lost | Treat 401 as retryable and preserve the selected file for the same signed-in owner | Desktop and mobile browser journey checks re-login and identical scan ID on retry |
| J3 M2: Enter discards new sender/type | Enter invokes inline creation and prevents parent form submit | Desktop and mobile browser journey saves and reopens both values |
| J3 M3: revoked filter traps tag | Active grants produce a specific 409; revoked grants detach before tag deletion | Red/green HTTP regression in `test_agents.py`; full API suites passed |
| J3 M4: nested processing error remains English | Translate nested JSON fields named `error` without changing title or other user content | Red/green HTTP regression in `test_api_language.py`; API contract test passed |
| J2 M2 / J3 M5: tiny mobile controls | 44 px coarse-pointer targets for filing actions, file links, and paper-copy actions | Mobile browser measures the controls |
| J2 M3: 320 px overflow | Targeted min-width, wrapping, and minmax grid tracks | Mobile browser checks Paper/Agents against live regular-account data and People/Backups with read-only Italian owner-layout fixtures; checks page width and exposed descendants |
| J2 low UX | Correct one-file Italian grammar, announce result count and paper move, use dark-theme on-primary skip-link colour | Browser count and paper-move journeys; production web build passed |

## Commands and limits

- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` → 307 passed, 14 skipped.
- Isolated PostgreSQL container, current `archive/` and fixture files, `pytest -q archive` → 312 passed, 9 skipped.
- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` → no changes.
- `cd apps/web && npx tsc --noEmit -p . && npm run build` → pass.
- `cd apps/web && RIPIANO_E2E_ORIGIN=http://localhost:18080 RIPIANO_E2E_LOCAL_DIST=$PWD/dist ... npx playwright test e2e/judge-round3-regressions.spec.ts --workers=1` → 8 passed, 2 skipped; the owner-layout fixture test run separately → 1 passed.

The shared API image was the previous commit. The browser tests served the new PWA at its trusted origin and used a disposable regular account. The People/Backups layout fixture was read-only and did not give that account server privileges. The ended-session browser test injects a 401 to verify queue behavior; a new judge should also test a real expired session on the assembled candidate.

Independent scoped reviews: `judge-round3-code-review.md` (approve), `round3-ux-clone-fidelity.md` (approve), and `round-3-current-gate-review.md` (release claim rejected). No score is transferred to this diff. A candidate commit, clean restore, parity audit, and three fresh running-stack judges remain.
