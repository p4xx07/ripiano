# Shared pending-document OCR status — focused verification, 22 November 2026

The round-14 medium finding was that a reader opening a shared pending document saw no processing or stopped-worker explanation. This follow-up is a focused bug fix, not a new judge round. The owner's 9.42 acceptance remains the score of candidate `8a1ab1a`, not of this changed code.

## Change and privacy check

- `GET /api/documents/<id>` now includes a `processing` summary for a readable shared document while it is pending/processing. The summary filters to that single document. The normal `/api/jobs` list remains limited to the signed-in person's own archive.
- The shared-document panel shows pending/processing/failed state. While a shared document waits, it polls its detail every 15 seconds, shows stopped-worker or unavailable-queue guidance, and stops polling when processing finishes. The original stays downloadable.
- Reviewed the data path: document access is checked before the summary query; the query uses the already authorized document ID. No owner-wide job list, other document title, or private count is returned. The API regression checks a second private pending document is absent from the summary and inaccessible to the viewer.

## Verification

- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_people.py archive/test_api_contract.py` — **11 passed**.
- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` — **459 passed, 17 skipped** in 75.17 seconds.
- `cd apps/web && npx tsc --noEmit -p . && npm run build` — passed; Vite's existing large-chunk warning remains.
- Built `ripiano-shared-fix-web:local` and ran the focused `e2e/judge-round11.spec.ts` `round 14:` case on the local Compose stack in Chrome 157, desktop 1440×900 and mobile emulation 390×844 — **2 passed**. The browser test mocks only the shared-list/detail/notes/history responses; the API regression separately checks the real authorization and summary calculation. Screenshots: [desktop](../../qa-artifacts/20261122-shared-worker-fix/desktop.png), [mobile](../../qa-artifacts/20261122-shared-worker-fix/mobile.png).

No live stopped-worker replay, installed-phone test, or independent three-judge rescore was run after this fix. Those are not implied by the focused results.
