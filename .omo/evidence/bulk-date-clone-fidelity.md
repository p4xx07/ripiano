# Batch document-date UX and design-system review

Scope: uncommitted batch document-date feature in `/Users/debotta/dbrepos/ripiano`.

## Evidence inspected

- `apps/web/src/App.tsx:509-527` — live batch-date request and success/error state.
- `apps/web/src/App.tsx:1128-1135` — disclosure, native date input, and action buttons.
- `apps/web/src/ui.tsx:4-19` — shared Button and Field primitives.
- `apps/web/src/style.css:1-145`, `737-786`, and `1224-1233` — semantic tokens and responsive bulk-control layout.
- `apps/web/e2e/bulk-date.spec.ts:9-49` — desktop/mobile interaction journey, including the API-observable set and clear states.
- `qa-artifacts/20261112-bulk-date/desktop/bulk-date.png`.
- `qa-artifacts/20261112-bulk-date/mobile/bulk-date.png`.

## Review

The feature is a live React component tree. The input and buttons are regular DOM controls connected to `applyBulkDate`; the screenshots are Playwright evidence of that interaction, not images used as interface elements. The added controls reuse the established `bulk-filing-details`, `bulk-filing`, and `Button` primitives. The change adds no one-off visual CSS, inline layout values, background images, canvas, or screenshot-backed interface.

Existing semantic color, typography, spacing, border, and radius tokens drive the rendered controls. The narrow viewport rule lets the buttons flex inside the existing wrapped bulk-control layout; the inspected mobile capture remains within the viewport and keeps the date input and both actions readable. The field carries an explicit accessible name, while the disclosure creates a compact, optional action rather than adding a required filing step.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Recommendation

APPROVE. The batch-date controls are live, reusable, token-driven, responsive, and visually consistent with Ripiano's existing bulk-edit hierarchy. No blocker remains in this scoped design review. This approval is limited to this feature and is not a 9.5 release score.
