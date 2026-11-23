# Workflow editor UX review — 2026-11-23

Scope: current workflow editor diff against `9ad2d53`; reviewed the JSX, responsive CSS, English/Italian labels, documentation, and desktop/mobile screenshots. This is an independent pass over the uncommitted layout work handed off to this session.

## Findings and changes

- The old 340px agent sidebar forced every condition, source, and action into one narrow column. The editor now occupies the content width and uses two columns on desktop, one on mobile. The workflow list and run history remain visible when the editor is closed.
- A long tag collection still made the new mobile editor needlessly tall. The Add tags choices now open on demand and show the selected count. The browser test opens the picker and verifies a real workflow still applies its tag.
- The Italian empty-state hint referred to a recipe being on the right, although recipes now sit above the list. Corrected it.
- The live rule sentence reflects the current draft. Cancel closes the editor without saving; Save stays in view during long forms. Advanced actions and source filters remain available.

No high or medium findings remain in this slice. Long specialist forms still require scrolling on phones; the tag picker and source grid reduce the longest part without hiding workflow capabilities.

## Evidence

- `cd apps/web && npx tsc --noEmit -p .`: exit 0.
- `cd apps/web && npm run build`: exit 0; Vite reports the existing large chunk advisory.
- Isolated synthetic stack on `localhost:18122` with final rebuilt web image: `npx playwright test e2e/workflow-layout.spec.ts e2e/workflows.spec.ts e2e/workflow-assignments.spec.ts --workers=1 --reporter=line`: **6 passed** in 37.9s, desktop and mobile. Creation, tagging after OCR, title patterns, custom fields, and run history exercised.
- `git diff --check`: exit 0.

During the first browser run, one upload returned 500 because `os.fsync` on a directory in the Docker Desktop bind mount raised `EBADF`. A direct synthetic file write and the next browser run passed. This is an unrelated intermittent storage issue, to be investigated in its own slice; the failure is not counted as a workflow result.
