# One-tap filing suggestions: clone-fidelity review

Recommendation: **APPROVE** (scoped to the current uncommitted one-tap filing-suggestion slice).

## Evidence inspected

- Current diff for `apps/web/src/DocumentPanel.tsx`, `apps/web/src/style.css`, and `apps/web/e2e/filing-suggestions.spec.ts`.
- Shared live UI primitives in `apps/web/src/ui.tsx`.
- The token definitions and theme overrides in `apps/web/src/style.css`.
- Browser evidence:
  - `apps/web/test-results/filing-suggestions-one-tap-c3d76-se-a-manually-filed-example-desktop/filing-suggestions.png`
  - `apps/web/test-results/filing-suggestions-one-tap-c3d76-se-a-manually-filed-example-mobile/filing-suggestions.png`
- The targeted Playwright journey, which records two passing projects (desktop and mobile) and asserts that the immediate tag save leaves an edited title as a local draft until the normal Save action.

## Findings

### CRITICAL

None. The suggestion area is live React DOM: a semantic `section`, real `button` controls, Lucide SVG icons, and text content. It does not substitute a screenshot or image for the interface.

### HIGH

None. The implementation uses the existing modal and form structure, retains a visible focus target after acceptance, and applies the established semantic color, spacing, type, and radius tokens. The panel fits the warm-paper/olive system in both inspected captures.

### MEDIUM

None. The busy state disables competing suggestion controls while the request is pending; the inline alert and status channels cover failure and completion. The browser journey verifies the important mixed-state case: a proposed tag persists immediately while an unsaved title stays local.

### LOW

None.

## Fidelity conclusion

The change extends the existing document-detail hierarchy rather than introducing a separate visual system. Its layout remains a compact bordered recommendation block inside the established detail form, with token-backed surface, border, typography, spacing, focus border, and responsive wrapping. The desktop and mobile captures remain readable with long generated titles and evidence text.
