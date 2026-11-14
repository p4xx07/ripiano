# One-tap filing suggestions: final gate review

Recommendation: **APPROVE**

## Blockers

None.

## Original intent

Reduce the filing friction that made Paperless tedious. A useful suggestion should be optional, explainable, and accepted with one action. Accepting it must not silently classify unrelated fields or save other edits that are still drafts.

## Desired outcome

- Suggestions remain based on the owner's manually filed examples and show their evidence.
- One tap immediately saves the selected tag, sender, or document type.
- Other edits in the open form remain drafts until **Save changes**.
- Tag acceptance adds one tag without replacing existing tags, cannot use another owner's tag, is idempotent, and respects the 100-tag limit.
- Desktop and mobile remain readable and accessible.

## User outcome review

The scoped outcome is satisfied. The document panel sends only the selected suggestion field. Its returned server state is reconciled into the form while preserving unrelated local drafts. The tag API is owner-scoped and additive; sender and type reuse the existing owner-scoped PATCH validation. Suggestions are never applied automatically. The copy explains that the tapped field is saved immediately and that other edits still require the normal save action.

The updated Playwright journey covers tag, sender, and type acceptance on desktop and mobile. It edits the title before accepting suggestions, verifies after each server request that the stored title is still unchanged, then verifies the title changes only after **Save changes**. The rendered evidence block is readable at both captured widths and uses semantic controls and the existing token system.

This approval is limited to the one-tap filing-suggestion slice. It does not establish full Paperless parity or a whole-application 9.5 score.

## Artifacts checked

- `services/api/archive/views.py`
- `services/api/archive/test_classification.py`
- `apps/web/src/DocumentPanel.tsx`
- `apps/web/src/style.css`
- `apps/web/e2e/filing-suggestions.spec.ts`
- `docs/FEATURE_PARITY.md`
- `.omo/evidence/filing-suggestions-code-review.md`
- `.omo/evidence/filing-suggestions-clone-fidelity.md`
- `apps/web/test-results/filing-suggestions-one-tap-c3d76-se-a-manually-filed-example-desktop/filing-suggestions.png`
- `apps/web/test-results/filing-suggestions-one-tap-c3d76-se-a-manually-filed-example-mobile/filing-suggestions.png`

## Reproduced evidence

- Focused API suite: `15 passed`.
- Production PWA build: passed.
- `git diff --check`: passed.
- Current desktop and mobile captures inspected directly.
- Executor browser run: two projects passed after expansion to tag, sender, and type. The test source and generated captures were inspected directly.

## Direct programming and overfit review

The production change is limited to an additive owner-scoped tag PATCH operation and form-state reconciliation required by the interaction. There is no unnecessary abstraction, extraction, normalization, or broad API expansion.

The API test exercises observable boundaries: additive behavior, preservation of existing metadata, manual origin, override removal, idempotency, owner isolation, and ambiguous-input rejection. The browser test exercises the full user flow and server persistence for all three suggestion kinds, including the main adversarial case of an unrelated unsaved title. It is neither tautological nor an implementation-mirroring test. No deletion-only or padding tests were added.

The code-review report explicitly records its own programming and overfit pass. Its earlier low coverage note for sender and type was resolved by the updated browser scenario.

## Exact evidence gaps

- The latest browser result is represented by the successful run output and generated captures rather than a separate checked-in textual run log. This does not violate the scoped success criteria because the executable scenario and its current artifacts are present and were inspected.
- No ULW attempt directory could be resolved because the local `omo` runtime target is missing, so this report uses the documented fallback evidence path.
