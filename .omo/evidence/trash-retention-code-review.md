# Trash retention code review

## Scope reviewed

The uncommitted opt-in per-owner Trash-retention slice: policy model and migration, owner API, daily Celery task, the existing durable purge path, PWA controls, documentation, and new focused tests.

## Skill-perspective check

The required `remove-ai-slops` and `programming` skill files were not available under the configured local skill roots. I applied their stated review criteria directly. The production change is scoped to the requirement: it reuses the established `PurgeJob` protocol rather than creating a parallel file-deletion mechanism. The tests exercise externally meaningful behavior (default-off, owner isolation, retention threshold, queue outage recovery, policy disable, browser confirmation/persistence), rather than mirroring implementation details. No needless parsing, abstraction, untyped escape hatch, or tautological/removal-only test was found.

## Evidence independently inspected

- `RIPIANO_DEBUG=1 uv run pytest -q archive/test_retention.py archive/test_purge.py` — **6 passed**.
- `RIPIANO_DEBUG=1 uv run python manage.py makemigrations --check --dry-run` — **No changes detected**.
- `RIPIANO_DEBUG=1 uv run pytest -q archive/test_retention.py` — **2 passed**.
- `RIPIANO_DEBUG=1 uv run python manage.py check` — **no issues**.
- Code review confirmed cleanup reaches `purge_document`, whose shared backup-media lock at `archive/tasks.py:121` serializes live-file removal with snapshots. The daily task is routed to the maintenance queue in `ripiano/settings.py:107` and scheduled in `ripiano/celery.py:22-25`.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Verdict

`codeQualityStatus`: **CLEAR**
`recommendation`: **APPROVE**
`blockers`: None.

The retention task locks the policy before selecting one eligible trashed document (`archive/tasks.py:172-182`), creates a durable cleanup job transactionally via `record_purge`, and delegates media removal to the existing backup-coordinated retry flow. This preserves the key deletion safety property while ensuring a broker outage leaves a reconciled pending job rather than orphaned state.
