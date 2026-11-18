# Round 3 current gate review — 2026-11-18

## Recommendation

**REJECT** the 9.5/release claim for the current working tree. This is an evidence gate result, not a conclusion that the fixes are wrong.

## Original intent

Run Ripiano's documented judge system until the application earns a defensible 9.5/10 release score, while applying owner decision D7: real phone installs/capture, real Telegram/cloud accounts, and DS923+ checks remain owner-side checks and do not lower local judge scores.

## Desired outcome

Three independent running-stack reviews of one candidate commit and representative corpus; mean at least 9.5, every dimension from every judge at least 9.0, no severe unresolved finding, and hard gates 1, 2, 4, and 5 demonstrated locally. D7 is the accepted deviation for hardware/account-only portions of gate 3 and external integrations.

## User outcome review

The available round-three evidence does not establish the desired outcome. Judge 2 scored 8.48 and Judge 3 scored 8.67. A Judge 1 round-three report is absent, although its screenshot directory exists. Both available reports explicitly leave hard gates incomplete. Current uncommitted fixes address the reported medium findings, including the four 320 px overflow cases, and scoped backend and UX reviews approve those fixes. They are newer than the `d8724ff` running candidate and therefore cannot change its scores without a new release-candidate run.

## Blockers

1. **QUALITY-JUDGES / three independent reviews and score threshold**
   - Observation: only `judge-2-round-3-report.md` and `judge-3-round-3-report.md` exist. Their weighted means are 8.48 and 8.67; both contain dimensions below 9.0. Scores cannot be raised by prose or code inspection.
   - Evidence pointer: `.omo/evidence/judge-2-round-3-report.md:34-42`; `.omo/evidence/judge-3-round-3-report.md:10-21`; missing `.omo/evidence/judge-1-round-3-report.md`; `docs/QUALITY_JUDGES.md:25`.

2. **Hard gate 1 / row-by-row parity scenarios or accepted deviation**
   - Observation: both available judges explicitly say row-by-row parity was not verified. `FEATURE_PARITY.md` has 24 capability rows, but no round-three artifact demonstrates every row or records an accepted deviation for every unexercised row.
   - Evidence pointer: `.omo/evidence/judge-2-round-3-report.md:48-54`; `.omo/evidence/judge-3-round-3-report.md:67-73`; `docs/FEATURE_PARITY.md:3,41-43`; `docs/QUALITY_JUDGES.md:7`.

3. **Hard gate 2 / clean restore on the candidate including locations and revoked grants**
   - Observation: the only live restore drill used `f2b9416`, not the round-three candidate or current working tree, and explicitly omitted live checks for locations and revoked grants/permissions.
   - Evidence pointer: `.omo/evidence/restore-drill-20261118.md:3,9-11`; `docs/QUALITY_JUDGES.md:8`; both round-three reports' hard-gate tables.

4. **Hard gate 5 / all verification on one candidate commit**
   - Observation: the running judge candidate is `d8724ff`, while the working tree now contains uncommitted production and test changes. Judge 2 did not run repository suites; Judge 3 did not rerun production builds, full browser journeys, or deployment checks. A dirty working tree has no candidate SHA suitable for the required report.
   - Evidence pointer: `git status --short`; `.omo/evidence/judge-2-round-3-report.md:3,29`; `.omo/evidence/judge-3-round-3-report.md:3,69-73`; `docs/QUALITY_JUDGES.md:11,25`.

## Direct code, test, and overfit review

- The added API regressions are behavior-focused rather than tautological: they exercise active/revoked agent-tag deletion and nested translated error responses through HTTP.
- The accent-search test exercises PostgreSQL and the migration/backfill path. `makemigrations --check --dry-run` reports no model-state drift. The raw search-vector columns intentionally remain database implementation details, matching migration 0055's pattern.
- The browser tests are useful regressions but are not release-score evidence by themselves. The ended-session test stubs `/api/session` and the first upload response, so it proves client queue behavior, not a live server-side session-expiry journey. A new judge must reproduce the real cookie/session scenario on the candidate.
- The 320 px regression now covers all four formerly overflowing screens. Paper and Agents use live regular-account data. People and Backups use read-only intercepted owner-layout fixtures with long Italian content, then assert both page width and exposed descendants. This is sufficient evidence for the CSS/layout defect, while correctly making no authorization or persistence claim.
- No excessive deletion-only, implementation-mirroring, or unnecessary production abstraction was found in the inspected diff.

## Notes, not blockers

- D7 supersedes the older hard-gate wording for local judging: real-device capture, real provider accounts, and DS923+ validation remain open owner-side release checks and should be listed honestly, but should not reduce the local score.
- The current fixes have focused API/PostgreSQL/build/browser evidence described in the active handoff, but that evidence does not replace three fresh independent running-stack reviews.
- The scoped follow-up reports approve the backend and UX diffs, and the recorded verification includes 307 passing SQLite tests, 312 passing PostgreSQL tests, migration-state checks, a production PWA build, and targeted browser journeys. These reduce candidate risk but cannot be transferred into the old judges' scores.
- `omo ulw-loop status --json` could not run because its installed runtime target is missing, so the standard fallback evidence path is used.

## Checked artifacts

- `AGENTS.md`
- `docs/QUALITY_JUDGES.md`
- `docs/DECISIONS.md` (D7/D8)
- `docs/FEATURE_PARITY.md`
- `.omo/evidence/judge-2-round-3-report.md`
- `.omo/evidence/judge-3-round-3-report.md`
- `.omo/evidence/restore-drill-20261118.md`
- `.omo/evidence/judge-round3-followup-20261118.md`
- `.omo/evidence/judge-round3-code-review.md`
- `.omo/evidence/round3-ux-clone-fidelity.md`
- `qa-artifacts/20261118-r3-judge-{1,2,3}/`
- Current `git diff`, including API, migration, PWA, CSS, and regression tests
- Fresh `git diff --check`
- Fresh `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`

## Exact evidence gaps before the next release-score run

1. Commit/build one candidate, then run full API tests, migrations, production builds, browser journeys, and deployment checks on that SHA.
2. Rerun clean-stack restore on that SHA and assert originals, tags, locations, and revoked grants/permissions.
3. Produce the parity row-by-row scenario/deviation audit.
4. Run three independent judges on that same candidate and corpus, producing all three reports with commands, versions, fixture IDs, artifacts, and scores.
