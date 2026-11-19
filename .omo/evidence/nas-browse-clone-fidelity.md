# NAS browse copy — UX and clone-fidelity review

## Scope and evidence inspected

- Uncommitted NAS browse UI in `apps/web/src/App.tsx:224-385` and its browser journey in `apps/web/e2e/nas-browse.spec.ts`.
- New selectors in `apps/web/src/style.css:2978-2994`, including the existing mobile backup layout rule at `apps/web/src/style.css:2378-2420`.
- Design-system contract in `docs/DESIGN_SYSTEM.md`.
- Running-stack browser captures:
  - `qa-artifacts/20261112-nas-browse/desktop/backups.png` (1100×162)
  - `qa-artifacts/20261112-nas-browse/mobile/backups.png` (358×229)

## Findings

### CRITICAL

None. The captures show live React content from `BackupPanel`: semantic heading, `Button`, Lucide folder icon, dynamic run text, and status badge. No image, canvas, rasterized UI, or `background-image` substitutes for the interface.

### HIGH

None. The new action uses the existing shared `Button` primitive, existing `.section-heading`, `.document-row`, `.document-icon`, `.document-info`, and `.status` structures. Desktop and mobile render the same live controls and state rather than separate mockups.

### MEDIUM

None. The mobile capture retains a large reachable action, clear heading, descriptive copy, current run count, visible status, and a safely wrapping truncated path. The browser scenario covers navigation, starting the job, polling completion, reload persistence, and the returned folder identifier.

### LOW

1. `apps/web/src/App.tsx:317-350` is indented one level less than its surrounding `<section>`. This does not change rendered hierarchy or accessibility, but adjusting it would make the component structure easier to review.

## Design-system assessment

The small amount of new CSS is token-driven: it uses semantic spacing, muted text, and named type tokens. It adds no fixed color, spacing, radius, shadow, or typography value. The desktop capture follows the established Backups page hierarchy; the mobile capture stacks the control and run card cleanly under the existing responsive rules. The vocabulary remains plain and aligned with Ripiano's safety-first language.

## Recommendation

**APPROVE.** No fidelity or UX blocker remains for this slice. The indentation note is cosmetic.

## Blockers

None.

## Follow-up

The `<section>` contents in `apps/web/src/App.tsx` were indented consistently after review. The singular document count was corrected, and the desktop/mobile section captures were refreshed from isolated synthetic accounts.
