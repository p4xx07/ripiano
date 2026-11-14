# ASN-only barcode split code review

## Scope

Reviewed the uncommitted ASN-only PDF barcode splitting change. It records ASN pages, splits a first-run PDF at two or more ASN pages while retaining the barcode pages and source scan, prevents a multi-ASN scan from being assigned one arbitrary serial number when it cannot split, and updates the UI, documentation, fixtures, and browser journey.

## Independent verification

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_barcodes.py -q` — **6 passed, 7 skipped** (the skips require Linux zbar).
- Linux zbar targeted test: `docker exec ... pytest archive/test_barcodes.py -q -k 'asn_barcodes_split_a_multi_document_scan'` — **1 passed, 12 deselected**.
- `git diff --check` — passed.
- A full Linux image suite was attempted but the container process was resource-killed after starting (`exit 137`). The focused real-zbar test above then passed.

## Skill-perspective check

The requested `remove-ai-slops` and `programming` skills were not available at the configured skill roots, so I applied their criteria directly. The production change is small and directly serves barcode-page boundaries; no untyped escape hatch, needless abstraction, or unnecessary parsing/normalization was found. The unit tests exercise boundary behavior and the real test decodes generated QR PDFs, so they are not deletion-only, tautological, or solely implementation-mirroring.

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

`codeQualityStatus`: **WATCH**

`recommendation`: **APPROVE**

Scoped score: **9.6 / 10**. The core split ranges are sound, source preservation and first-run guards remain intact, and the real Linux QR path has targeted evidence.

`blockers`: None.

## Re-review

The prior browser-repeatability finding is resolved. `apps/web/e2e/barcodes.spec.ts:69-77` clears the two fixed test ASNs before upload, matching the established pattern in the prior journey. The implementation also handles a single ASN appearing after introductory pages: `asn_split_ranges` returns an initial unnumbered part and an ASN-labelled part, while truncated scans remain unnumbered to avoid guessing about unseen pages.

Fresh verification:

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_barcodes.py -q` — **7 passed, 8 skipped**.
- `git diff --check` — passed.

No new correctness or test-quality finding was identified. The same skill-perspective assessment remains applicable: no slop, needless abstraction, or implementation-mirroring test burden was found.
