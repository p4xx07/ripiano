# Missing paper-copy filter — incremental code review

## Scope reviewed

Uncommitted changes after `79fd21f`: accepts `copy_status=missing` in the Library API and saved searches, filters by `PhysicalCopy.missing_at`, exposes the option in the PWA, and adds API/browser coverage.

## Evidence independently checked

- `git diff --check`: clean.
- Focused API suite: `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_archive.py -q` — **30 passed**.
- Django system check and migration dry run — **passed; no changes detected**.
- Supplied execution evidence: complete API suite **171 passed, 6 skipped**; PWA build; desktop/mobile archive Playwright **2 passed**.

## Skill-perspective check

`remove-ai-slops` and `programming` SKILL files remain unavailable in the local skill roots used for the prior review, so their requested criteria were applied directly. This small extension does not add needless parsing, abstraction, or untyped escape hatches. The API and browser tests validate observable behavior rather than internal constants; there are no deletion-only or tautological tests.

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

The new value is accepted consistently by the document endpoint and saved-view boundary ([views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/views.py:324), [metadata_views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/metadata_views.py:173)). `missing` uses a correlated `Exists` condition on `missing_at`, retaining the pre-existing owner scoping from the outer document queryset ([views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/views.py:378)). It is added to the existing signed `filters` payload, so cursors remain bound to the exact state. `SavedView.copy_status` has `max_length=7`, exactly accommodating `missing`.

The semantics are coherent for a document with several physical copies: it appears in “Reported missing” if any copy is missing, while “Has a paper copy” remains a broader registration filter. The PWA labels make that distinction visible, and the browser scenario exercises changing a copy to missing then filtering for it.

**Scoped score:** 9.7 / 10

```json
{
  "codeQualityStatus": "CLEAR",
  "recommendation": "APPROVE",
  "reportPath": ".omo/evidence/paper-missing-filter-code-review.md",
  "blockers": []
}
```
