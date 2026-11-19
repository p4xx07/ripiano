# Judge 1 — round 6 report

- Candidate SHA: `635be8edb4768499d627eae922c1ab5a463cfeb3` (branch `codex/initial-implementation`); running stack at http://localhost:18080
- Date: 2026-11-19 (run between 00:05 and 00:25 CET)
- Reviewer account: `judge1` (Admin). Emphasis: a first-time owner on desktop, with key journeys repeated on mobile emulation
- Browser: Playwright `Version 1.64.1` (`npx playwright --version`), channel `chrome` = Google Chrome 157.0.8103.79. Desktop 1440x900; mobile 390x844 with `isMobile`, `hasTouch`, and DPR 2; locales en-US and it-IT
- Artifacts: `qa-artifacts/20261118-r6-judge-1/` (40 PNGs; `d*` = desktop, `m*` = mobile; the token in `d17-*` is masked)

## Commands and scripts

All scripts are in my scratch folder (`…/scratchpad/j1/`, outside the repo). I ran them with `cd apps/web && node <scratch>/j1/<script>.mjs`. `lib.mjs` imports `@playwright/test` by absolute path, reads the password from judges.env at runtime, and never prints it.

| Script | What it does |
| --- | --- |
| explore1/explore2.mjs | Sign-in, home inventory, Add dialog inventory |
| upload.mjs | Desktop: Take a photo (judge.png), a five-file Browse batch, then Choose from photos (judge.png). Polls `/api/documents/<id>` until all are ready |
| search.mjs | Library searches: OCR phrase, sender, prefix, `date:`, `tag:`, number |
| doc.mjs, file.mjs | Opens a document; rejects one suggestion, accepts another, then edits title, date, new sender, and tags in one screen; saves and verifies after reload |
| paper.mjs, paper2.mjs, archive.mjs | Creates a paper copy, finds it by sticker code, prints the sticker label, moves the copy, checks History, views the Paper archive screen |
| mobile.mjs | Mobile: sticker deep link while signed out, sign-in, landing on the found copy, camera upload, document dialog, touch-target audit |
| kbd.mjs | Keyboard only: skip link, `/`, Esc, `j`, Enter, Tab in dialog, Esc focus return, `n`, `?`, sticker lookup |
| ital.mjs | it-IT mobile: home, menu, Paper archive, document dialog; scans for English leftovers |
| grant.mjs, mcp.mjs … mcp5.mjs, revoke2.mjs | Creates the two MCP grants in the UI; `initialize`, `tools/list`, and `tools/call` with each bearer token; revokes in the UI; checks 401 |
| offline.mjs | Mobile: add while offline (queued), back online; connection reset mid-upload, then reload (resumes) |
| damaged.mjs, dmg2.mjs, inbox.mjs | Truncated PDF plus an unsupported .txt; Inbox and Pages panel |
| backup.mjs | Back up now; Overview |
| mobile2.mjs, unsaved.mjs | Mobile filters by sender, tag-chip tap, horizontal-overflow sweep over 13 screens, closing a dialog with an unsaved edit |
| api.mjs + q*.js | Read-only API checks in the signed-in page context (document JSON, pages, archive, search counts) |
| shell | `docker cp` of one fixture copy into my own folder source `/sources/r2-judge1/` (maintenance worker), then `docker exec … ls` to watch it move to `processed/`. No restarts, no rebuilds, no source edits |

## Fixture IDs used

`judge.png` (camera, gallery, mobile camera), `three-pages.pdf` (batch, offline; a first-third truncation of it as the "damaged" input), `office-letter.docx` (batch, aborted-upload resume), `email-notice.eml`, `outlook-notice.msg`, `office-sheet.xlsx` (batch), `barcode-batch-desktop.pdf` (watched folder, PATCHT split). All uploads used the prefix `r6j1-`.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 8.8 | All 7 desktop uploads (camera, gallery, PDF, DOCX, EML, MSG, XLSX) were ready in 6.2 s and went straight to the Library, no TODO screen (d04, d05). Mobile camera upload worked (m05). Watched-folder file imported in about 2 min and split into 2 by the barcode sheet. In one screen: rejected a sender suggestion (the rejection persists), tapped a type suggestion (it saved without losing the draft title/date), added a new sender inline, tagged, saved (d07–d09). | Telegram (real bot), real device camera, Android scanner |
| Retrieval and physical filing | 20% | 8.7 | OCR phrase "tassa rifiuti" → 4 results with snippets (d06). Sender filter on mobile (m15), `date:2026-11-10`, `tag:Tasse`, and "9473" all correct. Sticker code search; label printed with QR, title, code, and location (d11). Moving the copy is announced and recorded in History (d12). The QR deep link `/?sticker=` survives sign-in and lands on the copy (m01, m02). | Physically scanning a printed QR with a phone camera (the deep link was simulated) |
| UX and accessibility | 20% | 8.6 | Polished desktop and mobile. No horizontal overflow on any of 13 mobile screens. Complete Italian, with no English leftovers found (m07, m08, m10). Skip link, `/`, Esc to the first result, Enter opens, Esc returns focus to the row, `n`, `?` list; focus trapped in dialogs. Findings M2, M3, L1–L4 below. | Screen reader (VoiceOver/TalkBack), installed PWAs, native Android |
| Reliability and recovery | 20% | 8.6 | Offline add → "1 file is waiting… sends when the connection is back" → sent when online (m11). Connection reset mid-upload → "trying again…", and the file was sent after a page reload (m13). Unsupported file gets a clear per-file error while the other file in the batch is still added (d20). Back up now → complete snapshot (d24). Restore drill file read and found credible. Finding M1 below. | Killing or restarting workers and services (shared stack; not allowed), a clean-stack restore myself |
| Privacy and agent control | 15% | 9.3 | Creating a grant requires the password. Local grant `tools/list` = 6 tools; Cloud (titles only, tag Tasse) = `search_documents` only. Cloud search for a body-only word ("rifiuti") → 0 results, so there is no content oracle. Cloud `get_document_text` and `semantic_search` were denied, and the denials appear in Recent activity. Filter enforced (only the Tasse document is visible). The agent's tag change shows as `Agent "R6J1 Local"` in document Changes. Revoke uses an inline confirm (d18), then 401 at once while the other grant stays 200. Token shown once with Copy. | Real cloud MCP client (Claude) end to end; Ollama |

**Weighted mean: 0.25·8.8 + 0.20·8.7 + 0.20·8.6 + 0.20·8.6 + 0.15·9.3 = 8.78**

## Hard gates

| Gate | Status | Notes |
| --- | --- | --- |
| 1. Parity rows have a working scenario | Partially demonstrated | I exercised the upload channels, email/Office formats, barcode split, tags/senders/types, suggestions, search syntax, notes UI, history, sharing UI, MCP grants, backups, and Italian. I did not verify the matrix row by row. Two deviations: no search by original file name (L2), and a contradicted touch-target claim (M3). |
| 2. Install / upload / OCR / search / backup / clean restore | Accepted from evidence | Upload, OCR, search, and backup demonstrated live. The clean-stack restore comes from `.omo/evidence/restore-drill-round6.md` (same SHA; checks originals by SHA-256, tags, nested locations, revoked grant still 401). It is credible but was not re-run by me. |
| 3. Installed iOS/Android PWA, native Android | Out of scope by owner decision (D7) | — |
| 4. Security review | Partially demonstrated | Agent isolation, scope filtering, revocation, and password-confirmed grant creation verified live. CSRF and upload validation only seen in passing (.txt rejected). No full security review. |
| 5. Tests / builds / migrations on the candidate | Not demonstrated by me | I did not run the suites, because that needs dependency sync. |
| DS923+ performance/ACL/restore, real Telegram and cloud accounts | Out of scope by owner decision (D7) | — |

## Findings

No severe or high findings.

### Medium

**M1. A damaged (truncated) PDF is marked Ready, and the lost pages go unreported.**
- Repro: upload the first third of `three-pages.pdf` as `r6j1-damaged.pdf`.
- The document becomes `ready` with text "Page 1 first otter" (1 of 3 pages). It never appears in Inbox or Overview "could not be read".
- The Library row says Ready. The dialog shows only "No preview for this document" (d23), and Pages & versions says "This PDF could not be read" (`GET /pages` → 400, `pages/1.png` → 400).
- Cause: `services/api/archive/tasks.py:100-118`. ocrmypdf silently repairs the file, then the status is set to READY without checking that the original is readable or that page counts match.
- Impact: the user believes a 3-page paper is archived when only 1 page is searchable.

**M2. Closing the document dialog throws away unsaved edits without warning.**
- Repro (mobile or desktop): open `r6j1-office-sheet`, change Title, tap the close button (or press Esc).
- The dialog closes, no prompt appears, and the edit is lost; the API still shows the old title (m18).
- Cause: `apps/web/src/DocumentPanel.tsx:480-481`. Both close paths call `onClose` directly, and the panel has no dirty-state check.
- This matters because the panel deliberately mixes auto-saving suggestion taps with edits that need "Save changes", so users will expect their edits to stick.

**M3. Touch targets in the document dialog are below the 44 px that FEATURE_PARITY claims.**
- Repro: 390x844 with touch, open any document, measure the controls.
- Title/ASN/date inputs are 37–39 px tall. Sender, type, and location selects are 38 px. Save changes is 41 px, Create sticker 38 px, Add note 40 px, tag chips 41 px.
- The keyboard/accessibility parity row says "mobile targets at least 44px for filing and document actions".
- Cause: the `@media (pointer: coarse)` blocks in `apps/web/src/style.css` (around lines 1384-1421 and 4670+) cover text actions, nav, and close only, not form controls or `.button`.

### Low

**L1. Saving changes closes the dialog without a confirmation.** If the edit changes what the current search matches, the document disappears from the list and the page shows "Nothing found yet" (d09, after renaming a title that the search matched). A first-time owner may think the document was lost.

**L2. Original file names are not searchable.**
- `r6j1-email-notice` → 0 results, and `r6j1-camera.png` → 0 after the title changed, even though the Library row displays the file name.
- Paperless indexes `original_filename`.

**L3. Partial-word search is inconsistent.**
- `lampo` → 0 (while `lampone` matches 4), and `r6j1-watched` → 0, but `Bollet` → 6 and `r6j1-watched-batch` → 2.
- Typing mid-word shows "Nothing found yet".

**L4. Keyboard focus is lost after Clear search, and there is no shortcut for Paper archive.**
- After using the Library's Clear search button, focus drops to `<body>` instead of returning to the search field.
- There is no `g`+letter shortcut for Paper archive, which is a primary screen. `g p` does nothing.

**L5. An imported email's sender is not used as "From".** For `email-notice.eml` the email metadata shows Comune di Esempio, but the correspondent stays empty, and Library rows for that email show no "From:". Searching "Comune di Esempio" does find it through the text.

**L6. Printed stickers show the location at print time.** After a move, the label is stale (d11 vs d12). Nothing prompts a reprint, so people might trust an outdated label over a scan.

**L7. Exact duplicates fill the Inbox.** 31 "exact copies to review" (expected with re-uploaded fixtures), but there is a "Resolve all exact copies" action, so this is noted only.

## Most serious finding

**M1: a truncated/damaged PDF is silently accepted as Ready with pages missing, and nothing tells the owner.** For an archive whose promise is "the original is safe and searchable", a scan that reads as fine while 2 of its 3 pages are unreadable is the failure most likely to surface only when the paper is gone.
