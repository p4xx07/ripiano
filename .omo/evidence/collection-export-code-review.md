# Collection export code review — 12 November 2026

## Decision

**APPROVE**

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- `blockers`: none

## Scope inspected

- `services/api/archive/export_views.py`
- `services/api/ripiano/urls.py`
- `services/api/archive/test_collection_export.py`
- `apps/web/src/App.tsx`
- `apps/web/src/style.css`
- `apps/web/e2e/collection-export.spec.ts`

The route is ordered before the UUID document detail route, validates one to twenty distinct UUIDs, restricts every selected document to the authenticated owner and active archive, retains caller selection order, and fails the complete response if any original is missing or has a changed checksum. The ZIP uses per-document UUID directories, avoiding filename collisions. Reuse of `_write_files` keeps the single-document and collection export file contracts aligned.

## Verification inspected

- Independent focused run: `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_collection_export.py archive/test_export.py` — **3 passed**.
- `git diff --check` — clean.
- The new API test verifies ZIP manifest and bytes, preserved request order, metadata, duplicate/malformed/empty/over-limit selection rejection, Trash and owner isolation, and changed-original rejection.
- The browser journey exercises selection, the download affordance, and a successful ZIP download in both configured desktop and mobile profiles. Its full artifact screenshots are in `qa-artifacts/20261112-collection-export`.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Skill-perspective check

The required `remove-ai-slops` and `programming` skills were searched under the available local skill roots but are unavailable in this environment. I applied their stated review criteria directly. The tests cover user-observable behavior and security boundaries instead of implementation constants; they are not deletion-only or tautological. The production code adds only the validation, packaging, and shared single-file helper required by this endpoint. No needless parsing, normalization, untyped escape hatch, or abstraction was found.
