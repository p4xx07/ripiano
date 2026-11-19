# Bulk operations code review

Reviewed commits: `98c8e9d` and `5016572` on `codex/initial-implementation`.

## Scope

- Bulk OCR retry and searchable-PDF rebuild.
- Atomic bulk Trash and Restore.
- Owner isolation, state transitions, queue recovery, preservation of originals and related records, and desktop/mobile browser journeys.

## Evidence inspected

- `services/api/archive/views.py:575-657`: request validation, owner-scoped row locks, allowed state checks, transactional state changes, and deferred task enqueueing.
- `services/api/archive/test_archive.py:243-313`: unauthorized, cross-owner, Trash, duplicate-ID, allowed-state, original-path, and unavailable-broker cases.
- `services/api/archive/test_trash.py:156-205`: unauthorized, cross-owner, processing, duplicate-ID, atomic rejection, related note/sticker preservation, and restore cases.
- `apps/web/src/App.tsx:508-554,1074-1129` and `apps/web/src/TrashPanel.tsx:48-97`: selection controls, confirmation, notices, refreshes, and disabled busy states.
- `apps/web/e2e/bulk-ocr.spec.ts` and `apps/web/e2e/trash.spec.ts`: browser scenarios for both desktop and mobile projects.

Independent verification run:

```text
RIPIANO_DEBUG=1 uv run pytest -q \
  archive/test_archive.py::test_bulk_ocr_retries_failures_and_rebuilds_ready_documents_without_crossing_owners \
  archive/test_archive.py::test_bulk_ocr_pending_work_survives_an_unavailable_queue \
  archive/test_trash.py::test_bulk_trash_and_restore_are_atomic_owner_scoped_and_preserve_links

3 passed in 1.51s
```

`git diff 98c8e9d^ 5016572 --check` was clean. The worktree was clean during review.

## Skill-perspective check

The required `remove-ai-slops` and `programming` skill files were not available under the configured local skill roots, so their documented criteria from the review instruction were applied directly. The diff does not add deletion-only, tautological, prompt-string, or implementation-mirroring tests; the tests exercise externally observable document state, ownership, state guards, original-byte preservation, and UI paths. Production validation is appropriate at these API boundaries, and no needless abstraction or untyped escape hatch was introduced.

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

`codeQualityStatus`: **CLEAR**

`recommendation`: **APPROVE**

`blockers`: none.

The new endpoints validate the bounded unique UUID input before mutation, lock and owner-scope every selected record, reject incompatible state as a whole batch, and preserve originals and linked records. OCR queue submission occurs after commit; queue delivery failure leaves the document pending for the existing reconciliation task. The review found no correctness or maintenance defect that requires a change.
