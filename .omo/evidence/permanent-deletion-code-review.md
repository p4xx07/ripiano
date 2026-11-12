# Permanent deletion code review

## Scope

Reviewed the uncommitted Trash permanent-deletion slice: durable `PurgeJob` state, owner-only request and retry endpoints, media cleanup, snapshot exclusion, Celery reconciliation, Compose permissions, PWA UX, migration, documentation, and focused tests.

## Evidence inspected

- `git diff --check` completed with no whitespace errors.
- `RIPIANO_DEBUG=1 uv run pytest -q archive/test_purge.py` completed: 4 passed.
- `RIPIANO_DEBUG=1 uv run python manage.py makemigrations --check --dry-run` completed: no changes detected.
- The executor supplied fresh full-suite evidence: 62 API tests and 56 browser journeys passed. This review independently verified the focused deletion suite above.

## Skill-perspective check

The required `remove-ai-slops` and `programming` skill files were not available in the supplied local skill roots (`rg` found no matching `SKILL.md`), so their requested review criteria were applied directly. The production change is scoped to deletion coordination and no needless data extraction, normalization, untyped escape hatch, or abstraction was found. The tests exercise behavior boundaries rather than only implementation constants: owner and Trash guards, snapshot locking, queue recovery, checksum preservation, unsafe paths, storage failure/retry, and the browser confirmation/status path. No overfit or deletion-only test was found.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Decision

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- `blockers`: none

The cleanup holds the same nonblocking backup-volume lock used by snapshotting before unlinking live media. The request deletes only an authenticated owner's trashed document; a durable job retains the required file metadata for retries. Path validation rejects traversal and symlink escapes, the original checksum prevents unlinking a changed file, and failed cleanup remains visible and retryable. Existing snapshot retention is correctly documented as independent of live-media deletion.
