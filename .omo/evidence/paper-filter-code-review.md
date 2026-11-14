# Paper-copy Library filter — code review

## Scope reviewed

Uncommitted changes against `6867685`: `SavedView.copy_status` and migration 0037; Library API filtering and signed-cursor binding; saved-view serialization and validation; PWA filter, saved-search persistence, and end-to-end coverage.

## Evidence inspected

- `git diff --check`: clean.
- API focused suite: `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_archive.py -q` — **30 passed**.
- PWA build: `npm run build` — **passed**.
- Existing execution evidence supplied in the worktree context: full API suite **171 passed, 6 skipped** and Playwright desktop/mobile archive flow **2 passed**.

## Skill-perspective check

The required `remove-ai-slops` and `programming` skills were not available in the listed local skill roots (`/Users/debotta/.codex/skills`, `/Users/debotta/.agents/skills`); their `SKILL.md` files could not be consulted. I applied the requested perspectives directly: the change adds no needless parsing/normalization or abstraction, has no untyped escape hatch, and its tests exercise behavior rather than only implementation constants. The test data covers owner isolation, Trash, split sources, missing physical copies, query combination, invalid input, cursor binding, saved-view persistence, and the UI interaction. No deletion-only, tautological, or implementation-mirroring test was found.

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

The API checks `copy_status` at both boundaries, adds it to the signed cursor filter set, and implements the intended existence semantics with a correlated `PhysicalCopy` subquery ([views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/views.py:324), [views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/views.py:378)). The saved-view field is serialized, validated, and retained on partial edits ([metadata_views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/metadata_views.py:149), [metadata_views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/metadata_views.py:165)). The PWA passes the filter to requests and saved searches ([App.tsx](/Users/debotta/dbrepos/ripiano/apps/web/src/App.tsx:755), [SavedSearchBar.tsx](/Users/debotta/dbrepos/ripiano/apps/web/src/SavedSearchBar.tsx:12)).

**Scoped score:** 9.7 / 10

```json
{
  "codeQualityStatus": "CLEAR",
  "recommendation": "APPROVE",
  "reportPath": ".omo/evidence/paper-filter-code-review.md",
  "blockers": []
}
```

## Follow-up review: missing-copy Library summary

Reviewed the incremental `PaperCopySummary` rendering, warning style, and browser scenario. The component filters out copies with `missing_at` before choosing a displayed location, while still explicitly reporting missing copies ([App.tsx](/Users/debotta/dbrepos/ripiano/apps/web/src/App.tsx:131)). This corrects the stale-location presentation without changing API semantics. It also handles a document with both located and missing copies without hiding either state.

The end-to-end test marks the generated copy missing, asserts the warning, and verifies the old location no longer appears in that row ([archive.spec.ts](/Users/debotta/dbrepos/ripiano/apps/web/e2e/archive.spec.ts:129)). This is behavior coverage, not an implementation-mirroring test. `npm run build` and `git diff --check` pass independently for this review.

No new findings. **Scoped score remains 9.7 / 10; `codeQualityStatus: CLEAR`; `recommendation: APPROVE`; blockers: none.**
