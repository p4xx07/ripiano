# Judge 2 — quality round 10

- **Candidate:** `5bc8c7de72619aac6ebea44b3cad7c69a610b31a` (branch `codex/initial-implementation`; HEAD `255f81d` adds evidence files only).
- **Date:** 2026-11-20 (local, Europe/Rome; 2026-11-19 UTC).
- **Stack:** my own, `http://localhost:18102`, Compose project `ripiano-j2`, started empty. Left running, all nine services up.
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (Chrome channel, headless). Desktop 1440x900; mobile emulation 390x844 (`isMobile`, `hasTouch`, DPR 2); one reflow check at 320x640.
- **Emphasis:** mobile, keyboard-only, assistive technology, Italian interface. Every journey ran with locale `it-IT`; the interface followed the device language without my choosing it.
- **Screen-reader stand-in:** no screen reader is installed. I used Playwright's accessibility tree (`locator.ariaSnapshot()`), the contents of `aria-live` / `role=status` / `role=alert` regions, and `document.activeElement` after every action. This is not a real VoiceOver/TalkBack run.
- **Screenshots:** `qa-artifacts/20261119-r10-judge-2/` (37 files; token values masked).

## Scores

| Dimension | Weight | Score | Evidence (what I ran) | Not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.2** | Setup in Italian on mobile by keyboard. Uploads through the camera input, the file browser and mixed batches (PDF, DOCX, DOC, ODT, PPTX, XLSX, EML, MSG, PNG); nothing required a visit to a TODO screen. Unsupported file in a batch of three: the two good files were added, the bad one named with a reason in an alert. Offline upload queued and sent by itself on reconnect; a request cut mid-flight was retried by itself, one copy. Filing by keyboard (new sender, type, tag) and by touch. Suggestions from a similar filed document appeared with the shared words, one tap to accept, one to reject, both announced. | Telegram and watched folder (not exercised). Gallery input (same control type as camera; not driven separately). Learned model suggestions (needs 10 filed documents). Real camera. |
| Retrieval and physical filing | 20% | **9.4** | On mobile: OCR phrase (`tassa rifiuti`, with snippet), Italian stemming (`contribuenti` finds `contribuente`), `sender:` and `mittente:`, `tag:`, `date:`, zero-result help text; result counts announced. Two nested locations, sticker created, copy moved, sticker found by code in lower case, unknown code and denied camera both announced as alerts. Label page is Italian HTML with a QR. | Reading a QR with a camera. Printing and re-scanning a label. Saved searches, custom-field filters. |
| UX and accessibility | 20% | **9.0** | All 15 screens on mobile: no horizontal overflow, no unnamed control, one heading 1 each, focus moved to the heading on navigation, no leftover English, no console errors. Skip link, `/`, `n`, `?`, `g`+letter, `j`/`k`/Enter, Esc; shortcuts do not fire inside a dialog. Document dialog traps Tab in both directions; mobile drawer makes the page inert and cycles Tab; unsaved-changes dialog is an `alertdialog` with name, description, 44px buttons, Esc and browser Back handled. Session expiry and conflicts (see below). Defects M1, M2, L1 lower this score. | Real screen reader, installed iOS/Android PWA, Android client. Dark/AMOLED contrast. English only spot-checked (language switch works and is announced). |
| Reliability and recovery | 20% | **9.1** | Worker stopped before upload, then killed while a document was `processing`: all documents ready, one copy each; the interrupted one recovered 201 s after the kill. Broker stopped during a camera upload: accepted, processed after the broker returned. Database restarted: documents listed again after about 5 s. API stopped during a save: the edit stayed in the form and saved after restart, but see M3. Backup from the UI completed with checksum verification. Session expiry mid-edit kept the draft and merged another member's edit. API suite re-run: `400 passed, 17 skipped in 63.44s`. | A restore on my own stack (I rely on `restore-drill-round10.md`, which is specific and credible: checksums, sticker, revoked grant, 81 migrations). Restarting the API in the middle of an upload body. |
| Privacy and agent control | 15% | **9.5** | Two grants created by keyboard, each needing the owner password; token shown once, announced, focus moved to it. Full agent: 6 tools. Title-only agent limited to tag "casa": 1 tool (`search_documents`), sees only "casa" documents, text read refused, and searching for words that exist only in document text returns nothing. Audit list shows successes and refusals per agent without query or text. Revocation asks for confirmation; both tokens return 401 afterwards, on existing and new sessions. Second family member: own archive empty, other documents 404, backups 403, admin screens absent. Request without CSRF token: 403. | Real cloud agent client. Two-step sign-in. Share links. |

**Weighted mean: 9.2** (2.30 + 1.88 + 1.80 + 1.82 + 1.425 = 9.225).

Below the 9.5 target, and UX and accessibility sits exactly at the 9.0 floor. I would not hand this build to a non-technical family member today because of M1 and M3; both look like small fixes.

## Hard gates

| Gate | Demonstrated? | Note |
| --- | --- | --- |
| 1. Parity scenarios | Partly, for what I ran | Capture, formats, search syntax, sharing, conflicts, physical archive, agents, backup, Italian. I did not audit every parity row. |
| 2. Fresh install, upload/OCR/search, backup, clean restore | Yes, with the restore taken from the drill record | Fresh setup, upload, OCR, search and backup done on my stack. Restore not repeated by me; `restore-drill-round10.md` records 13 of 13 checks on this commit. |
| 3. Installed iOS/Android PWA, native Android | **Out of scope by owner decision** (D7) | Also out of scope: real Telegram/Google/Microsoft/Dropbox accounts and checks on the Synology DS923+. No score lowered for these. |
| 4. Security review | Yes, for what I ran | Member isolation, agent scopes and document filter, revocation, CSRF, upload validation, no text to a title-only agent. |
| 5. Tests and builds | Credible | `round10-verification.md` has commands and result lines; my re-run of the API suite gave the same `400 passed, 17 skipped`. I did not run the build or e2e suite, as instructed. |

## Findings

No severe or high findings.

### Medium

**M1. A note typed but not added is thrown away, without warning, when you press "Salva modifiche".**
Repro: open any document, type in "Nuova nota", change another field (I set the ASN to 43), press "Salva modifiche". The dialog closes and announces "“…” salvato."; reopen the document: no note, empty field. Closing with Esc is protected (the unsaved-changes dialog appears for a typed note), so the form already treats the note as unsaved work; only Save ignores it.
Cause: `apps/web/src/DocumentPanel.tsx:781` counts `noteDraft` as dirty, but `save()` (`:462`, closes at `:500-501`) neither posts the note nor asks.

**M2. The conflict list runs its three pieces of text together, on desktop and mobile.**
Repro: open one document in two tabs, save a new title in tab 2, change the title in tab 1 and save. The notice reads "**Titolo**Valore più recente: Titolo dalla scheda 2Il tuo valore: Titolo dalla scheda 1" with the "Usa il mio valore" button in the middle of the line. The accessibility tree has the same run-on text ("…MarcoIl tuo valore…"). This is the one moment where the person must compare two values. Screenshots `13-…`, `16-…`.
Cause: `apps/web/src/DocumentPanel.tsx:948` and `SharedDocumentPanel.tsx:259` render `ul.draft-conflict-list` with adjacent `<strong>`/`<span>` elements; `apps/web/src/style.css` at HEAD has no rule for `.draft-conflict-list` (only `.draft-restored`, `:5377`).

**M3. With the API container stopped, Save shows "Salvataggio…" for more than 45 seconds with no message.**
Repro: open a document on mobile, change the ASN, `docker compose -p ripiano-j2 … stop api`, press "Salva modifiche". The button stays disabled as "Salvataggio…"; no alert or status appeared in 45 s of polling. It ended only when I started the API again (the request then returned 504 and the edit could be saved). In my earlier run, the alert "Ripiano si sta riavviando o non è disponibile. Riprova tra un minuto." appeared only once the API was back. Nothing was lost.
Likely cause: no client-side time limit on requests in `apps/web/src/api.ts:280-289`, and no `proxy_connect_timeout` in `apps/web/nginx.conf` (only `proxy_read_timeout 75s`, `:21`), so the default 60 s applies when the upstream container does not answer. Not confirmed beyond that.

### Low

**L1. Keyboard focus falls to the page body after four actions** (each announces its result correctly, and Tab stays inside the dialog where there is one):
- Sharing a document: "Condividi" by Enter in "Persone con accesso".
- Saving a shared document as the second member ("Salva modifiche" in the "Condiviso con te" dialog; the dialog stays open). Screenshot `17-…`.
- "Aggiungi posizione" in Archivio cartaceo when pressed as a button (pressing Enter in the name field keeps focus).
- "Riprova l'OCR" on a failed document in the Library list; here the second failure is also not announced, unlike the Inbox, where the retry start and result are both announced and focus stays on the button.

**L2. The unsaved-changes dialog offers "Continua a modificare" and "Scarta le modifiche" but no "Salva".** On a phone the Save button is far down the form.

**L3. Small wording and naming points in Italian.**
- "casa +1 altre" for one extra tag (should be "altra").
- "Da fare" status is "Completato" in the owner's dialog and "Fatto" in the shared dialog.
- Backup snapshots are headings made of the raw ID (`20261119T234107987200Z-de673080`); the readable date is plain text below.
- Inbox "Riprova l'OCR" buttons do not include the document name (the Library ones do).
- Creating a sender or type inline is not announced (creating a tag is).

**L4. A first suggestion needs three shared words of four or more letters, and a title still equal to the file name does not count.** With three filed fixtures and a fourth similar upload (`office-legacy.doc`) nothing was suggested until I gave two documents titles with common words. This is documented behaviour (`services/api/archive/classification.py`, "shared < 3"), but a new owner with short scans will see no suggestions at first and nothing says why.

## Things that worked notably well

- Session expiry in the middle of an edit: sign-in screen says the session ended and that unsaved changes are kept for 12 hours for that person only (with a "delete them" button); after signing in the document reopens, focus lands on the notice, the title, tag and typed note are back, and a title changed meanwhile by the other member is shown as a conflict with "Usa il mio valore". Final state had my title, his date, my tag.
- Two tabs or two members: changes to different fields merge silently; the same field gives a 409 handled in the form, nothing overwritten.
- Offline: "1 file è in attesa di caricamento. Ripiano lo invia quando torna la connessione." and it did.

## Most serious finding

**M1**: pressing Save discards a typed note without saying so. It is the only place I found where something a person typed is lost silently.

## Fixtures used

`three-pages.pdf`, `office-letter.docx`, `office-open.odt`, `office-legacy.doc`, `office-slides.pptx`, `office-sheet.xlsx`, `email-notice.eml`, `outlook-notice.msg`, `judge.png`, `barcode-batch-desktop.pdf`, `barcode-batch-mobile.pdf`, `asn-batch-desktop.pdf`, `asn-batch-mobile.pdf`, `tag-barcode-desktop.pdf`, `tag-barcode-mobile.pdf`. Two inputs of my own, kept in the scratch folder: the first 700 bytes of `three-pages.pdf` (a damaged PDF for the Inbox) and a one-line `.txt` (unsupported type).

## Commands and scripts

All scripts are in the scratch folder `…/scratchpad/j2r10/` (`lib.mjs`, `s01.mjs` … `s35.mjs`, `mcp.mjs`), each run as `node sNN.mjs`. Passwords, session states and agent tokens are only there.

| Script | What it did |
| --- | --- |
| s01–s03 | Setup screen, setup by keyboard, menu and Add dialog (mobile, Italian) |
| s04–s09 | Uploads, document dialog, filing by keyboard and touch, suggestions |
| s10–s12 | Shortcut list, People, second member, sharing with edit access |
| s13–s18 | Two members, two tabs, unsaved-changes dialog, session expiry, typed-note check, focus after shared save |
| s19–s21 | Backup, offline and interrupted uploads, Inbox retry |
| s22, s23, s32, s33, s33b | `stop`/`kill`/`start worker`, `stop`/`start api`, `restart db`, `stop`/`start broker` in `ripiano-j2` only |
| s24–s27, s35, mcp.mjs | Agents: create, MCP `initialize` / `tools/list` / `tools/call`, audit, revoke |
| s27–s29 | Search and filters, physical archive |
| s30–s31 | Sweep of all screens on mobile; keyboard, mixed upload, label, CSRF, member isolation |

Other commands: `docker compose -p ripiano-j2 --env-file …/jstacks/j2/stack.env ps`; `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q`; `git show HEAD:<path>` for the file references above.

## Clean-up

Both agent grants I created are revoked (tokens return 401). I changed no repository source file; the only files I added are this report and the screenshot folder. When I finished, `git status` showed uncommitted edits to ten files under `services/api/archive/` that are not mine (someone else was working in the tree). At the time of my API suite run the tracked tree was clean, so that result is for the candidate commit; my file references were checked with `git show HEAD:`. My stack holds 23 documents, two accounts (owner and one member), two locations, one sticker and one backup snapshot.
