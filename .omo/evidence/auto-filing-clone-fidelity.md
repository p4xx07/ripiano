# Automatic filing: clone-fidelity review

Recommendation: **APPROVE** (scoped to the current uncommitted automatic-filing UI slice).

## Evidence inspected

- Current UI diff for `apps/web/src/LearningPanel.tsx`, `apps/web/src/locales/LearningPanel.ts`, `apps/web/src/style.css`, `apps/web/src/DocumentPanel.tsx`, `apps/web/src/App.tsx`, and `apps/web/e2e/learning.spec.ts`.
- The live component tree and data types in `apps/web/src/LearningPanel.tsx` and `apps/web/src/api.ts`.
- Shared card/form rules and the design-token definitions/theme overrides in `apps/web/src/style.css`.
- The prior filing-suggestions fidelity report at `.omo/evidence/filing-suggestions-clone-fidelity.md` for the established review standard.
- Browser evidence from the passed Playwright desktop and mobile journeys:
  - `apps/web/test-results/learning-learned-suggestio-e6c15-plain-how-reliable-they-are-desktop/auto-filing-enabled.png`
  - `apps/web/test-results/learning-automatic-filing-control-remains-usable-on-mobile-mobile/auto-filing-mobile.png`

## Findings

### CRITICAL

None. The control is live React DOM: a semantic `label` with a real checkbox, explanatory text, and API-backed state. It does not substitute a screenshot, image, or hardcoded visual for interactive UI.

### HIGH

None. The generic card-input selector now excludes checkboxes at `apps/web/src/style.css:1836`, so the compact, token-coloured 20px checkbox at `apps/web/src/style.css:3950` renders as intended. The desktop capture confirms the live checkbox and text share a compact horizontal card; the mobile capture confirms a full-width label target without clipping or horizontal overflow.

### MEDIUM

None. `apps/web/e2e/learning.spec.ts` verifies the control's default, persistence through reload, disable path, and both desktop/mobile interaction. Its captures show the explanatory copy wrapping cleanly. The narrow layout switches learned-status rows to a single column at `apps/web/src/style.css:3965`, avoiding the previously likely compressed metric layout.

### LOW

None.

## Fidelity conclusion

The implementation uses the existing warm-paper/olive semantic tokens, shared card hierarchy, and real form structure. It introduces no raster or hardcoded UI substitute. The checked option card, live state, agent/model-origin explanations, and new readiness text fit the established visual hierarchy. The desktop and mobile artifacts support the responsive fidelity claim; dark and AMOLED views inherit the same semantic token overrides.
