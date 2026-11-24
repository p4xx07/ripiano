# Round 13 fix code review

Candidate reviewed: uncommitted working tree after the round-12 follow-up fixes.

Scope: `App.tsx`, `DocumentPanel.tsx`, `JobsPanel.tsx`, `classification.py`, their
regressions, README, and FEATURE_PARITY.

## Result

`codeQualityStatus`: **CLEAR**

`recommendation`: **APPROVE**
`blockers`: none.

## Review method

- Read the complete scoped diff and the adjacent implementation paths.
- Traced `/api/jobs`: it scopes work to `request.user`; its `processing` summary is
  therefore appropriate for the Library and document currently open by that person.
- Traced session ownership: `session.owner` means Django `is_superuser`, so the
  document dialog must receive the session flag instead of assuming that ownership
  of a document allows restarting containers. The final diff does this.
- Checked the existing browser evidence. The initial full run exposed a direct
  regression where a third `.notice-region` broke `judge-round8.spec.ts`'s
  two-region contract. The final diff places `ProcessingProblem` in the existing
  first region, preserving that contract. A fresh full browser run is still needed
  by the executor as release evidence; this review does not claim it was run after
  that last structural adjustment.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None remaining.

Two medium findings were raised during this review and fixed before this final
assessment:

1. `DocumentPanel` had hard-coded `isOwner`, which would instruct a regular
   account holder to restart a container. `App.tsx` now passes `session.owner` at
   the sole call site, `DocumentPanel.tsx` requires that prop, and the Italian
   browser regression checks the dialog as well as the Library.
2. A separate third live region broke the existing accessibility test. The final
   code renders the worker message inside the first persistent region, whose
   purpose already includes status announcements.

### LOW

None.

## Correctness and scope

The email filter is limited to the two MIME types Ripiano renders as mail. It
removes display-only recipient/date/attachment header values and email addresses
from the first header block, while retaining sender, subject, and body evidence.
The regression covers both PDF text layouts produced by the email renderer,
reproduces the former false suggestion through a controlled counterfactual, and
shows that genuinely similar mail remains suggested. It does not change searchable
OCR text or the learned-model path.

The UI reads the already existing `/api/jobs` processing summary only while a
visible document is pending or processing, every 15 seconds. It clears health
when no such document remains. This adds no service, dependency, or server-side
load beyond the pre-existing job polling.

## Test and maintainability review

The new backend test is behavior-oriented: it distinguishes an unrelated tax
email from a genuinely similar meeting email and proves that the old evidence
would have crossed the suggestion threshold. The UI tests cover Library and
document dialog, desktop/mobile via the existing Playwright projects, and the
non-owner Italian instruction. They do not merely mirror implementation constants.

The required `remove-ai-slops` and `programming` skills were not available in the
provided skill catalog or filesystem lookup for this review. I applied their stated
perspectives manually: no deletion-only or tautological tests, no brittle prompt
assertions, no untyped escape hatch, and no unnecessary parser beyond the rendered
email-header boundary required by the defect. No violation found.
