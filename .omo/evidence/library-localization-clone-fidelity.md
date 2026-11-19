# Incremental Italian Library localization — clone and design fidelity review

## Scope

Reviewed the uncommitted Library/search/filter/upload localization after `8620632`. This review does not approve complete Italian interface coverage.

## Evidence inspected

- Current diff: `apps/web/src/App.tsx`, `apps/web/src/locales/AppLibrary.ts`, `apps/web/e2e/language.spec.ts`, `README.md`, and `docs/FEATURE_PARITY.md`.
- Live component structure: Library content and capture modal in `apps/web/src/App.tsx:1186-1653`; shared `Button`, `Field`, and portal-backed `Modal` in `apps/web/src/ui.tsx:1-100`.
- Token and responsive system: `apps/web/src/style.css:601-706`, `:956-1049`, and `:1239-1367`.
- Final rendered desktop and mobile artifacts:
  - `apps/web/test-results/language-the-interface-swi-da6b5-ck-and-remembers-the-choice-desktop/library-italian.png`
  - `apps/web/test-results/language-the-interface-swi-da6b5-ck-and-remembers-the-choice-mobile/library-italian.png`
- Browser journey additions at `apps/web/e2e/language.spec.ts:24-38`. Parent reran it serially after fixing its mobile sidebar sequencing; both projects passed.

## Findings

### CRITICAL

None. The localized Library is a live React component tree with native controls and Lucide icons. The review found no canvas, screenshot, raster, or background-image substitute.

### HIGH

None. The change introduces no visual styling or hard-coded palette. Existing CSS tokens, shared primitives, and responsive rules render the localized surface.

### MEDIUM

None in the implemented daily Library scope. The desktop capture is orderly and readable: Italian title, summary, saved search, search input, filter controls, and empty-state hierarchy follow the existing Ripiano layout. The mobile capture cleanly stacks search, sort, action buttons, and the filter form without overflow.

### LOW

1. The mobile capture is intentionally taken after opening filters, so it begins below the top heading and does not show the Italian capture modal. The same serial Playwright journey did open/assert the modal; a future visual-review artifact should additionally capture it at mobile width. `apps/web/e2e/language.spec.ts:34-37`.

2. The documented scope correctly leaves bulk operations, document detail, mail, sharing, and workflows in English. Those surfaces can still yield mixed-language journeys and therefore prevent a whole-app localization approval; they do not block this incremental Library slice.

## Design-system assessment

The translation catalog is typed through `defineMessages`, while the live DOM keeps the established heading, summary-card, toolbar, `Field`, `Button`, dialog, focus, and token-driven CSS hierarchy. Italian labels fit within the inspected desktop and mobile layouts. The filter and capture controls retain semantic native inputs/buttons and the modal's existing focus trap.

## Recommendation

**APPROVE** for the incremental Library localization scope, **9.5/10**.

## Blockers

None for this scoped change. Full UI localization remains open work.
