# Incremental English/Italian localization — clone and design fidelity review

## Scope

Reviewed the uncommitted localization foundation and the implemented surfaces: sign-in, appearance/language controls, responsive sidebar, top bar, Backups, and the panels that now import their local message catalogues. This is an incremental review; it does not certify full application localization.

## Evidence inspected

- Live React/i18n implementation: `apps/web/src/i18n.ts`, `apps/web/src/App.tsx`, and `apps/web/src/locales/*.ts`.
- Existing shared primitives and token styles: `apps/web/src/ui.tsx`, `apps/web/src/style.css`.
- Browser journey: `apps/web/e2e/language.spec.ts`.
- Rendered desktop and mobile evidence:
  - `apps/web/test-results/language-the-interface-swi-da6b5-ck-and-remembers-the-choice-desktop/italian.png`
  - `apps/web/test-results/language-the-interface-swi-da6b5-ck-and-remembers-the-choice-mobile/italian.png`
- Current dirty diff and `docs/FEATURE_PARITY.md` disclosure.

## Findings

### CRITICAL

None. The language UI is live semantic DOM: native labelled selects, React state through `useSyncExternalStore`, and existing components. There is no image, canvas, pasted screen, or background-image surrogate.

### HIGH

None. The selector reuses the existing `appearance-control` pattern and its established semantic color, spacing, radius, and focus tokens. The rendered sidebar, controls, navigation, and Action empty state match Ripiano’s existing hierarchy at desktop and mobile widths.

### MEDIUM

1. Localization remains intentionally incomplete. Major screens including Library/document detail, mail, sharing, workflows, and some API errors still contain English, so switching to Italian can lead to mixed-language flows. The implementation and parity matrix accurately disclose this; it prevents approval of the full localization parity row, but does not block this incremental foundation. See `docs/FEATURE_PARITY.md:31`, `apps/web/src/App.tsx`, and the untranslated component set.

### LOW

1. The reused sidebar select has a 39px minimum height, below the 44px touch target used by several other controls. The mobile screenshot remains usable and the pattern predates this change, but the eventual localization polish should align both selectors with the app’s touch target standard. `apps/web/src/style.css:246`.

## Design-system assessment

The implementation is a real component system: language selection has a browser-persisted preference, delegates all visible strings through typed per-surface message maps, changes `<html lang>`, and uses the same design tokens as the surrounding app. The Italian screenshots show a consistent green sidebar, typographic hierarchy, spacing, buttons, and responsive mobile shell. No new hard-coded palette or one-off visual system was introduced.

## Recommendation

**APPROVE — 9.0/10 for this incremental localization slice.**

## Blockers

None for the implemented foundation. Full Italian/English parity remains open until all user-facing screens and API errors are translated and re-reviewed.
