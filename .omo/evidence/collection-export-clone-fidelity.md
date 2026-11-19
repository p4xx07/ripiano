# Collection export clone-fidelity review — 12 November 2026

**Recommendation: APPROVE**

## Scope and evidence inspected

- Uncommitted UI diff in `apps/web/src/App.tsx` and `apps/web/src/style.css`.
- Live browser journey: `apps/web/e2e/collection-export.spec.ts`.
- Rendered desktop and mobile captures:
  `qa-artifacts/20261112-collection-export/desktop/selected.png` and
  `qa-artifacts/20261112-collection-export/mobile/selected.png`.
- Existing UI primitives and token definitions in `apps/web/src/ui.tsx` and
  `apps/web/src/style.css`.

## Findings

### CRITICAL

None. The export control is ordinary live React DOM: a semantic `details` /
`summary`, descriptive paragraph, and anchor. It does not use a screenshot,
raster substitute, canvas, or `background-image` to fake the interface.

### HIGH

None. The feature sits in the established bulk-action hierarchy and reuses the
existing `.bulk-filing`, `.button`, and `.button-secondary` system. It has a
real link target and an accessible link name that reflects the selected count.

### MEDIUM

None. The desktop and narrow mobile captures keep the disclosure, copy, and
download control legible without clipping or horizontal overflow. The native
`details` control preserves keyboard operation and exposes an understandable
summary.

### LOW

None. The recaptured desktop and mobile evidence use distinct valid PNG bytes
and no longer show unrelated duplicate warnings.

## Design-system conclusion

The added UI is a live component-tree addition rather than a pasted visual.
Colors, spacing, radii, and type flow through the existing CSS custom-property
tokens (`--color-*`, `--space-*`, `--radius-*`, and `--type-*`) used by the
shared button and bulk-filing styles. The only new CSS declaration removes the
native underline for all `.button` links and does not introduce a one-off color,
dimension, or layout value. The visual language matches the rest of Ripiano in
both reviewed viewports. `apps/web/src/App.tsx:1152` correctly uses an anchor
styled by the shared button classes for a download instead of misrepresenting
the navigation as a button.

`recommendation`: **APPROVE**

`blockers`: None.
