# Archive pagination check

Checkpoint base: `02e536d`. This slice adds server paging after that checkpoint.

- API: `RIPIANO_DEBUG=1 uv run pytest -q` in `services/api` passed, 21 tests. The new test creates 51 open documents plus a document owned by another user, checks both Library and Needs action pages, stable non-overlapping results, summary totals, and invalid offsets.
- Web: `npm run build` passed.
- Running Compose stack: API/web rebuilt and healthy; the complete desktop/mobile Playwright suite passed, 12 tests. After a final repeated-tap guard, the four focused action and pagination journeys passed again on the rebuilt stack.
- The browser pagination fixture returns 51 synthetic documents. Both desktop and mobile reach document 51 through **Show more documents** and **Show more follow-ups**, and the summary shows the full count.

The test uses synthetic documents and a local Compose stack. NAS permissions and physical-device capture remain separate release gates.
