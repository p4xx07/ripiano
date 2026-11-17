# Hybrid Library ranking — code review

**Scope reviewed:** current uncommitted hybrid keyword/semantic Library ranking: `services/api/archive/views.py`, `test_semantic.py`, App integration, removed standalone result panel, styles, and docs. Re-reviewed after the cursor-state revision.

**Skill-perspective check:** The `remove-ai-slops` and `programming` skills were not available in the listed Codex/agent skill roots. I applied their documented criteria directly. The tests exercise observable search behavior, filter authorization, fallback, pagination, and rank order; they are not deletion-only or tautological. The production implementation has no untyped escape hatch or unrelated parsing/normalization.

## Evidence inspected

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_semantic.py archive/test_archive.py` → **42 passed** on the re-review.
- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_semantic.py -k 'library_hybrid'` → **4 passed** after the rank-order test was added.
- The executor reported a web type check and production build, but this review did not treat that as a substitute for the backend behavior checks.
- `git diff --check` completed without whitespace errors.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None. The prior cursor finding is resolved: `views.py:107-127` validates signed, bounded semantic IDs and `:531-543` reuses them on later pages without a model request. `test_semantic.py:277-296` makes a later model call fail if attempted and verifies all 56 results appear once.

### LOW

The former rank-order finding is resolved by `test_semantic.py:299-312`, which verifies that the document present in both lists ranks ahead of keyword-only and semantic-only documents.

1. `semantic.storage_ready()` and a remote embedding request occur synchronously on each eligible Library query (`views.py:506-511`). This is within the feature’s explicit optional cost model, but it should be measured on the DS923+ before an R4 performance claim. No code change is required for this review.

## Verdict

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- `reportPath`: `.omo/evidence/hybrid-library-ranking-code-review.md`
- `blockers`: None.
