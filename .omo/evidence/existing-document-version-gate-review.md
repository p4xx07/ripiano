# Existing-document-as-version gate review

## Recommendation

**APPROVE — scoped score 9.8/10.**

## Blockers

None.

## Original intent

Close the Paperless parity gap for combining already archived documents as versions without inheriting a destructive or tedious workflow. A user should be able to find another owned document, use its current original as the target's new current file, retain the target's metadata and previous file, and leave the source document intact.

## Desired outcome

- A simple PWA picker for ready, owned source documents.
- Independent target bytes so later source deletion or damage cannot break the target.
- Target title, tags, notes, and older versions remain attached to the target root.
- The source stays separate and unchanged.
- Owner isolation, stale-source/target protection, checksum validation, share revocation, and no orphan files on failure.
- Desktop/mobile behavior that explains the consequences and recovers from concurrent changes.

## User outcome review

The slice satisfies the intended outcome. The endpoint is owner scoped, refuses foreign, trashed, split, processing, self, malformed, unavailable, checksum-mismatched, and stale sources. Source and target rows are reloaded and locked in deterministic UUID order inside one transaction, and the source file is copied through the existing validated original-storage path while those locks are held. The target receives an independent file path and checksum-verified bytes; the target's prior file becomes a normal downloadable `DocumentVersion`; share links and containing bundles use the existing version-change revocation path; OCR is queued only after commit. The source remains a separate document.

The PWA uses semantic search, fieldset, radios, shared buttons, and design tokens. It announces loading, clears stale results, exposes first-page limits, distinguishes source staleness from target staleness, and preserves the page editor after a rejected stale-source action. The wording states that the operation copies a file and does not merge metadata, notes, physical copies, or delete the source.

## Evidence reproduced

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_versions.py -q`: **9 passed**.
- `RIPIANO_DEBUG=1 ./.venv/bin/pytest -q`: **175 passed, 7 skipped**.
- `RIPIANO_DEBUG=1 ./.venv/bin/python manage.py check`: no issues.
- `RIPIANO_DEBUG=1 ./.venv/bin/python manage.py makemigrations --check --dry-run`: no changes.
- `npm run build`: production PWA build passed.
- `git diff --check`: passed.
- Final browser evidence after the wording change: desktop and mobile journeys passed **2/2** and assert source-stale recovery, page-editor preservation, target current bytes, previous-version download bytes, source bytes, and source version independence. The temporary account and its files were removed afterward.
- Visual inspection: desktop and mobile screenshots are readable, consistent with the version-card hierarchy, and use the existing green token palette.

## Artifacts inspected

- `services/api/archive/versions.py`
- `services/api/archive/version_views.py`
- `services/api/archive/test_versions.py`
- `services/api/archive/views.py`
- `services/api/ripiano/urls.py`
- `apps/web/src/PagesPanel.tsx`
- `apps/web/src/style.css`
- `apps/web/src/api.ts`
- `apps/web/e2e/pages-versions.spec.ts`
- `README.md`
- `docs/FEATURE_PARITY.md`
- `.omo/evidence/existing-document-version-code-review.md`
- `.omo/evidence/existing-document-version-clone-fidelity.md`
- `apps/web/test-results/pages-versions-an-archived-f2e24-ther-document-s-new-version-desktop/existing-document-version.png`
- `apps/web/test-results/pages-versions-an-archived-f2e24-ther-document-s-new-version-mobile/existing-document-version.png`

## Direct slop, overfit, and maintenance pass

`remove-ai-slops` and `programming` were not available as local skills, so their required criteria were applied directly. The two added backend tests are proportionate and user-observable: preservation and independence in the success path, plus authorization, staleness, unavailable/corrupt file handling, and absence of mutation/orphans in failure paths. They are not deletion-only, tautological, or implementation-mirroring. The browser test follows the real UI and validates persisted bytes and recovery, rather than asserting markup alone. Production changes reuse the existing version/storage pipeline; there is no needless parser, normalization layer, abstraction, or untyped escape hatch. The code-review report explicitly records the same skill-perspective and anti-overfit review.

## Evidence gaps and notes

- `omo ulw-loop status --json` could not run because its installed runtime target is missing, so the documented fallback evidence path is used.
- Fresh desktop and mobile screenshots were captured by the final post-wording Playwright run. The final label, first-50 guidance, interaction flow, and responsive layout therefore have current browser evidence.
- The seven full-suite skips are environment-specific existing skips; focused version coverage passed completely.
