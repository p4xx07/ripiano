# Round 3 follow-up — UX and accessibility review

- Reviewer: independent read-only UX/accessibility pass.
- Date: 2026-11-18.
- Candidate under review: current uncommitted working tree on `codex/initial-implementation`; the normal running stack at `http://localhost:18080` remains the earlier `d8724ff` image, while the browser regression routes the freshly built local PWA through that same origin. It validates the web changes but not an assembled candidate container image.
- Scope: Claude's round-3 findings and the follow-up changes in `apps/web/src/App.tsx`, `DocumentPanel.tsx`, `style.css`, `uploadQueue.ts`, and `e2e/judge-round3-regressions.spec.ts`.

## Evidence inspected

- `.omo/evidence/judge-2-round-3-report.md` and `.omo/evidence/judge-3-round-3-report.md`.
- `qa-artifacts/20261118-r3-judge-2/72-mobile-320-people-overflow.png` and its recorded 320 px reflow script.
- The current web diff and the regression browser tests.
- Existing responsive, filing, upload-queue, physical-copy and live-region implementation.

## Findings

No high or medium usability finding was identified in the final reviewed diff.

## Verified follow-up fixes

- The 401 upload path now preserves the selected file under the previous signed-in owner before the asynchronous session-end handler changes session state. `sendWaiting` retries it after the same owner signs in, retains the scan ID, and the regression journey asserts two equal scan IDs. This resolves the former silent-loss medium finding subject to a candidate-stack run.
- Sender and document-type inputs now prevent form submission on Enter and invoke the same creation action as their buttons. The regression journey checks that the dialog stays open and that the created values survive saving and reopening.
- The touch-target selectors cover the three former sender/type row icon buttons, the file links, and paper-copy actions under a coarse pointer. The mobile regression checks the measured controls at 44 px. The dark-theme skip link now uses the semantic on-primary colour token.
- The Library count is now a polite atomic status region and its regression checks the zero-results update. The Italian rejected-file message now handles the singular case. Moving a paper copy clears stale feedback and announces the moved sticker code; the mobile journey checks the resulting status.
- The 320 px check now covers all four formerly overflowing screens. Paper and Agents run against the regular account and live API data. People and Backups use read-only intercepted API responses after sign-in to render their real owner UI with Italian labels, long representative person/group/backup values, an owner session flag, `scrollWidth`, and unclipped-descendant assertions. The reported run passed.

## Fixture limitation

The People and Backups journey validates the rendered owner layout and the responsive CSS, but it does not validate owner authorization, data persistence, or live owner-service responses. Those are separate API/security and release-gate concerns. This is appropriate for resolving the former layout-only reflow defect without creating a privileged account in the shared stack.

## Design-system review

No evidence of image or screenshot substitution was found. The affected UI is rendered by live React components, and the new CSS uses existing semantic design tokens for colour, spacing, and radius. The touch-target additions are limited to coarse-pointer media queries, retaining desktop density.

## Recommendation

APPROVE

No critical or high issue was found in this review. The earlier 320 px reflow defect now has targeted responsive changes and coverage for all four affected screens. This is not a release score or a substitute for the full three-judge running-stack gate.
