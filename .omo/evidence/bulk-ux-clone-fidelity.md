# Bulk OCR and Trash UX clone-fidelity review

Scope: commits `98c8e9d` and `5016572` in `/Users/debotta/dbrepos/ripiano`.

## Evidence inspected

- `apps/web/src/App.tsx` lines 1107-1126 and 1157-1163.
- `apps/web/src/TrashPanel.tsx` lines 80-96.
- `apps/web/src/style.css` lines 1-154, 728-790, 1293-1337, and 2230-2242.
- Browser-test evidence: `apps/web/test-results/bulk-ocr-rebuild-OCR-for-s-88039-and-preserve-both-originals-desktop/bulk-ocr.png` and its mobile counterpart.
- The Playwright journeys in `apps/web/e2e/bulk-ocr.spec.ts` and `apps/web/e2e/trash.spec.ts`.

## What is verified

- The UI is live React DOM. The new controls use existing `Button` and document-row primitives; no screenshot, canvas, raster background, or generated static markup substitutes for the interaction.
- The controls inherit the shared token-driven system: semantic color, spacing, radius, and typography tokens in `style.css`; the new UI does not introduce one-off visual values.
- The desktop and mobile OCR screenshots show a coherent selection state, controls that fit the existing visual hierarchy, and an explicit success status. The tests exercise the actions on desktop and mobile.

## Findings

No remaining actionable findings in the reviewed scope.

The narrow selected-Trash layout now deliberately hides the file icon, reserves the first column for the checkbox, and pins metadata and Restore to the second column (`apps/web/src/TrashPanel.tsx:92-96`, `apps/web/src/style.css:2240-2260`). The new mobile screenshot `qa-artifacts/20261112-bulk-trash/mobile/selected.png` confirms that content no longer shifts between unintended cells.

The confirmed bulk move now uses a reusable `danger` variant (`apps/web/src/App.tsx:1119-1124`, `apps/web/src/ui.tsx:4-9`, `apps/web/src/style.css:425-433`) driven by the existing semantic danger tokens. It distinguishes the consequence without adding one-off visual values.

## Recommendation

APPROVE

The revised scope has a real reusable component tree, token-driven styling, and verified desktop/mobile evidence. No critical, high, medium, or low issue remains in this review.
