# Judge 1 — round 10 report (first-time owner)

- **Candidate:** `5bc8c7de72619aac6ebea44b3cad7c69a610b31a` (branch `codex/initial-implementation`; `HEAD` was `255f81d`, the evidence-only commit on top of it).
- **Date:** 2026-11-20 (session started 00:28 local time, Europe/Rome).
- **Stack:** my own, `http://localhost:18101`, Compose project `ripiano-j1`, started empty. Images were not rebuilt; I only stopped, killed, started and restarted services.
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (Chrome channel, headless), macOS Darwin 25.6.0. Desktop 1440x900; mobile emulation 390x844 with `isMobile` and `hasTouch`.
- **Screen reader stand-in:** none is installed; I used Playwright's accessibility tree (`ariaSnapshot()`) and DOM checks instead.
- **Weighted mean: 8.73 / 10.** Two High findings, no Severe.

## Things to know before reading the scores

- **The working tree changed while I was judging.** `git status` was clean at the start. Later it showed 18 modified and several new files (for example `services/api/archive/backup.py`, `apps/web/src/api.ts`, a new migration `0064`), plus the other judges' reports. I did not make those edits and did not read the other reports. All file:line references below are from `git show 5bc8c7d:<path>`.
- **I did not re-run the API test suite**, because the working tree no longer matched the candidate, so the run would not have tested it.
- **The host clock jumped during the session** (containers reported "Up 7 hours" at the end, and a scheduled 02:00 backup had run). Timings inside one script run are reliable; wall-clock gaps between runs are not.
- **I changed one thing inside my stack to diagnose finding H1:** I deleted the leftover folder `/data/work-9n47xu9w` in the `api` container. Its journal listed two part files from the interrupted split (`originals/7a/7a9c86bc-….pdf`, `originals/8f/8fc84f93-….pdf`). With the journal gone, the app's own cleanup can no longer remove those two files in my stack.

## Scores

| Dimension | Weight | Score | Evidence | Not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 8.6 | First-time setup with the setup key worked from the README. Camera input, file picker, PDF, DOCX/ODT/DOC/XLSX/PPTX, `.eml` and `.msg` all reached "Ready" without visiting any mandatory screen. Barcode splitting and ASN fill-in worked. An uncertain suggestion was accepted, rejected and corrected in one screen on mobile and desktop; the rejection is in "Changes". Deductions: M1, M3, H2. | Telegram and real cloud accounts (out of scope). Watched folder and the gallery input (same mechanism as the camera input) were not tried. Learned suggestions never became active: they need 3 documents each for 2 senders, and the fixtures share too few words. |
| Retrieval and physical filing | 20% | 9.0 | OCR phrase ("badger" on page 3, "9473" in the image), sender, tag, type, date (`14/10/2026`, `date:2026-10`), `asn:900011`, and sender plus date filters all returned the right documents. Sticker created, label opened, QR scanned back through "Scan with camera" with a fake camera feed, copy moved, history shown, shelf contents list nested boxes. Fallback and camera-denied wording are clear. Deductions: L1, L2, L3. | Printing on paper and scanning with a real phone camera. |
| UX and accessibility | 20% | 8.9 | Calm, consistent screens; no horizontal scroll at 390 px; all visible controls labelled; focus trapped in the document dialog and returned on Esc; `/`, `n`, `?` shortcuts work; skip link first in tab order. Italian is complete on the screens I visited, including API errors. Deductions: M2, L4, L5, L6. | Installed PWAs and the Android app (out of scope). A real screen reader. |
| Reliability and recovery | 20% | 8.0 | Worker killed mid-OCR: the document showed "Taking longer than usual. Processing was interrupted and will be tried again by itself." and was ready after 202 s, one copy. API restarted mid-upload: the upload completed by itself after 22 s. API stopped: after the request failed, the file was kept on the device, survived a reload, and was sent once when the API returned. Damaged PDFs are handled honestly. Deductions: H1, H2. | I did not run my own restore; I read `restore-drill-round10.md` (13 of 13 checks, credible). Broker and database stops. |
| Privacy and agent control | 15% | 9.3 | Two grants with different scopes and filters. Tool lists differed (4 tools vs. `search_documents` only). The titles-only agent could not match OCR-only words, saw only "tasse" documents, and was refused text, tag listing and tag changes; refusals appear in the activity log. Revocation answered 401 at once while the other agent kept working. A second family account saw none of the owner's documents, stickers, labels or backups (404/403). | CSRF, token expiry, two-step sign-in, share links, password-change revocation. |

Weighted mean: 0.25×8.6 + 0.20×9.0 + 0.20×8.9 + 0.20×8.0 + 0.15×9.3 = **8.73**.

## Hard gates

| Gate | Demonstrated? | Note |
| --- | --- | --- |
| 1. Feature parity | Partly | I exercised the journeys in my emphasis, not the matrix row by row. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Partly | Install, upload, OCR, search: yes, on my stack. Backup: failed twice, then succeeded once the leftover folder was gone (H1). Restore: not run by me; the separate drill record is credible. |
| 3. Real iOS/Android devices | Out of scope by owner decision | Not scored. |
| 4. Security review | Partly | Account and agent isolation, scopes, revocation, and rejection of empty and non-PDF uploads were shown. CSRF and external input boundaries were not tested by me. |
| 5. Tests and builds | Not re-verified | `round10-verification.md` gives commands and result lines (400 passed, 17 skipped; 305 e2e passed, 45 skipped) and reads as credible. I did not re-run it, for the reason above. |

## Findings

### Severe

None.

### High

**H1 — After a worker is killed while splitting or reading a document, every backup fails with a message the owner cannot act on.**
- Reproduce: upload `asn-batch-mobile.pdf`; about 1 s later run `docker compose -p ripiano-j1 … kill worker`, then `start worker`. Documents finish normally. Open Backups → "Back up now".
- Result: "The backup did not finish: Snapshot contains an unexpected media path". "Try again" fails the same way (two UI attempts and one API attempt, 14 to 17 minutes after the kill).
- Cause: the killed run left `/data/work-9n47xu9w/split-parts.txt`. Work folders are created directly in the media folder (`services/api/archive/tasks.py:211`), and the backup refuses any top-level folder other than `originals` and `archive`, skipping only `previews`, `bundles` and `.pending` (`services/api/archive/backup.py:122`, `:136`).
- Confirmed: after I deleted that folder, the next three backups completed.
- Scope: by the code, cleanup removes such folders only after 2 hours (`tasks.py:82`, `:383`), so manual and nightly backups fail in that window. I did not wait to see the cleanup happen.
- One backup started while a document was processing succeeded; that single attempt does not rule out the same failure during normal processing.

**H2 — A file being uploaded while the server is down is lost if the page is reloaded or closed before the request fails, although the screen says "trying again…".**
- Reproduce (mobile emulation): `docker compose … stop api`; Add → Take a photo → `judge.png`. The Library shows "Adding 1 of 1… Ripiano can't be reached; trying again…". Reload at about 18 s. Start the API.
- Result: no "waiting to upload" notice, no document, nothing in the device queue. The capture is gone without any message (`rec4.log`).
- Cause: the file is saved to the device queue only after the POST fails (`apps/web/src/App.tsx:1920`). With the API container stopped, the proxy held the request about 40 s before answering 502. There is no leave-page warning during an upload.
- Contrast: left alone for 45 s, the same file was kept, survived a reload, and was sent once (`rec5.log`).

### Medium

**M1 — Suggestions for documents split from one scan are driven by the file name, and can be confidently wrong.**
- Reproduce: upload `barcode-batch-desktop.pdf`; file part (1/2) with sender "Quokka Meadow Bank", type "Letter", tag "bank"; open part (2/2), whose text is "invoice wombat harbour".
- Result: it suggests that sender, type and tag with "shared: separator, barcode, desktop, batch".
- Cause: the rule that ignores a title still equal to the file name compares "barcode-batch-desktop (2/2)" with the stem "barcode-batch-desktop-2", which never match (`services/api/archive/classification.py:36`). The user guide says such titles are ignored.

**M2 — Inbox explanations are cut to one line, so the advice is hidden, worst on phones.**
- Reproduce: upload a truncated copy of `three-pages.pdf` and a garbage `.pdf`; open Inbox at 390 px.
- Result: "This PDF is damaged, so some of its pages may be mi…" and "OCR could not finish: Text recognition failed for this fil…". The text is 1044 px wide in a 294 px box, with no tooltip. It is also cut at 1440 px. The full text is readable in the Library row and the document panel.
- Cause: `apps/web/src/style.css:989` (`.document-info p`, `white-space: nowrap`); only the exact-copy note is exempted.

**M3 — Typing an existing name into "Add a type" or "Create a tag" in the document panel does not select it.**
- Reproduce: with type "Invoice" and tag "bills" already existing, open a document, use "Add a type" → "Invoice" and "Create a tag" → "bills", then Save changes.
- Result: the server answers 409 ("This name already exists"), and the document is saved without the type and tag. I did not capture whether an inline message appeared before the panel closed.

### Low

- **L1** A misspelled search ("bagder", "verificaton") returns nothing and offers no correction.
- **L2** A bare archive number ("900011") finds nothing; only `asn:900011` does. The empty-result tips do not mention `asn:`.
- **L3** A sticker code typed without its prefix ("MUD3PLDT") or pasted as a link is "Sticker not found".
- **L4** The Inbox item in the menu shows no count, so nothing draws the owner there when a file needs a look (the Library row and Overview do say so).
- **L5** On first-time setup, after a wrong setup key the "Invalid setup key." alert and the red field stay while the corrected form is blocked for another reason (password under 12 characters).
- **L6** A first-time owner sees 15 menu entries at once; the locations list shows a box before its shelf ("Study shelf / Box A", "Cellar box", "Study shelf").
- **L7** Uploading the same barcode batch twice puts three "exact copy" rows in the Inbox (the unsplit scan plus each part).
- **L8** The printable sticker page shows only the label; I saw no print control on it (I could not check in headless Chrome whether a print dialog opens by itself).

## Single most serious finding

**H1.** A worker killed at the wrong moment (power cut, NAS restart, out-of-memory) makes manual and scheduled backups fail with "Snapshot contains an unexpected media path", and the owner has no way to fix it from the app.

## Fixtures used

`office-letter.docx`, `office-open.odt`, `office-legacy.doc`, `office-slides.pptx`, `office-sheet.xlsx`, `judge.png`, `email-notice.eml`, `outlook-notice.msg`, `three-pages.pdf`, `barcode-batch-desktop.pdf`, `barcode-batch-mobile.pdf`, `asn-batch-desktop.pdf`, `asn-batch-mobile.pdf`, `tag-barcode-desktop.pdf`, `tag-barcode-mobile.pdf`.

Derived from `three-pages.pdf` for the damaged-file checks: first 70% of the bytes (truncated), 3,000 bytes zeroed in the middle (holed), plus a random-bytes `.pdf`, an empty `.pdf` and a text file named `.pdf`.

## Commands and scripts

All scripts are in `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j1r10/` and were run with `node <script>` (a `node_modules` symlink there points at `apps/web/node_modules`).

| Script | What it did |
| --- | --- |
| `s2.mjs` | First-time setup: wrong key, short password, then success |
| `s4.mjs`, `s7.mjs`, `s8.mjs` | Desktop upload of Office files; inline sender, type, tag; filing three documents |
| `s10.mjs` | "Learn now" and similar documents |
| `s11.mjs`, `s12.mjs`, `s14.mjs`, `s16.mjs` | Mobile camera input, batch upload, filing, accepting and rejecting suggestions |
| `s13.mjs`, `s15.mjs` | Uncertain suggestion on mobile and desktop, with network log |
| `s17.mjs`, `s18.mjs` | Search, qualifiers, filters |
| `s19.mjs`–`s23.mjs` | Locations, sticker, label, camera scan (`--use-file-for-fake-video-capture`), fallback, denied camera, move, history |
| `s24.mjs`–`s26.mjs` | Damaged PDFs, Inbox on desktop and mobile |
| `rec1.mjs`, `rec2.mjs` | `kill worker` after upload and mid-OCR, then `start worker` |
| `rec3.mjs` | `restart api` and `stop api` during a throttled upload |
| `rec4.mjs`, `rec5.mjs` | `stop api`, camera upload, reload at 18 s and after 45 s, `start api` |
| `s31.mjs`, `mcp.mjs`, `s32.mjs`, `s40.mjs` | Two agent grants, MCP calls, activity log, revocation |
| `s33.mjs` | Second account, Italian, isolation |
| `s34.mjs` | Keyboard-only and mobile control audit |
| `s35.mjs`, `bk.mjs`, `bk2.mjs` | Backups from the UI and API |

Compose commands used, all with `-p ripiano-j1 --env-file …/jstacks/j1/stack.env`: `ps`, `kill worker`, `start worker`, `restart api`, `stop api`, `start api`, `logs maintenance_worker`, `exec -T api …` (list the media folder; delete the one leftover work folder).

## State left behind

- Stack `ripiano-j1` is running; all nine services are up.
- Both agent grants I created are revoked (both tokens answer 401); the token file is deleted.
- Accounts: owner `nonna-anna` and family member `figlio-marco`; passwords are only in the scratch folder (`creds.txt`).
- Screenshots: `qa-artifacts/20261119-r10-judge-1/` (39 files; the token is blurred in `60-agents-two-grants-token-masked.png`).
