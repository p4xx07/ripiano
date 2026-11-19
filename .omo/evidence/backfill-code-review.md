# Selected-document local filing code review

## Scope reviewed

The uncommitted change adds `POST /api/documents/bulk-learned-filing` and a Library bulk action that explicitly applies the owner's trusted local filing model to up to 100 existing documents. It deliberately does not alter the preference that controls automatic filing for newly processed documents.

## Independent verification

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_learning.py -q` — **7 passed**.
- `npm run build` in `apps/web` — passed.
- `git diff --check` — passed.
- `RIPIANO_DEBUG=1 ./.venv/bin/python manage.py check` — no issues.
- `RIPIANO_DEBUG=1 ./.venv/bin/python manage.py makemigrations --check --dry-run` — no changes detected.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Review notes

- The endpoint validates count, UUIDs, duplicates, and complete owner-scoped selection before calling the model. A race after that validation is contained by the owner check within `apply_learned_filing`; a trashed, no-longer-ready, or split-source document becomes a reported skip instead of a write. See `services/api/archive/views.py:657` and `services/api/archive/auto_filing.py:26`.
- Explicitly selected backfill bypasses only the *future intake* preference. It still uses the trained-model, 90% confidence, held-out precision, evidence-count, manual/source origin, tag-removal, and owner-local target checks. The front end states that distinction at `apps/web/src/App.tsx:1403`.
- The API returns skipped IDs, and the UI keeps them selected; this is a useful retry/review affordance rather than a false success signal. The real-model test verifies no policy is created or enabled by the one-time endpoint (`services/api/archive/test_learning.py:86`), and the validation test verifies no model call is made for any invalid or foreign selection (`services/api/archive/test_learning.py:111`).
- The browser test relies on a separately provisioned trained-model fixture, so it cannot replace the API test; its assertions are appropriate as a UI wiring test and verify the setting remains off.
- Re-review: the prior deferred `transaction.on_commit` retry is now a synchronous, bounded three-attempt loop in `services/api/archive/auto_filing.py:26`. A model or document change between prediction and lock produces a fresh in-request prediction, so the bulk response cannot report a skip and later mutate the selection after the response. The regression at `services/api/archive/test_learning.py` simulates a model-metrics change during the first prediction and verifies both the second prediction and the returned assignment count. No regression risk found in the automatic-intake caller: it retains the same policy gate and returns zero after repeated concurrent edits.

## Skill-perspective check

The prescribed `remove-ai-slops` and `programming` skill files could not be located in the available local skill roots, so their review criteria were applied directly. The diff does not add needless abstractions, untyped TypeScript escapes, brittle prompt tests, or unnecessary parsing. The tests exercise observable ownership and behavior boundaries rather than merely mirroring implementation constants; no deletion-only or tautological test was found.

## Assessment

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- Scoped score: **9.5/10**
- `blockers`: None.
