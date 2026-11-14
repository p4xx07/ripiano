# Configurable tag barcode mapping — code review

## Scope reviewed

Uncommitted changes after `21ede7f`: a per-owner, case-insensitive barcode value on tags; tag-label QR printing; decoding and applying mapped tag codes; TagOverride protection; PWA editing/printing; migration `0038`; fixture and browser coverage; documentation.

## Evidence independently checked

- `git diff --check`: clean.
- Focused backend suite: `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_barcodes.py archive/test_classification.py -q` — **19 passed, 6 skipped**. The skips require zbar, unavailable on the macOS environment.
- Django check and migration drift check — **passed**.
- Examined the executor's current worktree evidence: full API suite **173 passed, 7 skipped**, production PWA build passed, and the desktop/mobile Playwright journey exercised the Linux Docker worker with real QR PDFs.
- Inspected migration `0038`, the API route and generated-schema mechanism, model/export mechanism, scanner, task, label response, PWA type/UI, tests, and current desktop/mobile captures.

## Skill-perspective check

`remove-ai-slops` and `programming` SKILL files were not available under the configured local roots, so their criteria were applied directly. The review found no deletion-only or tautological tests, no test that only mirrors a production constant, no brittle prompt checking, no untyped escape hatch, and no needless abstraction. The small normalization at the API boundary is required for stable case-insensitive uniqueness and matches the scanner's ASCII-bound value domain. The scanner's bounded list and a single database query for configured values are proportionate to decoding untrusted files.

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

The model and migration preserve a blank default for existing archives and enforce owner-local, case-insensitive uniqueness only for nonblank values ([models.py](/Users/debotta/dbrepos/ripiano/services/api/archive/models.py:214), [0038_tag_barcode_value_tag_unique_tag_barcode_owner_ci.py](/Users/debotta/dbrepos/ripiano/services/api/archive/migrations/0038_tag_barcode_value_tag_unique_tag_barcode_owner_ci.py:1)). API validation keeps control codes out of the configurable mapping and exposes only owner-scoped values ([metadata_views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/metadata_views.py:63), [metadata_views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/metadata_views.py:482)). Escaping plus a restrictive CSP protect the printable label.

The worker only queries mapped tags belonging to the document owner, adds the tag with `source` origin, and honors a prior TagOverride ([tasks.py](/Users/debotta/dbrepos/ripiano/services/api/archive/tasks.py:425)). It bounds raw decoded non-control values and avoids loading all account tags per document ([barcodes.py](/Users/debotta/dbrepos/ripiano/services/api/archive/barcodes.py:44)). The tests cover reserved-value validation, owner isolation, label access and escaping, automatic mapping, real decode coverage where zbar is available, manual suppression, and the user-facing journey.

**Scoped score:** 9.7 / 10.

```json
{
  "codeQualityStatus": "CLEAR",
  "recommendation": "APPROVE",
  "reportPath": ".omo/evidence/tag-barcode-code-review.md",
  "blockers": []
}
```
