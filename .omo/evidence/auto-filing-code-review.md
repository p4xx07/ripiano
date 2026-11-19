# Auto-filing code review

## Scope and evidence

Reviewed the uncommitted automatic-filing slice: the policy model and migration, local-model
application path, OCR task integration, API and PWA control, origin rendering, documentation,
and focused tests.

Independent verification run:

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_learning.py archive/test_workflows.py -q` — 12 passed.
- `RIPIANO_DEBUG=1 ./.venv/bin/python manage.py makemigrations --check --dry-run` — no changes detected.
- `git diff --check` — passed.

## Skill-perspective check

Ran the `remove-ai-slops` and `programming` review perspectives. The new module is 95 pure
LOC; the other directly changed feature modules are below the 250-LOC threshold. The tests cover
observable opt-in, ownership, field/tag precedence, confidence rejection, first-OCR invocation,
and persistence. They are not deletion-only or tautological. No needless abstraction or untyped
TypeScript escape hatch was found. The feature retains a broad exception at the optional OCR-task
boundary, but it logs and deliberately preserves ingestion availability, matching the existing
task pattern; this is not flagged as a separate defect.

## Re-review of the quality-gate fix

The previous blocker is resolved. `learning.py` now records `auto_precision` and
`auto_tested_suggestions` only for held-out predictions at `AUTO_THRESHOLD` (90%), and
`auto_filing._trusted` gates writes on those separate values. The focused regression suite now
also checks that a 94% auto precision or fewer than 20 high-threshold test predictions refuses
automatic filing.

Independent re-verification:

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_learning.py -q` — 5 passed.
- `git diff --check` — passed.
- `RIPIANO_DEBUG=1 ./.venv/bin/python manage.py makemigrations --check --dry-run` — no changes detected.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Assessment

`codeQualityStatus`: **CLEAR**

`recommendation`: **APPROVE**

Scoped implementation score: **9.4 / 10**. The ownership isolation, explicit consent, lock
ordering, non-overwrite semantics, tag suppression, and evidence gate now align with the
probability band that can change documents.

`blockers`: None.
