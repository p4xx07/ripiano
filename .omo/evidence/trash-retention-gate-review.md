# Trash retention final gate review

## Recommendation

**APPROVE**

## Blockers

None.

## Original intent

Continue implementing Ripiano toward the Paperless parity plan. This slice closes the remaining Trash-retention gap after manual permanent deletion: automatic cleanup must be optional, understandable before activation, scoped to each owner, and must preserve the existing backup-safe cleanup and retry behavior.

## Desired outcome

- Automatic Trash cleanup is disabled by default.
- An authenticated owner can choose a retention age, see the current eligible count, and explicitly confirm activation.
- The daily maintenance task selects only that owner's expired trashed documents.
- Selected documents become durable purge jobs; media removal remains serialized with snapshots and recoverable after queue failure.
- The owner can disable future automatic selection, while cleanup already durably requested still completes.
- Desktop and mobile present the destructive behavior, schedule, eligible count, and backup-retention limitation clearly.

## User outcome review

The implementation satisfies the intended slice. `TrashRetentionPolicy` is per-owner and defaults disabled. The API validates 30–3650 days and previews eligible items without changing policy. The PWA requires a review step and destructive confirmation, explains the 03:00 Europe/Rome schedule, and distinguishes Trash retention from backup retention. The scheduled task locks the policy and document transactionally, creates the existing durable `PurgeJob`, and delegates file removal to `purge_document`, which holds `backup_media_lock`. Disabling the policy stops later selection without discarding already-created cleanup jobs.

No full-project completion or 9.5 release claim is made. The evidence document explicitly retains the broader parity and real-device/NAS gates.

## Checked artifacts

- Production diff: `services/api/archive/{models.py,purge.py,purge_views.py,tasks.py}`, `services/api/ripiano/{celery.py,settings.py,urls.py}`, `apps/web/src/{TrashPanel.tsx,style.css}`.
- Migration: `services/api/archive/migrations/0024_trashretentionpolicy.py`.
- API tests: `services/api/archive/test_retention.py` and existing `test_purge.py`.
- Browser journey: `apps/web/e2e/trash-retention.spec.ts`.
- UX evidence: `qa-artifacts/20261112-trash-retention/{desktop,mobile}/{confirmation,off}.png`.
- Peer reports: `.omo/evidence/trash-retention-code-review.md` and `.omo/evidence/trash-retention-clone-fidelity.md`.
- Documentation: `README.md`, `docs/{ARCHITECTURE.md,BACKUP_RESTORE.md,FEATURE_PARITY.md,QUALITY_JUDGES.md}`.

## Independent verification

- `RIPIANO_DEBUG=1 uv run pytest -q archive/test_retention.py archive/test_purge.py` — 6 passed.
- `RIPIANO_DEBUG=1 uv run python manage.py makemigrations --check --dry-run` — no changes detected.
- `RIPIANO_DEBUG=1 uv run python manage.py check` — no issues.
- `git diff --check` — clean.
- Visually inspected desktop/mobile confirmation and mobile off-state captures. The dialog remains readable on the narrow viewport, has a clear cancel route, and uses the shared danger action.
- Confirmed the code and UX reports independently inspect the relevant skill perspectives and cite their own reproduced checks.

## Direct slop and programming pass

The named `remove-ai-slops` and `programming` skill files were unavailable under the configured skill roots, so their required criteria were applied directly. The two API tests cover meaningful external behavior: default-off and owner isolation, exact age boundaries, validation, queue outage durability, disabling future retention, physical-copy removal, and live-file cleanup. The browser test covers confirmation, persistence across reload, and disable behavior. They are not deletion-only or implementation-mirroring tests. Production code reuses the established purge protocol instead of adding a parallel deletion system. The small `record_purge` extraction removes duplication between manual and scheduled deletion and is justified by two production callers.

## Notes and exact evidence gaps

- The parent reported a full 64-test API suite, 58 desktop/mobile browser journeys, a live maintenance-queue deletion, and a checksum-verified post-retention snapshot. The full-run terminal logs and live-task output are not stored as standalone files in this slice. This is a traceability note, not a blocker: the focused checks were independently reproduced; screenshots and peer reports exist; and no stated criterion requires archived terminal logs.
- The `omo ulw-loop status --json` runtime is unavailable because its cached CLI target is missing, so the required fallback report location `.omo/evidence/trash-retention-gate-review.md` is used.
