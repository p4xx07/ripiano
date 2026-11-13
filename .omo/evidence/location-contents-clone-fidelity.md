# Location contents and missing-copy state — clone / design-system fidelity review

## Recommendation

**APPROVE** — scoped score: **9.8 / 10**.

## Scope and evidence inspected

- Uncommitted diff against `94eedfb`, including the live React surface in `apps/web/src/PhysicalPanel.tsx`, API response semantics in `services/api/archive/physical_views.py`, and the browser scenario in `apps/web/e2e/physical-missing.spec.ts`.
- [Desktop missing-location contents capture](../../apps/web/test-results/physical-missing-a-missing-e4621-ker-and-last-known-location-desktop/missing-location-contents.png).
- [Mobile missing-location contents capture](../../apps/web/test-results/physical-missing-a-missing-e4621-ker-and-last-known-location-mobile/missing-location-contents.png).
- The established Ripiano design tokens and physical-archive styles in `apps/web/src/style.css`.
- The shared live `Button` primitive in `apps/web/src/ui.tsx`.

No external visual reference was provided for this narrow increment, so fidelity is assessed against the existing Ripiano physical-archive surface and its token system.

## Findings

### CRITICAL

None. The location result is a live React tree: count, warning, contents list, and pagination button are ordinary semantic DOM in [PhysicalPanel.tsx](../../apps/web/src/PhysicalPanel.tsx#L164). There is no screenshot, raster image, canvas, or background image replacing interaction.

### HIGH

None. The initial count-only handling would have hidden the identity of missing copies from the location workflow. The revised surface preserves discoverability without misrepresenting those copies as present: it renders a distinct, titled missing list with each document title, sticker, and last known path at [PhysicalPanel.tsx](../../apps/web/src/PhysicalPanel.tsx#L191). The browser journey verifies the empty present list, the named missing item, its sticker and last known location, click-through to the document, and return to the present list after the copy is marked found at [physical-missing.spec.ts](../../apps/web/e2e/physical-missing.spec.ts#L58).

### MEDIUM

None. Desktop and 390 px mobile captures keep the present count, missing warning, section label, document title, sticker, and last known location visible without clipping or relying on color alone. The warning text states the status explicitly, including the fact that the location is only the last recorded one.

### LOW

None. The result card, warning, spacing, typography, border, and background reuse existing semantic classes and tokens: [style.css](../../apps/web/src/style.css#L2393), [style.css](../../apps/web/src/style.css#L2797), [style.css](../../apps/web/src/style.css#L2849), and [style.css](../../apps/web/src/style.css#L2883). Pagination actions use the shared `Button` component at [PhysicalPanel.tsx](../../apps/web/src/PhysicalPanel.tsx#L190).

## Assessment

The surface is a real, token-driven component rather than a visual imitation. It retains the existing physical-archive hierarchy: location identity, present contents, then a distinct exception state. The screenshots show that this hierarchy remains readable at desktop and mobile widths. The updated flow keeps an actionable record for each missing document, rather than reducing it to a count, and the tested transition back to “found” avoids leaving a stale missing warning behind.

## Blockers

None.
