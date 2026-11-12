# Permanent deletion UX and design-system review

**Recommendation:** APPROVE

## Evidence inspected

- Pending UI implementation: `apps/web/src/TrashPanel.tsx` and `apps/web/src/style.css`.
- Shared live-DOM primitives: `apps/web/src/ui.tsx`.
- Browser journey and assertions: `apps/web/e2e/trash.spec.ts`.
- Rendered browser evidence: `qa-artifacts/20261112-permanent-deletion/{desktop,mobile}/confirmation.png` and `qa-artifacts/20261112-permanent-deletion/{desktop,mobile}/trash-cleanup.png`.

The interface is live React DOM using the existing `Button` and `Modal` primitives. The new status card uses existing typography, radius, spacing, color, and status tokens; it is not a raster or screenshot substitute. The desktop/mobile screenshots show the same responsive hierarchy as the surrounding archive UI. No token-system or component-tree blocker was found.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None. The earlier issue is resolved: `apps/web/src/TrashPanel.tsx:161` now renders the localized completion date/time and a stable short job reference after the backend erases the sensitive title. The updated desktop/mobile cleanup screenshots show distinct, reconcilable entries without retaining document content.

### LOW

The failure/retry surface is API-tested but has no browser screenshot or browser-level interaction scenario. `apps/web/src/TrashPanel.tsx:163-164` supplies a clear failure status, error text, and Retry cleanup control, so this is not a visual or interaction blocker for this slice. Capture it when the test fixture can intentionally produce a cleanup failure.

The earlier danger-affordance issue is resolved: the row action at `apps/web/src/TrashPanel.tsx:154` and confirmation action at `:173` both use the shared `danger` button variant. The updated confirmation screenshots show the destructive choice clearly separated from Cancel on desktop and mobile.

## Blockers

None.
