# Judge 2 — round 11 report

- Candidate: `1c823549b93d3d9f8a65866d2e2d26e192e1df5e` (branch `codex/initial-implementation`; HEAD `5925b9a` only adds evidence files on top, verified with `git diff --stat 1c82354 HEAD`).
- Date: 2026-11-20, 09:33–10:10 CET.
- Stack: own Compose project `ripiano-j2` at http://localhost:18102, built from the candidate by the orchestrator, empty at start. Not rebuilt. Left running.
- Browser: Playwright `Version 1.64.1`, Chrome channel `Google Chrome 157.0.8103.79`, headless. Desktop 1440×900; mobile emulation 390×844 (`isMobile`, `hasTouch`, DPR 2); locales `en-US` and `it-IT`.
- Accessibility: no screen reader installed; Playwright `locator.ariaSnapshot()` was used as a stand-in for the accessibility tree.
- Permissions: `curl` was denied by the permission system and was not used. HTTP API and MCP calls went through Playwright instead: in-page `fetch` with the session and CSRF cookie, and Playwright `request.newContext()` with the agent bearer token for MCP.

## Commands and scripts

All scripts, passwords, tokens, and id lists are in `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j2r11/`. They were run from `apps/web` as `node <scratch>/sNN-*.mjs`.

- `lib.mjs` holds the helpers: launch, login, in-page API, screenshots. `mcp.mjs` is the Streamable HTTP MCP client (`initialize`, `notifications/initialized`, `tools/list`, `tools/call`). `dc` wraps `docker compose -p ripiano-j2 --env-file …/jstacks/j2/stack.env`.
- s01–s02: first-run setup in the UI. A short password was blocked client-side ("Use at least 12 characters"), a wrong setup key showed "Invalid setup key.", and the correct key created the owner.
- s03–s04, s13: desktop "Browse files" with 6 files; mobile "Take a photo" (input has `capture=environment`), "Choose from photos", and "Browse files".
- Consume folder: `dc cp …/tag-barcode-desktop.pdf maintenance_worker:/consume/scan-from-printer.pdf`. It was imported with the label "from NAS folder", and the file was removed from `/consume`.
- s08, s10–s12, s49: filing three documents by hand, uploading similar documents, then accepting, rejecting, and correcting suggestions; the suggestion API was also checked for every document.
- s14–s15: 26 Library searches in the UI and through the API.
- s16–s23: Paper archive. Created nested locations, created stickers, looked up a sticker, moved a copy, checked its history, printed copy and location labels, decoded their QR codes (with pyzbar inside the `worker` container via `dc cp` and `dc exec`), and opened the QR URLs on mobile, both signed in and signed out.
- s25–s29: killed the worker mid-split (`dc kill worker`), took a backup with the worker dead, watched stall detection with the worker down for about 6 minutes, then `dc start worker`.
- s31–s33: `dc stop api` during a desktop upload; `dc stop api` during a mobile camera upload, followed by a page reload and closing the tab; `dc stop broker` during an upload.
- s34–s36, s41–s42, s54: two MCP agents created in the UI, tools/list, search, text and tag calls inside and outside each grant, the workflow hold-back, the audit log, revoking both agents (each in the UI), and a 401 check after each.
- s37–s40, s45, s50–s51: created member `maria` in the UI, a "When I change a document" share workflow, and a manual view share. Checked CSRF, a mixed invalid upload, anonymous access, and member isolation.
- s43–s44: keyboard-only checks: skip link, `?`, `/`, `j`/`k`/Enter, Esc, the focus trap (80 Tabs), `g p`, `g o`, `n`, and focus return.
- s24, s30, s52–s53: every screen in Italian (desktop and mobile), a scan of the Italian text for English leftovers, horizontal-overflow checks on 9 mobile routes, and the mobile menu and filters.
- s46–s47 plus the restore drill on my own stack:
  1. `s46-state.mjs state-before.json` (SHA-256 of every original through `/original`, locations, sticker, grants, workflows, share, search, MCP status).
  2. **Back up now** in the UI, giving snapshot `20261120T090004577280Z-102dcf64`.
  3. `dc down -v`
  4. `dc up -d db broker api` and wait until healthy (`showmigrations` ends at `0064`).
  5. `dc stop web worker maintenance_worker scheduler mcp api`
  6. `dc run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261120T090004577280Z-102dcf64 --yes` gave "Snapshot restored."
  7. `dc up -d`
  8. `s46-state.mjs state-after.json` and a diff of the two states.
- API suite: `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` gave `438 passed, 17 skipped in 76.63s`.

## Fixture IDs used

All 15 files were used: `three-pages.pdf`, `office-letter.docx`, `email-notice.eml`, `outlook-notice.msg`, `office-legacy.doc`, `office-open.odt`, `office-sheet.xlsx`, `office-slides.pptx`, `judge.png` (camera, gallery, and offline-camera uploads), `asn-batch-mobile.pdf`, `asn-batch-desktop.pdf`, `barcode-batch-desktop.pdf`, `barcode-batch-mobile.pdf`, `tag-barcode-mobile.pdf`, and `tag-barcode-desktop.pdf` (through the consume folder). Two synthetic invalid files were used only for the upload-validation check: `bad/invoice.pdf` (not a PDF) and `bad/script.sh`.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.0** | All four channels I could reach landed in the Library with no mandatory review step: camera (`capture=environment`), gallery, PDF/Office/email files, and the consume folder ("from NAS folder"; file removed after import). Status is announced ("Added 6 documents. Show", "Adding 1 of 1…"). Six mixed formats were ready in 10.8 s. Exact copies are flagged and kept, and Inbox offers "Keep both / Move this copy to Trash". After filing three Office documents by hand, the new `office-sheet.xlsx` showed four suggestions, each with its example document and shared words. In one dialog I accepted a tag and the sender, rejected "Test files" (recorded and not suggested again), created a new type, and saved; a title typed beforehand was kept. History records each step. Screenshots `02`, `03`, `04`–`06`. Friction: suggestions say nothing about how certain they are. The threshold (≥3 shared words, similarity ≥0.3) is conservative: `office-slides.pptx` ("Ripiano PowerPoint verification 2026") got no suggestion at all next to four filed "Ripiano … verification 2026" documents. Tapping a suggestion saves at once while other edits still need Save; this is announced, but it is two save models in one form. | Telegram (real bot): out of scope (D7). Native Android scanner: out of scope. |
| Retrieval and physical filing | 20% | **8.8** | The OCR phrase ("first otter" from a scanned PDF), sender (`sender:"Ripiano Lab"`, `mittente:comune`, plain "Comune di Esempio"), date (`date:2026-11`, `date:2026-11-10`), tag (`tag:Office`, `etichetta:casa`), `OR`, `-type:`, and `is:untagged` all returned exactly the expected sets. Email body text ("tassa rifiuti", "120 euro") and ODT text ("girasole") are searchable. The Filters panel (tag, paper copy, sender, type, date range) works on mobile. Nested locations work. A sticker typed in lowercase is found. The sticker and location labels print as HTML; their QR codes decode to `http://localhost:18102/?sticker=R-…` and `?location=L-…`, which open the Paper archive with the result even after a signed-out sign-in. A move is announced with "If its sticker shows the old location, print it again" and appears in the copy's history. A full restore kept stickers and locations. Friction: see M3. The sticker result card only offers "Open document"; moving the copy then needs scrolling about 3,400 px on mobile to Paper copies. Location lists are sorted by leaf name, so a child appears before its parent (L3). | Live camera QR scan: headless Chrome had no camera ("Ripiano may not use the camera … type the code" fallback shown); the printed QR codes were decoded offline instead. |
| UX and accessibility | 20% | **9.0** | Calm, consistent UI with no mobile horizontal overflow on 9 routes. The skip link moves focus to main. Shortcuts work: `?` lists them, `/` focuses search, Esc moves to the first result, `j`/`k`/Enter open a document, the dialog traps focus (0 escapes in 80 Tabs), Esc and Close return focus to the row, and `g p`, `g o`, `n` work. Labels and roles are present throughout the aria snapshots. Italian covers every screen including API errors ("Usa un numero dopo asn:"); my English-leftover scan found only placeholders and user data. Mobile filing rows are at least 44 px high; only the raw 13 px checkbox glyphs are smaller, and their whole rows act as labels. Friction: English plurals on Overview ("1 exact copies to review", L1). The owner sees "Backups are visible to the archive owner." before the first backup (L2). The mobile document dialog is very long (Paper copies at about y=3,444). | Installed iOS/Android PWA and the Android client: out of scope (D7). No real screen reader (ariaSnapshot stand-in). |
| Reliability and recovery | 20% | **9.1** | **API stopped during an upload:** a banner said "1 file is waiting to upload… trying again" with **Send now**, and the upload went out by itself when the API returned. **API stopped during a mobile camera upload, then a reload and closing the tab:** an offline page said "1 file is waiting on this device…", and the file uploaded once after the API returned (count +1, no duplicate). **Broker stopped:** `/healthz` returned 503 `{"status":"unavailable"}`, the upload was accepted (202, pending), and it was processed within about 10 s of the broker returning. **Worker killed mid-split:** **Back up now** still finished ("The snapshot passed its checksums"). The document was flagged "Taking longer than usual … will be tried again by itself" with Retry/Cancel about 2 min after the kill, and requeued about 1 min later. After `start worker`, all 5 waiting items finished within 20 s with each split part present once. **Own clean-stack restore drill** (`down -v` → restore): every original SHA-256 matched, and titles, sender, type, tags, both stickers with nested locations, the share with Maria, the workflow, OCR search, revoked agent B (401), active agent A (200), and the migration set (0064) were all identical. Friction: M1 and M2. | Synology restore and DS923+ load: out of scope (D7). |
| Privacy and agent control | 15% | **9.5** | Two agents were created in the UI, each requiring the owner's password; the token is shown once, with the MCP URL. A ("Local Mac": search, text, and tags, Office only) lists 4 tools; B ("Cloud": search only, all documents) lists only `search_documents`. B never sees text: "girasole" (text only) returned nothing, results carry no snippet field, and `get_document_text` and `change_document_tags` answer "Tool is not permitted for this agent". A cannot read or tag a Casa document ("Document not found within this grant"), and an unknown tag is refused. The audit log lists each call with done/refused/failed and no text. The D12 hold-back works: when A added `Casa` to an Office document, the owner's "share with Maria" workflow ran with "skipped sharing (an agent made the change…)" and Maria saw nothing. Revoking B made the next MCP request return 401 while A kept working. After restore, the grant states held. Also checked: CSRF missing → 403; anonymous API and original → 401; Maria sees only the shared document, cannot PATCH it (403), and sees only a name directory on `/api/people` and 403 on backups. | Real cloud MCP client and provider traffic: not exercised (direct protocol calls only). |

**Weighted mean: 0.25×9.0 + 0.20×8.8 + 0.20×9.0 + 0.20×9.1 + 0.15×9.5 = 9.06**

## Hard gates

| Gate | Status in this review |
| --- | --- |
| 1. Parity rows have a scenario or accepted deviation | Partly demonstrated. I exercised upload channels, Office/email conversion, barcode/ASN split, OCR search with field syntax, tags/senders/types, suggestions, duplicates, history, share and object permissions, workflows, agents, backups, and localization; none were missing. I did not verify the table row by row (mail IMAP, cloud Sources, page editing, custom fields, bundles, and email sending were not exercised). |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **Demonstrated on my own stack**: setup with the setup key, then upload/OCR/search, UI backup, `down -v`, `restore_snapshot`, and identical state including originals, tags, locations, and revoked grants. `.omo/evidence/restore-drill-round11.md` read and consistent with this. |
| 3. Installed iOS/Android PWA and native Android on real devices | **Out of scope by owner decision (D7).** Not scored. |
| 4. Security review | Partly demonstrated: account isolation, agent isolation and filters, token revocation (401), CSRF (403), upload validation (fake PDF and `.sh` refused with clear messages, valid file in the same batch accepted), no text to a search-only agent, and the D12 hold-back. No code-level security audit was done. |
| 5. Tests, builds, journeys, migrations | API suite re-run: `438 passed, 17 skipped`, matching `round11-verification.md`. Migrations on the stack end at 0064. The build and e2e records in `round11-verification.md` look credible: explicit commands and result lines, plus an honest note about earlier flaky mobile runs. I did not re-run them, as the brief instructs. |
| Real Telegram/cloud accounts, DS923+ performance/ACL/restore | **Out of scope by owner decision (D7).** |

## Findings

No severe or high findings.

### Medium

**M1 — No warning when the OCR worker is not running; queued documents wait forever with no explanation.**
- Repro:
  1. `dc kill worker`.
  2. Upload any file, or have one interrupted.
  3. Wait 5+ minutes and open Overview.
- Result: Background jobs lists each document as "Queued since 9:44 AM" with only Cancel. "Needs a look" has nothing about it. The only hint is "Background queues: 32 OCR". An interrupted document briefly shows "It was interrupted and will be tried again by itself", which cannot happen while no worker runs; after the requeue that message reverts to plain "Queued since…".
- Screenshot `17-overview-worker-down-5min.png`.
- Cause: stall detection only covers documents in `processing` with a claim (`services/api/archive/tasks.py` `reconcile_pending_documents`, around lines 486–511 at `1c82354`). Nothing checks whether any OCR worker is consuming the queue, and the worker service has no healthcheck.
- On a 4 GB NAS, a stopped or hung worker is a realistic case.

**M2 — Every pending document is re-queued every minute, so the OCR queue fills with duplicate messages.**
- Repro: leave 5 documents pending with the worker down for about 6 minutes. Overview then shows "Background queues: 32 OCR" for 5 documents.
- Cause: `services/api/archive/tasks.py:511` at `1c82354` (`for document_id in Document.objects.filter(status=PENDING …)[:100]: process_document.delay(...)`), scheduled every 60 s (`ripiano/celery.py` "reconcile-pending-documents").
- The same happens with a live but busy worker during a large import: each minute adds up to 100 duplicates, each a row-locking no-op. Correctness held (no duplicate processing was observed), but the queue depth shown to the owner is misleading and the broker queue grows without limit while the worker is down.
- This also bears on the "keep the NAS light" rule.

**M3 — After scanning a paper copy's sticker you cannot move it from the result.**
- Repro (mobile):
  1. Open `/?sticker=R-…` (the label QR) or type the code.
  2. The result card shows the document and its place, with only **Open document**.
  3. The document dialog opens at the top. Paper copies is about 3,400 px further down (y=3,444 in a 844 px viewport).
- Moving the copy therefore takes scan → open → about four screens of scrolling → choose location → Move.
- Location stickers show a count of copies but offer no "move a copy here" action.
- Code: `apps/web/src/PhysicalPanel.tsx:329` (the only action on the found copy).
- Screenshots `12`, `14`.
- This is the core physical-filing journey from the rubric.

### Low

- **L1** — The English Overview messages ignore the count: "1 exact copies to review", "1 follow-ups are overdue", "1 mailboxes have a problem" (`apps/web/src/locales/OverviewPanel.ts:10-15`; the Italian versions handle the plural).
- **L2** — Before the first backup, the archive owner sees "Backups are visible to the archive owner." instead of "No backup yet". A non-complete backup status is printed raw and untranslated (`apps/web/src/OverviewPanel.tsx:110`).
- **L3** — The location list and the "Inside" / "Location for the new paper copy" selects are ordered by leaf name, so "Studio shelf / Box Casa 2026" appears above "Kitchen drawer" and "Studio shelf". Children are not grouped under their parents. Screenshot `07`.
- **L4** — Suggestions show the example and shared words but not how certain they are. The ≥3-shared-word rule (`services/api/archive/classification.py:119-122`) gives nothing for short documents that clearly belong with filed ones (`office-slides.pptx`). This is conservative by design; noted as filing friction.
- **L5** — Source names are inconsistent: the workflow "Came from" list says "Watched folder" and "S3 bucket" (no WebDAV, Drive, OneDrive, or Dropbox), while the Library row says "from NAS folder".

## Most serious finding

**M1/M2 together.** When the OCR worker stops, Ripiano keeps accepting documents but never tells the owner that nothing is being read. Meanwhile the every-minute reconcile keeps stacking duplicate OCR tasks (`tasks.py:511`), so the only visible clue, the queue count, grows without limit and does not reflect the real number of waiting documents.

## Cleanup

- Both agent grants I created (`Local Mac worker`, `Cloud assistant`) are revoked; each token now gets 401.
- Member account `maria` and the share workflow remain on my stack only.
- The stack is running and healthy after the restore.
- 40 screenshots are in `qa-artifacts/20261120-r11-judge-2/`, with agent tokens masked.
