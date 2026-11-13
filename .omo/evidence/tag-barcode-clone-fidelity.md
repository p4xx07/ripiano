# Tag barcode mapping — clone / design-system fidelity review

## Recommendation

**APPROVE** — scoped score: **9.8 / 10**.

## Scope and reference

No external visual reference was supplied for this increment. Fidelity is assessed against the existing Ripiano tag-management surface, its shared primitives, and the warm-paper / olive design token system.

## Evidence inspected

- Live component implementation: [TagPanel.tsx](../../apps/web/src/TagPanel.tsx), especially the barcode creation field at lines 380–383 and editable card controls at lines 264–274.
- Shared live control primitive: [ui.tsx](../../apps/web/src/ui.tsx#L7).
- Token definitions and existing tag-card hierarchy: [style.css](../../apps/web/src/style.css#L1), [style.css](../../apps/web/src/style.css#L1601).
- Barcode row/editor responsive styles: [style.css](../../apps/web/src/style.css#L1670).
- Real browser journey: [tag-barcodes.spec.ts](../../apps/web/e2e/tag-barcodes.spec.ts#L14), including desktop/mobile tag creation, label endpoint verification, live QR-driven source tagging, and editor focus.
- Screenshots: [desktop tag barcode](../../apps/web/test-results/tag-barcodes-a-printed-tag-code-files-a-scanned-document-desktop/tag-barcode.png), [mobile tag barcode](../../apps/web/test-results/tag-barcodes-a-printed-tag-code-files-a-scanned-document-mobile/tag-barcode.png), [desktop edit state](../../apps/web/test-results/tag-barcodes-a-printed-tag-code-files-a-scanned-document-desktop/edit-tag-barcode.png), [mobile edit state](../../apps/web/test-results/tag-barcodes-a-printed-tag-code-files-a-scanned-document-mobile/edit-tag-barcode.png), [desktop source-tagged document](../../apps/web/test-results/tag-barcodes-a-printed-tag-code-files-a-scanned-document-desktop/tagged-by-barcode.png), and [mobile source-tagged document](../../apps/web/test-results/tag-barcodes-a-printed-tag-code-files-a-scanned-document-mobile/tagged-by-barcode.png).

## Findings

### CRITICAL

None. The barcode information, actions, and editor are live React DOM: a native input inside a form, a semantic link for the label, and real buttons. No screenshot, raster asset, canvas, or background image substitutes for functionality.

### HIGH

None. The new surface preserves the established tag-card structure, and the verified desktop/mobile QR journey demonstrates that the interface is a functioning product surface rather than a static visual mockup.

### MEDIUM

None. The edit input has a visible label, receives focus, uses the existing focus treatment, and the label-printing action is a named link with an icon. The mobile capture retains readable wrapping and touch-sized primary actions.

### LOW

None. The barcode row and editor reuse semantic color, typography, spacing, border, radius, and focus tokens. The 210px flex basis only establishes an input’s practical minimum width inside the existing responsive card and is not a color, spacing, or typography escape hatch.

## Assessment

The barcode value reads as a subordinate detail of a tag rather than a second competing primary action. Desktop keeps value, print, and edit actions compactly grouped; mobile wraps them without hiding the value or relying on icon-only meaning. The editor retains the existing tag-card rhythm and responsive one-column layout. The document captures prove the expected outcome is visible in the ordinary Library UI.

## Blockers

None.
