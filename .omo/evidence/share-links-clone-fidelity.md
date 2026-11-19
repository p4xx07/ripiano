# Share-link UX and design-system review — 12 November 2026

## Recommendation

**APPROVE**

`blockers`: none.

## Evidence inspected

- Live React components: `apps/web/src/ShareLinksPanel.tsx`, its insertion in
  `apps/web/src/DocumentPanel.tsx`, and shared `Button` / `Field` primitives in
  `apps/web/src/ui.tsx`.
- Token system and share-specific styles in `apps/web/src/style.css`.
- Browser journey: `apps/web/e2e/share-links.spec.ts`.
- Token-masked rendered captures:
  `qa-artifacts/20261112-share-links/desktop/{created,revoked}.png` and
  `qa-artifacts/20261112-share-links/mobile/{created,revoked}.png`.

## Findings

### CRITICAL

None. The feature is rendered by ordinary, interactive React DOM: a section,
native disclosure, labels, select, input, buttons, list, status text, and
time element. It is not a screenshot, canvas, raster substitute, or CSS
background pretending to be the share UI.

### HIGH

None. The control is placed directly after the document's Files section, where
the user already manages the preserved original. The browser evidence shows a
clear explanation that a bearer link permits unsigned download, a one-time
link surface, expiry choice, active state, and a revoke action. No clipping or
horizontal overflow appears at the reviewed desktop or 390px mobile widths.

### MEDIUM

None. `ShareLinksPanel` reuses the app's `Button` and `Field` primitives and
the existing keyboard-focus contract. The native `details` / `summary` keeps
the advanced control compact while remaining keyboard-operable. The real
browser journey exercises create, anonymous retrieval, revoke, and the
post-revocation state on both configured browser profiles.

### LOW

None. Share styles use existing colour, spacing, typography, radius, and focus
tokens; the only literal line-height is a normal content ratio rather than a
new visual value. The screenshot mask is test-only and deliberately prevents a
bearer token appearing in committed artifacts.

## Design-system conclusion

The share-link surface follows Ripiano's existing panel hierarchy: section
divider, compact heading with Lucide icon, muted operational explanation,
progressive disclosure, shared form controls, and a restrained danger action.
It adapts without a special mobile fork because the shared grid and width
constraints shrink cleanly. Its design is a real extension of the component
system and matches the surrounding Files and physical-copy sections.
