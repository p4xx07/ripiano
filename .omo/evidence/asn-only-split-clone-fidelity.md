# ASN-only barcode split — clone / design-system review

## Evidence inspected

- The uncommitted diff for `apps/web/src/DocumentPanel.tsx`, `apps/web/e2e/barcodes.spec.ts`, `README.md`, and `docs/FEATURE_PARITY.md`.
- The live `DocumentPanel` component and its shared `Modal`, `Button`, and `Field` primitives in `apps/web/src/ui.tsx`.
- Existing token-driven styles for `.email-origin` in `apps/web/src/style.css`.
- The generated desktop and mobile ASN PDF fixtures and the checked-in browser scenario.
- Final desktop and mobile browser captures at `qa-artifacts/20261114-asn-split/{desktop,mobile}/asn-only-split.png`, linked from the README gallery.

## Findings

### CRITICAL

None. The notice is live React DOM inside the established document dialog. It does not use a screenshot, background image, or substituted visual asset.

### HIGH

None. The feature reuses the existing `split-note`, `email-origin`, `Modal`, and Lucide `Layers` patterns. It adds no bespoke visual system or hardcoded palette.

### MEDIUM

None. The wording now truthfully covers both PATCHT and ASN boundaries. The linked full-scan affordance remains a real button and follows the existing focusable modal interaction.

### LOW

None.

## Assessment

`recommendation`: **APPROVE**

`scoped score`: **9.6 / 10**

`blockers`: None.
