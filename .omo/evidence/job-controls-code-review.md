# Job controls — code review

**Scope reviewed:** uncommitted task controls for queued backup and NAS browse runs: cancellation, retry lineage, worker claim checks, recovery scheduling, API permissions, migration, UI contract, and tests.

**Skill-perspective check:** The required `remove-ai-slops` and `programming` skill directories were searched under the available Codex and agent skill roots but were unavailable in this environment. I applied their stated review criteria directly. The production diff stays bounded to the task-control state and does not introduce needless parsing, normalization, abstractions, or untyped escape hatches. The tests exercise observable state transitions and worker behavior; they are not deletion-only, tautological, or mere copies of implementation constants.

## Evidence inspected

- Scoped API tests run independently: `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_job_controls.py archive/test_backup.py archive/test_browse_export.py` → **9 passed**.
- Parent evidence for the full API suite reports **166 passed, 6 skipped**; it is consistent with the scoped run but was not used as the sole basis for this review.
- `manage.py check` reported no issues.
- Migration `0035_backuprun_retry_of_browseexportrun_retry_of_and_more` has the expected dependency and operations.
- Browser evidence was reported separately by the executor; this review focused on code and focused test coverage.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Assessment

- `archive/job_views.py:30-52` locks the source backup row before changing or creating retry lineage. The unique one-to-one retry relation plus the row lock prevents two successful retries of one source run in PostgreSQL.
- `archive/job_views.py:62-87` additionally locks the owner for browse-copy operations, matching the existing start endpoint and preserving the one-active-copy invariant.
- `archive/tasks.py:125-138` changes backup claim semantics correctly: a cancelled queued run becomes a worker no-op. This closes the race between a queued Celery message and the user cancellation. Browse already had the equivalent state check.
- `archive/tasks.py:151-164` requeues only older pending backup runs and marks an excessively long running backup as failed. It does not revive cancelled runs.
- The API only permits instance owners, and browse runs additionally remain owner-scoped. Retry failures are persisted as failed records rather than silently disappearing.
- The migration is additive and preserves historical runs. A retry gets a new row linked to its source, retaining audit history.

## Verdict

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- `reportPath`: `.omo/evidence/job-controls-code-review.md`
- `blockers`: None.
