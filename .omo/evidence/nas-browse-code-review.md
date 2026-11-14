# NAS browse copy code review

## Scope reviewed

Uncommitted NAS browse export work: owner-only API, `BrowseExportRun`, maintenance tasks, Compose settings, Backups UI, deployment/docs, focused API tests, and desktop/mobile browser evidence.

## Evidence independently checked

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_browse_export.py`: 2 passed.
- Django system check and migration dry-run: passed; no model drift.
- `npm run build`: passed.
- Local and Portainer Compose configuration: passed.
- `git diff --check`: clean.
- Inspected `qa-artifacts/20261112-nas-browse/desktop/backups.png` and `mobile/backups.png` as supporting UI evidence; they are consistent with the live DOM/browser test but are not treated as a substitute for tests.

## Skill-perspective check

`remove-ai-slops` and `programming` skill files were unavailable in this review context. I applied their documented criteria directly. The production code contains only the validation/normalization needed for filenames and managed-media boundaries; it does not add unrelated parsing or abstraction. The tests exercise owner isolation, asynchronous job admission, successful readable output, original checksum verification, retention, cleanup on changed input, and a live UI route. They are not deletion-only, tautological, brittle prompt tests, or implementation-mirroring tests.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Assessment

The async state transition is guarded with a row lock, API admission serializes against the owner row, media access remains constrained by the existing `_media_path` guard, output paths use a safe sanitized component plus UUID, and the browse tree is staged then atomically published. The worker-only writable backup mount matches the API's read-only status inspection. The shared backup lock prevents browse publishing from overlapping a media snapshot/cleanup. The browse tree is expressly separate from the restorable snapshot tree, and old outputs are deleted only from tracked successful runs for the owner.

## Verdict

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- `blockers`: None.

## Re-audit: deterministic retry and published-copy verification

Reviewed the later implementation in `services/api/archive/browse_export.py`:

- The output folder is now deterministically derived from the run creation time and UUID. A worker retry after a crash can therefore recognize the already-published destination instead of creating a second tree.
- `_verify_published()` rejects unsafe paths and links, validates the owner/version/kind fields, checks every manifested canonical and tag-view file for type, size, and SHA-256, and is called before publication and before accepting an existing destination.
- The fallback from a hard link to a physical copy now uses the same expected size/hash path as the canonical file.
- The added `build_browse_tree(run)` assertion exercises the intact deterministic retry path. The focused API suite still passed (2 tests), Django checks/migrations passed, the PWA built, and the desktop live journey passed.

No new correctness, security, or maintainability finding resulted. The skill-perspective conclusion is unchanged: the verification code is proportionate to the persistence boundary, and the tests remain behavior-focused rather than implementation-mirroring.
