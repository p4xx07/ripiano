# Trash retention clone and design-system review

**Recommendation:** APPROVE

## Evidence inspected

- Pending React implementation: `apps/web/src/TrashPanel.tsx`.
- Shared live-DOM primitives and dialog focus handling: `apps/web/src/ui.tsx`.
- Token system and retention styles: `apps/web/src/style.css`.
- Desktop/mobile browser journey: `apps/web/e2e/trash-retention.spec.ts`.
- Rendered desktop/mobile confirmation and disabled-state captures: `qa-artifacts/20261112-trash-retention/{desktop,mobile}/{confirmation,off}.png` (refreshed 2026-11-12 15:36 local).

The retention panel, control, confirmation, and state copy are live React DOM. The screenshots show real form controls and a portal modal over the Trash page; no raster image, background image, or screenshot substitute is present. The implementation reuses the existing `Button` and `Modal` primitives. New styling is driven by the established semantic color, type, radius, and spacing tokens.

The desktop and mobile renders preserve the Ripiano hierarchy: Trash context, recovery state, then a bounded settings card. Default-off language, the visible age threshold, eligible-count preview, backup-retention disclosure, and danger confirmation make automatic deletion understandable before activation. The mobile dialog wraps its title cleanly and retains a visible cancellation route.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None. The final source at `apps/web/src/style.css:2137-2185` uses the established spacing tokens for the modal heading clearance and numeric-control height. The remaining `6rem` width is an intentional component layout constraint, not a competing spacing or visual-token system.

## Blockers

None.
