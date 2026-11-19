# Untagged search final gate review

## Recommendation

**APPROVE**, scoped to the optional `is:tagged` / `is:untagged` Library search and Overview shortcut. This verdict does not imply whole-app Paperless parity or a 9.5 score.

## Blockers

None.

## Original intent

Reduce the filing friction that made Paperless tedious. Documents should remain available without a mandatory TODO queue, while users can still find the subset that has no tags and review it when they choose.

## Desired outcome

- Overview makes its existing untagged count actionable when the count is nonzero.
- The action opens the normal Library with an explicit, editable `is:untagged` query.
- `is:tagged` and `is:untagged` stay owner-scoped and preserve established Library exclusions.
- The syntax combines with ordinary search terms and works through the existing cursor and saved-search contracts.
- Desktop and mobile remain readable and operable.

## User outcome review

The slice satisfies the scoped outcome. The Overview control is optional and does not create a new filing inbox or mutate metadata. It clears unrelated filters, opens the Library, and exposes `is:untagged` in the normal search field. The backend applies tag presence to the already owner-scoped, non-trashed, non-split-source Library queryset. The raw query remains bound into signed cursors and saved searches store it through their existing query field.

## Artifacts checked

- Current diff:
  - `services/api/archive/views.py`
  - `services/api/archive/test_archive.py`
  - `apps/web/src/App.tsx`
  - `apps/web/src/OverviewPanel.tsx`
  - `apps/web/e2e/untagged-search.spec.ts`
  - `docs/FEATURE_PARITY.md`
- Code review: `.omo/evidence/untagged-search-code-review.md`
- UX review: `.omo/evidence/untagged-search-clone-fidelity.md`
- Desktop capture: `apps/web/test-results/untagged-search-overview-o-3c62b-without-tags-in-the-Library-desktop/untagged-library.png`
- Mobile capture: `apps/web/test-results/untagged-search-overview-o-3c62b-without-tags-in-the-Library-mobile/untagged-library.png`
- Related contracts: `services/api/archive/stats_views.py`, `services/api/archive/metadata_views.py`, `services/api/archive/models.py`, and `apps/web/src/SavedSearchBar.tsx`.

## Independently reproduced evidence

- `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_archive.py -q`: **29 passed**.
- `npm run build`: **passed**, including TypeScript and Vite PWA production output.
- `manage.py check`: **passed**.
- `manage.py makemigrations --check --dry-run`: **No changes detected**.
- `git diff --check`: **passed**.
- Inspected the reported full API run (**169 passed, 6 skipped**) and the desktop/mobile Playwright result (**2 passed**) as supporting executor evidence.
- Visually inspected both destination captures. The explicit query and results are readable at 1440px and 390px widths.

## Adversarial and contract review

- Foreign-owner, trashed, and hidden split-source documents are created in the API test and excluded by observable result equality.
- Tagged and untagged branches are both exercised.
- An ordinary word combined with `is:untagged` narrows the result correctly.
- Invalid `is:` values return a validation error.
- The Overview count and search predicate both use `DocumentTag` presence over the same visible-document population.
- The browser journey uses the semantic Overview button and verifies the destination query and uploaded document in live DOM on both viewport projects.

## Direct slop, overfit, and programming pass

The requested `remove-ai-slops` and `programming` skill files were not available in the local skill roots, so their criteria were applied directly. The code-review report explicitly records the same skill-perspective and overfit pass.

No excessive, deletion-only, tautological, or implementation-mirroring tests were found. The API test validates externally visible filtering and ownership boundaries; the browser test validates the user journey. Production adds one accepted search field, one bounded validator, and one correlated existence predicate. There is no unnecessary extraction, normalization layer, untyped escape hatch, duplicated parser, or unrelated scope expansion.

## Evidence gaps

No blocking gap for this slice. The browser capture shows the Library destination rather than the Overview source, but the Playwright journey directly locates and clicks the semantic source button on both desktop and mobile before asserting the destination. A fresh browser rerun was not needed because the existing execution output and captures were available; backend and build checks were independently reproduced.
