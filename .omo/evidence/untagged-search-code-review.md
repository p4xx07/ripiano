# Untagged Library search code review

## 2026-11-13 scoped review

**Verdict:** `CLEAR` / **APPROVE**, scoped to the uncommitted `is:tagged` / `is:untagged` query syntax and Overview shortcut.

## Scope inspected

- `services/api/archive/views.py`: parser validation, correlated `DocumentTag` presence query, owner scoping, pagination cursor binding, and sort selection.
- `services/api/archive/test_archive.py`: API coverage for tagged/untagged results, ordinary-word combination, split-source and trash exclusion, foreign-owner isolation, and invalid syntax.
- `apps/web/src/OverviewPanel.tsx` and `apps/web/src/App.tsx`: optional Overview-to-Library navigation and query reset.
- `apps/web/e2e/untagged-search.spec.ts` and `docs/FEATURE_PARITY.md`.
- Existing `services/api/archive/stats_views.py`: verified that the Overview count uses the same `DocumentTag`-link definition as `is:untagged`.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Correctness notes

- The document queryset is owner-scoped before the tag-presence correlated subquery, so another account's tags or documents cannot affect results.
- The query also retains the established exclusion of trashed documents and separator-scan source documents in the Library.
- The raw query is part of the signed cursor. `is:untagged` therefore cannot reuse a cursor issued for a different search. Existing field-only cursor coverage exercises the same clauses-only ordering path.
- `SavedSearchBar` persists its regular `query` field without a special case, so either presence query can be saved and reopened through the existing contract.
- The Overview link clears unrelated filters and selects the optional query; it does not create a new mandatory inbox or mutate document metadata.

## Independent verification

- `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_archive.py -q` from `services/api`: **29 passed**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py check`: **passed**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`: **No changes detected**.
- `git diff --check`: **passed**.
- Inspected the executor's reported full API run (**169 passed, 6 skipped**), PWA build, and desktop/mobile Playwright run (**2 passed**) as supporting evidence. The focused API run above was reproduced independently.

## Skill-perspective check

The advertised `remove-ai-slops` and `programming` skill files were not present in the listed local skill roots, so their stated criteria were applied directly. The API test covers observable behavior and ownership boundaries rather than implementation constants; the browser test exercises the actual Overview-to-Library path at both viewport profiles. The production code introduces one bounded field validator and one correlated existence predicate, both required by the query feature. I found no deletion-only or tautological test, brittle prompt test, untyped escape hatch, needless abstraction, or unnecessary production parsing/normalization.

## Blockers

None.
