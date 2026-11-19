# Office upload UX and clone-fidelity review

## Scope and evidence inspected

- Uncommitted diff for `apps/web/src/App.tsx`, `apps/web/src/style.css`, the Office intake backend, and both Compose files.
- [`office-upload.spec.ts`](../../apps/web/e2e/office-upload.spec.ts), including its successful mobile journey.
- Browser artifacts:
  - `apps/web/test-results/office-upload-a-Word-docum-ff23d-e-its-original-stays-intact-mobile/office-search.png`
  - `apps/web/test-results/office-upload-a-Word-docum-ff23d-e-its-original-stays-intact-mobile/office-document.png`
- The existing design system in `apps/web/src/style.css:1-110` and the live modal/document-panel component tree in `apps/web/src/App.tsx`.

## Findings

### CRITICAL

None. The reviewed surfaces are live React controls and DOM content. I found no screenshot, raster image, or background image used in place of the upload, result, or document-detail interface.

### HIGH

None. The incremental control uses the existing modal and button hierarchy, existing status/error pattern, existing responsive layout, and semantic color/type/spacing tokens. The mobile evidence is coherent with the app rather than a separate static mockup.

### MEDIUM

None.

### LOW

1. The modal says “Word, Excel, or PowerPoint,” while the accepted formats are specifically `.docx`, `.xlsx`, and `.pptx` (`apps/web/src/App.tsx:1347`, `1392-1394`; backend rejection text at `services/api/archive/storage.py:54,60`). Users with legacy `.doc`, `.xls`, or `.ppt` files can reasonably infer support and only learn otherwise after selection. Change the helper copy to “Word (.docx), Excel (.xlsx), or PowerPoint (.pptx)” when this slice is next touched.

2. The reviewed mobile search evidence contains a pre-existing duplicate warning for another test upload. It does not affect the Office journey, but it makes the screenshot weaker as product evidence because the result card is visually noisy. Use a fresh account or isolated fixture for README/product screenshots.

## Design-system assessment

The Office addition reuses the existing `Modal`, `add-options`, document list, error/retry, and document panel paths. The only visual change is text inside an existing button. Its colors, spacing, typography, radii, focus treatment, and responsive behavior remain driven by the semantic tokens in `style.css`; no one-off visual styling was added. The mobile screenshot shows readable, live form and result controls at 390px width.

## Recommendation

**APPROVE.** There are no blocking clone-fidelity or UX defects in the Office upload slice. The format-label clarification is low risk follow-up work.

## Blockers

None.

## Follow-up resolution

The file-picker helper now lists `DOCX`, `XLSX`, and `PPTX` explicitly. The README screenshots were recaptured from two fresh synthetic accounts, each with a single Office document and no duplicate warning.
