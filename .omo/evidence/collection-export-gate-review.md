# Collection export gate review — 12 November 2026

## Recommendation

**APPROVE**

`blockers`: none

This approval is scoped to selected-document collection export. It is not an R4, Paperless-parity, real-device, or 9.5 release approval.

## Original intent

Continue Ripiano toward Paperless feature parity while preserving its simpler responsive UX, NAS-first storage model, portable data, and judge-reviewed checkpoints. This slice adds a practical way to export several selected Library documents together without claiming complete archive export/import.

## Desired outcome and criteria

- **CE-1 Selection contract:** an authenticated archive user can export 1–20 distinct active documents and preserve the caller's selection order.
- **CE-2 Portable contents:** one ZIP contains stable per-document folders, preserved originals, available searchable PDFs and OCR text, readable metadata, and SHA-256 entries.
- **CE-3 Access and integrity:** foreign or trashed documents cannot be exported; malformed, duplicate, empty, and over-limit requests fail; a changed or missing original prevents the whole export.
- **CE-4 User experience:** the action is discoverable in Library selection mode and works in desktop and mobile browser profiles without overflow or inaccessible custom controls.
- **CE-5 Regression safety:** the existing single-document export keeps its file layout and verification behavior.
- **CE-6 Honest scope:** documentation identifies the 20-document limit and leaves complete archive export/import and broader release gates open.

## User outcome review

The current implementation satisfies the scoped outcome. Selecting documents exposes an **Export selected** disclosure and a semantically correct download link. The server validates the full selection before packaging, restricts the query to the signed-in owner and active archive, preserves request order, and writes each document below `documents/<uuid>/`. The root manifest carries document metadata and per-file checksums. Any inaccessible selection returns 404 and any unverifiable original returns 503 rather than returning a partial collection.

The current desktop and mobile captures are clean and show two selected documents, the limit explanation, and the download control without the earlier unrelated duplicate badge. The broader application remains a draft; the docs correctly leave complete archive export/import, real-device checks, and the 9.5/R4 release decision open.

## Artifacts checked

- Production diff: `services/api/archive/export_views.py`, `services/api/ripiano/urls.py`, `apps/web/src/App.tsx`, `apps/web/src/style.css`.
- Tests: `services/api/archive/test_collection_export.py`, `services/api/archive/test_export.py`, `apps/web/e2e/collection-export.spec.ts`.
- Evidence: `.omo/evidence/collection-export-code-review.md`, `.omo/evidence/collection-export-clone-fidelity.md`, `.omo/evidence/collection-export-live-check.md`.
- Visuals: `qa-artifacts/20261112-collection-export/desktop/selected.png`, `qa-artifacts/20261112-collection-export/mobile/selected.png`.
- Documentation: `README.md`, `docs/FEATURE_PARITY.md`, `docs/QUALITY_JUDGES.md`, `docs/CONTINUATION_2026-11-12.md`.

## Independent checks

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_collection_export.py archive/test_export.py` — **3 passed**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py check` — no issues.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` — no changes.
- `git diff --check` — clean.
- Direct inspection confirmed route ordering before the UUID route, bounded UUID parsing, owner/Trash filtering, request-order restoration, UUID folder naming, all-or-nothing original verification, and reuse of the existing single-export file writer.
- Direct visual inspection confirmed the current desktop and mobile captures have no duplicate warning, clipping, or horizontal overflow.

The live-check artifact records **67/67 API tests** and **62/62 desktop/mobile browser journeys** on the rebuilt Compose stack. I independently reproduced the focused three-test export suite and Django checks rather than treating those aggregate counts as the sole proof. The browser test verifies the real download in both configured profiles; the API test opens the resulting ZIP and verifies its contents and boundaries.

## Adversarial and maintenance review

- Owner isolation, Trash exclusion, duplicate IDs, malformed IDs, empty input, 21-item input, changed bytes, stable order, ZIP paths, checksums, tag metadata, and note metadata are covered.
- UUID-based directories prevent collisions from repeated or hostile original filenames.
- The 20-document bound and existing per-upload size bound constrain temporary-disk use. Streaming the completed temporary file avoids holding the ZIP response in application memory.
- The extraction of `_write_files` is justified because both export modes require the same file naming and integrity rules. It does not add speculative abstraction.
- Tests assert public behavior and archive contents. They are not tautological, deletion-only, implementation-mirroring, or excessive for the security and portability boundary.
- The code-review report explicitly contains its own remove-ai-slops/programming perspective check. Those named skills were unavailable; I directly applied the stated overfit, false-confidence, needless-abstraction, and maintenance-burden criteria and found no violation.

## Notes and exact evidence gaps

- An earlier duplicate-warning screenshot issue was resolved by using distinct synthetic bytes. The refreshed UX report and current images confirm the warning is absent.
- The aggregate 62-journey console transcript is summarized in the live-check report rather than committed as a raw log. This does not block CE-1 through CE-6 because the scoped desktop/mobile journey artifacts and focused server verification exist, but the aggregate count should not be treated as an R4 release artifact.
- The collection export has no corresponding importer and is intentionally capped at 20 documents. Both limitations are disclosed and remain future parity work.
