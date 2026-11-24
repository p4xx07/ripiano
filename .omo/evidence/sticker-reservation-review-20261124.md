# Sticker code reservation review — 24 November 2026

## Scope and decision

ASN remains the numeric barcode field used by uploaded scans. The visible topic code (`MED-00042`) belongs to the sticker system. A digital-only document gets no code by default; an advanced action can reserve one, and a later paper copy uses that same code.

## Separate code and UX review

- A reserved code is serialized as `reserved_at` and remains searchable by code. Library's **Paper copy** filter excludes it from the paper option and includes it in **Digital only**. Location contents exclude it because a reservation has no location, and the database enforces that invariant and one reservation per document.
- The copy move and missing-status endpoints reject reservations. Sticker lookup and its UI identify a reservation and show no paper movement or missing controls. The document panel shows a reserved code separately from a registered paper copy.
- Registering paper under the document lock clears the reservation and retains the same code and copy ID. The selected location receives the first movement record. Repeated reservation requests return the existing code; another paper copy remains an advanced action after activation.
- A mistaken reserved topic can be changed under an advanced action. The earlier code remains a lookup alias. The numeric ASN is unchanged by reservation and activation.
- The new API errors have Italian translations. The existing English `Archive number (ASN)` label remains stable for browser tests; its hint now explains its barcode role. No runtime dependencies or always-on services were added.

No high or medium finding remains from this review. This was a separate review pass by the implementing agent, not an external judge round.

## Verification

- API: `RIPIANO_DEBUG=1 .venv/bin/pytest -q` — 482 passed, 17 skipped.
- Focused physical, API language, and API contract tests — 22 passed.
- Web TypeScript and production build — passed. Migration dry run — no changes. `git diff --check` — clean.
- Playwright against the rebuilt local stack: reserve then activate on desktop Chrome and mobile Chrome emulation — 2 passed. The first attempt used `127.0.0.1` instead of the configured `localhost` origin and was rejected by CSRF; rerunning with `localhost` passed.
- Local preview: `/healthz` returned 200, migration 0069 is applied, and the web bundle is served on port 18125. The temporary browser-test account and its two documents were removed afterwards; other user documents were left intact.

The in-app browser automation runtime could not start (`No such file or directory`), so the browser evidence comes from Playwright. Real-device testing and physical destruction tracking are outside this slice.
