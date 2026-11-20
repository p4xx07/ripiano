# Judge 1 — round 12 report

- Candidate: `71315f4531f0ef02d0205aa77bfdce0019c9c127` (branch `codex/initial-implementation`; HEAD at review time was `57c76a3`, an evidence-only commit on top of it; the running stack `ripiano-j1` was built from the candidate).
- Date: 2026-11-20, 11:16–12:40 CET. (The time box ran over: one Bash call waited roughly 55 minutes for a permission prompt between 11:38 and 12:35. No testing happened during that wait.)
- Stack: own Compose project `ripiano-j1`, http://localhost:18101. It started empty, and I did the first-time owner setup myself through the setup screen with the env file's setup key. The owner password is kept only in my scratch folder.
- Browser: Playwright 1.64.1 (`npx playwright --version`) with Google Chrome 157.0.8103.79 (channel `chrome`, headless). Desktop 1440x900 (en-US). Mobile emulation 390x844 with `isMobile` and `hasTouch` (en-US and it-IT).
- No screen reader is installed. As a stand-in I used Playwright's accessibility tree (`locator.ariaSnapshot()`).
- Artifacts: `qa-artifacts/20261120-r12-judge-1/` (40 PNGs; token fields masked before every screenshot).
- Permission notes: `curl` against localhost and some compound shell commands were denied. I did not work around them. All HTTP/API calls went through the signed-in page (`fetch` in Playwright), and MCP calls used Playwright's `request` API (`APIRequestContext`).

## Commands and scripts

All scripts are in the scratch folder `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j1r12/`:
`lib.mjs`, `01-setup.mjs` (owner setup), `02-upload.mjs` (Add dialog uploads: Browse files, Choose from photos, Take a photo), `03-open.mjs`, `04-file.mjs` (manual filing), `05-correct.mjs` (mobile suggestion correction), `06-mobile-camera.mjs` (Italian, mobile, camera input), `07-search.mjs`, `08/09/10-*.mjs` (paper archive, sticker, print, move, lookup), `11-qrcam.mjs` (in-app QR scan through a Chrome fake camera fed with the printed label, `ffmpeg` → `label.y4m`), `12-watch-upload.mjs` (upload + UI watch during worker stop/kill), `13/14/16-*.mjs` (agents create/revoke), `15-mcp.mjs` (Streamable HTTP MCP client), `17-look.mjs`, `18-api-down.mjs` (mobile upload while api stopped), `19-backup.mjs`, `20-keyboard.mjs`, `21-kbd-suggest.mjs`, `q.mjs` (API reads).

Service operations, all on my own project: `docker compose -p ripiano-j1 --env-file …/jstacks/j1/stack.env` with `ps`, `stop worker` / `start worker`, `kill worker` (mid-task), `stop api` / `start api` (during an upload), `logs worker`, and `exec api .venv/bin/python manage.py shell` (read-only checks of extracted text and processing times).
API suite: `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q -p no:cacheprovider` → **457 passed, 17 skipped in 81.91s**. This matches `round12-verification.md`.

## Fixture IDs used

three-pages.pdf, office-letter.docx, email-notice.eml, office-slides.pptx, office-open.odt, outlook-notice.msg, barcode-batch-desktop.pdf, asn-batch-desktop.pdf, tag-barcode-desktop.pdf, office-sheet.xlsx, office-legacy.doc, barcode-batch-mobile.pdf, judge.png (camera input, Italian, mobile), asn-batch-mobile.pdf (uploaded while the worker was stopped), tag-barcode-mobile.pdf (worker killed mid-task), three-pages.pdf again (uploaded while the api was stopped). That is all 15 fixtures.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | All 15 fixtures went in through the one Add dialog: Browse files with several at once, gallery input, and the camera input on mobile in Italian. judge.png was OCR'd and searchable 3.6 s after selection (21). Nothing passes through a mandatory TODO screen: documents land in the Library and the Inbox holds only the exact copy (37). PATCHT split, ASN (900021/900022/900012) and the hidden full scan worked. I filed 2 split parts manually (sender, type, tag; typing an existing name reuses it). Uploading the similar barcode-batch-mobile.pdf then produced explained suggestions ("Like … shared: separator, letter, meadow, quokka") (15). In one mobile screen I accepted the tag, rejected the wrong sender (recorded as `dismissed_suggestion` in history), picked another sender from the list, accepted the type and pressed Save (17, 18); the result was correct, with every origin `manual`. | Telegram (out of scope by owner decision). The watched folder was not exercised for lack of time. Real phone camera capture is out of scope (D7). |
| Retrieval and physical filing | 20% | 9.4 | Each search found the right documents: OCR phrase (`second heron`, `judge 9473`, `contribuente lampone`), sender (`sender:"Wombat Spa"`), tag (`tag:casa`), type, date (`date:2026-11`), and exclusion (`heron -otter` → none, correct). The typo `quoka` offered "Did you mean quokka" (23-*). The paper journey also worked end to end. I created nested locations, created a sticker in Box A, printed the label (popup with QR, code and place: 27) and moved the copy to Box B; the history shows both moves. Lower-case typed lookup works (29). **The in-app "Scan with camera" decoded the printed label's QR through a fake camera and opened the copy** (31). The `/?sticker=` link that a phone camera app opens lands on the copy (32). | Real phone camera (out of scope). |
| UX and accessibility | 20% | 9.1 | Keyboard-only: the skip link is the first Tab stop, `/` focuses search, `j`+Enter opens a document, 60 Tabs stay inside the dialog, and Esc returns focus to the row. `n` opens Add, `?` lists the shortcuts (45), and `g p` navigates. Accepting a suggestion by keyboard moves focus to the field it filled (46). The Italian UI was complete in the screens I used (19–21), and the mobile layout and 44px targets look right. The aria snapshot of Paper archive has a sensible heading and label structure. Friction: see M1 (a document waiting on a stopped worker looks identical to a normal "Waiting" everywhere except Overview). The native date input shows the OS locale (`gg/mm/aaaa`) in the English UI; that is browser behaviour and is not scored. | Installed iOS/Android PWA, Android client, and a real screen reader (out of scope or not installed; the aria tree was used as a stand-in). |
| Reliability and recovery | 20% | 9.0 | **Worker stopped:** the upload waits; `/api/jobs` reports `worker_not_running`; after start the document processes by itself. **Worker killed mid-task** (tag-barcode-mobile.pdf, `docker compose kill worker` right after the task was received): the UI said "Taking longer than usual. Processing was interrupted and will be tried again by itself" (38-killworker-2). After the restart it became ready automatically about 3 minutes later (processed 10:40:59Z vs. worker restart 10:37:57Z), with no duplicate. **API stopped during a mobile upload:** "1 file is waiting to upload. Ripiano couldn't be reached; trying again… / Send now" plus an offline banner (39-apidown-1/2). The file was sent automatically about 20 s after the api came back ("Added 1 document"). **Backup:** "Back up now" gave a complete snapshot `20261120T113742990996Z-5585aaac` (44). | I did not run my own `down -v` → restore on this stack (time). I read `restore-drill-round12.md` (PASS on this commit: originals, tags, locations, sticker lookup, revoked grants). |
| Privacy and agent control | 15% | 9.5 | I created two grants with the password confirmation. Grant A (cloud-like): search only, filtered to tag `casa`. Grant B (local): search, OCR text and tags, all documents. `tools/list`: A → `[search_documents]`, B → `[search_documents, get_document_text, list_tags, change_document_tags]`. A sees only `casa` titles; text words (`quokka`) and non-casa documents (`Avviso`) return nothing, and `get_document_text` is refused. B read the three-pages text, and was refused when it tried to add `casa` (another agent's filter tag: "only a person can add or remove it") and when it called `set_document_filing` (not granted). Each call, including the refusals, appears in the Agents activity log, and no text is stored there. After revoke, the next MCP `initialize` → **401**. All four grants I created are revoked. | None within scope. |

**Weighted mean:** 0.25·9.0 + 0.20·9.4 + 0.20·9.1 + 0.20·9.0 + 0.15·9.5 = **9.18**

## Hard gates

| Gate | Status |
| --- | --- |
| 1 Parity scenarios | Partly demonstrated by me: upload channels (web, Office, email, .msg), barcode split/ASN, tags/senders/types, suggestions, search syntax, duplicates, notes and history views, stickers, agents, backup. I did not audit every row. |
| 2 Fresh install, upload/OCR/search, backup, clean restore | Install, upload/OCR/search and backup were demonstrated on my stack. Clean-stack restore is not my own run: I rely on `restore-drill-round12.md` (PASS, same commit). |
| 3 Real-device iOS/Android PWA and native Android | Out of scope by owner decision (D7). |
| 4 Security (isolation, revocation, CSRF, upload validation, no default content transfer) | Agent isolation, scope enforcement, filter-tag protection and revocation (401) were demonstrated. CSRF and upload validation were not probed this round. No AI provider is configured, and semantic search is off by default. |
| 5 Tests/builds/journeys/migrations | API suite re-run: 457 passed, 17 skipped (matches the record). The build, e2e (402 passed / 48 skipped) and migration check are recorded credibly in `round12-verification.md` with commands; I was not allowed to re-run them. |
| Synology NAS performance/ACL/restore | Out of scope by owner decision. |

## Findings

### Severe
None.

### High
None.

### Medium
**M1 — A stopped OCR worker is only explained on Overview; the Library, the document and the Inbox show a plain "Waiting".**
Repro:
1. Run `docker compose -p ripiano-j1 … stop worker`.
2. Upload asn-batch-mobile.pdf from the Library.
3. Wait over 2 minutes. `/api/jobs` now returns `problem: "worker_not_running"` and the document state is `waiting_for_worker`.

What each screen shows:
- **Library:** the row still says "Waiting" (34).
- **Document dialog:** nothing about processing apart from "Available once processing has finished" next to one action (36).
- **Inbox:** nothing (37).
- **Overview:** the only place with the explanation: "text recognition is not running … Start the Ripiano worker container again" (35).

A family member who uploads and stays in the Library gets no hint that nothing will happen. Cause: the only consumer of `worker_not_running` / `waiting_for_worker` in the web app is `apps/web/src/JobsPanel.tsx:14-40,106` (verified with `git show HEAD:`); the Library row and the document panel do not use the jobs health.

### Low
- **L1 — Slow automatic recovery after a worker is killed mid-task.** A document in flight when the worker is SIGKILLed is picked up again about 3 minutes after the restart (10:37:57Z → 10:40:59Z). Meanwhile the UI wording is honest ("will be tried again by itself; you can also retry or cancel"), so this is friction rather than a defect.
- **L2 — Suggestions are silent for short similar documents, and the hint wording misleads.** I filed office-letter.docx and office-slides.pptx (sender/type/tag) and then uploaded office-sheet.xlsx ("Ripiano Excel verification 2026"). It got no suggestions because only 2 distinctive words are shared, and the panel still says "Suggestions appear here after you have filed a few similar documents" (11), although two similar ones were filed. The threshold is `services/api/archive/classification.py:119` (`len(shared) < 3`) and the text is `apps/web/src/locales/DocumentPanel.ts:17`. Longer documents (barcode-batch) were suggested correctly.
- **L3 — After moving an upload to the Library, the row can lag behind the real state.** In the mobile camera run, the API reported `ready` while the row still showed "In elaborazione" for a moment (21). It refreshes on the next poll. Cosmetic.

## Most serious finding
M1: a stopped OCR worker is explained only on Overview. In the Library and the document view, a document that will never be processed looks the same as one that is about to be processed.
