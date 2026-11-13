# Untagged search and Overview shortcut: clone-fidelity review

Recommendation: **APPROVE** (scoped to the uncommitted optional `is:untagged` search and Overview shortcut).

## Evidence inspected

- Current diff for `apps/web/src/OverviewPanel.tsx`, `apps/web/src/App.tsx`, and `apps/web/e2e/untagged-search.spec.ts`.
- Live component hierarchy in `apps/web/src/OverviewPanel.tsx`, `apps/web/src/App.tsx`, and shared primitives in `apps/web/src/ui.tsx`.
- Theme tokens, global keyboard focus treatment, and existing `text-action` styling in `apps/web/src/style.css`.
- Browser evidence captured by the dedicated desktop and mobile journey:
  - `apps/web/test-results/untagged-search-overview-o-3c62b-without-tags-in-the-Library-desktop/untagged-library.png`
  - `apps/web/test-results/untagged-search-overview-o-3c62b-without-tags-in-the-Library-mobile/untagged-library.png`
- The end-to-end scenario verifies the Overview control opens the Library with `is:untagged` present in the real search input and the uploaded document visible, on both viewports.

## Findings

### CRITICAL

None. The new affordance is a real semantic `button` in the React Overview panel. The destination is rendered by the existing Library component tree; no screenshot, raster substitute, or CSS background image is used as interface.

### HIGH

None. The change reuses the established `text-action` pattern, token-backed type and colors, and the global focus-visible rule. It does not introduce a second design system or a fixed-position overlay.

### MEDIUM

None. The destination layout remains readable at the inspected 1440px desktop and 390px mobile widths. The existing responsive toolbar naturally stacks sort, filters, and add controls at mobile width; the text query fits without clipping. The button is present only when untagged documents exist, avoiding a dead navigation target.

### LOW

None. There is no separate Overview capture in this run, but the actual control, semantic role/name, click interaction, and Library result are exercised by the checked Playwright source and its successful desktop/mobile artifacts.

## Fidelity conclusion

The slice extends the current warm-paper/green archive UI through live DOM and existing token-driven styles. It makes an existing “without tags” status actionable without introducing a mandatory filing queue or adding visual density to the Library.
