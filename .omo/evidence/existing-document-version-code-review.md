# Existing-document versioning: code review

Scope reviewed: the uncommitted version-copy API, PWA picker, API shape, docs, focused API tests, and the added Playwright journey.

Final review evidence inspected:

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_versions.py -q`: 9 passed (re-run in this review)
- `RIPIANO_DEBUG=1 ./.venv/bin/python manage.py check`: passed (re-run in this review)
- `npm run build`: passed (re-run in this review)
- Desktop and mobile browser journeys: 2/2 passed, reported by the executor; the added browser assertion was inspected here.

Skill-perspective check: `remove-ai-slops` and `programming` were explicitly searched under the available local skill roots and were unavailable. I applied their stated review criteria directly. The added tests exercise observable preservation, ownership, stale inputs, checksums, revocation, and independent file lifetimes; they are not deletion-only or tautological. The new production code has no untyped escape hatch or needless abstraction. The picker does contain one behavior bug described below.

## Findings

### CRITICAL

None.

### HIGH

None. The previous source-concurrency blocker is fixed: `add_existing_document_version` locks source and target in stable UUID order, reloads the source under lock, validates both versions, and holds the locks through the source copy. The regression at `services/api/archive/test_versions.py:175-187` proves a source changed after the view lookup yields structured `409 stale`.

### MEDIUM

None. The stale source now has its own `source_stale` code. The panel calls `load(true)` for that rejected operation, preserves/reloads the editor, clears the obsolete source selection, and refreshes search results. The browser regression test asserts Page 3 is still visible after the stale alert.

### LOW

None.

## Strengths / scope observations

- Copying through `save_original` gives the target independent bytes and validates its checksum before the target mutation. The API tests correctly demonstrate that removing the source file does not break the target copy.
- Owner filtering in both target and source lookup is present, and the endpoint rejects self, foreign, processing/split, stale, malformed, unavailable, and checksum-modified sources.
- The API test at `services/api/archive/test_versions.py:117-193` is broad but relevant: its no-orphan assertion catches the expected-digest cleanup path.
- The Playwright scenario is an end-to-end proof of the intended desktop interaction and checks target history plus source independence. It does not cover the stale-source recovery finding.

The previous stale-selection and loading findings are fixed. The picker uses `ApiError.data.code`, clears the obsolete choice, refreshes the search, and renders a loading status rather than a false empty-result statement. Source and target staleness now have separate semantics, so a rejected source copy preserves the page editor while a real target change can invalidate it. The Playwright test covers stale-source reselection and page-editor preservation.

## Decision

- `codeQualityStatus`: CLEAR
- `recommendation`: APPROVE
- `score`: 9.8/10 for this implementation slice
- `blockers`: None.
