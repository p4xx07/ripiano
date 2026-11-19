# Existing-document version picker — clone/design fidelity review

## Scope and evidence inspected

- Current uncommitted diff for `apps/web/src/PagesPanel.tsx`, `apps/web/src/style.css`, `apps/web/src/api.ts`, and `services/api/archive/views.py`.
- Shared UI primitives and tokens in `apps/web/src/ui.tsx` and `apps/web/src/style.css`.
- Embedding context in `apps/web/src/DocumentPanel.tsx`.
- Browser evidence supplied after the implementation: successful desktop and mobile Playwright journeys, including source-stale recovery, plus [`existing-document-version.png` desktop](/Users/debotta/dbrepos/ripiano/apps/web/test-results/pages-versions-an-archived-f2e24-ther-document-s-new-version-desktop/existing-document-version.png) and [`existing-document-version.png` mobile](/Users/debotta/dbrepos/ripiano/apps/web/test-results/pages-versions-an-archived-f2e24-ther-document-s-new-version-mobile/existing-document-version.png). The mobile capture is taken after the source action, so it does not visually show a populated picker; the journey itself asserts radio selection and stale-result refresh.

## Findings

### CRITICAL

None. The picker is live React/HTML form markup; it does not use a screenshot, raster surrogate, or background-image stand-in.

### HIGH

None. The new UI uses the existing `Button` primitive and the established CSS semantic color, type, spacing, and radius tokens. It inherits dark and AMOLED values through the shared semantic tokens.

### MEDIUM

None. The revised picker clears earlier results at the start of a search, gives the pending state an accessible status, and suppresses the empty state until the request completes. The Playwright desktop and mobile journey also exercises selection, source-stale recovery, successful completion, and file preservation. [PagesPanel.tsx:65](/Users/debotta/dbrepos/ripiano/apps/web/src/PagesPanel.tsx:65), [pages-versions.spec.ts:8](/Users/debotta/dbrepos/ripiano/apps/web/e2e/pages-versions.spec.ts:8)

### LOW

1. `max-height: 260px` is a new one-off layout measurement outside the existing spacing scale. It is not visually harmful, but a named layout token or an existing constrained-list pattern would keep the system stricter. [style.css:3421](/Users/debotta/dbrepos/ripiano/apps/web/src/style.css:3421)

2. The source search’s label says it searches “title or content,” but the UI does not explain that it only lists ready, non-split documents or that results stop at the API’s first page. The selected-state copy handles the safety distinction well; a short availability hint would reduce surprising empty results. [PagesPanel.tsx:288](/Users/debotta/dbrepos/ripiano/apps/web/src/PagesPanel.tsx:288), [PagesPanel.tsx:293](/Users/debotta/dbrepos/ripiano/apps/web/src/PagesPanel.tsx:293)

## Design-system assessment

The interaction uses a genuine DOM component tree: a labelled search field, native `fieldset`/`legend`, native radios, and the shared `Button`. It reuses semantic colors, typography, spacing, borders, and radii, so it will follow the app’s light, dark, and AMOLED themes without a parallel palette. The card-like picker belongs to the existing Pages & versions hierarchy and the `44px` search control maintains an appropriate touch target. No image-based imitation or hard-coded palette was added.

The former interaction-validation gaps are resolved. The source-stale path clears the invalid choice, refreshes the result list, and reports the failure; the tested success message preserves the distinction between copying the file and retaining the source document. The desktop evidence shows the picker within the established version-card hierarchy and the mobile journey completed without a layout failure.

## Recommendation

**APPROVE — 9.7/10 for this slice.**

## Blockers

None for clone/design-system fidelity.
