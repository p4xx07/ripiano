# Judge 1 — round 7 report

- **Candidate SHA:** 2e97ca193004cae30da90c067357f89478e135f9 (`codex/initial-implementation`), judged on the running stack at http://localhost:18080.
- **Date:** 2026-11-19 (run 10:45–11:10 local).
- **Account:** judge1 (own data only; earlier-round documents in this account were left untouched apart from revoking two stale agent grants created by judge1 in earlier rounds).
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (channel `chrome`). Desktop 1440x900; mobile emulation 390x844, `isMobile`, `hasTouch`, DPR 2. Locales en-US and it-IT.
- **Emphasis (per assignment):** first-time owner on desktop, key journeys repeated on mobile; damaged files, unsaved-edit handling, physical filing (paper copies, moves, stickers).
- **Artifacts:** `qa-artifacts/20261119-r7-judge-1/` (39 PNGs; token field and MCP URL masked in `d21-*`). Scripts, copies of fixtures and the token file are in my scratch folder (`…/scratchpad/judge1/r7/`), not in the repository.

## Commands and scripts

All scripts are Node ES modules run from `apps/web` with `timeout N node <scratch>/judge1/r7/<script>.mjs`; they import `@playwright/test` from `apps/web/node_modules` by absolute path. The password is read from `judges.env` at run time and never printed.

| Script | What it does |
| --- | --- |
| `s1.mjs` | Sign in, capture Library (`d01-home`). |
| `s2.mjs` | Add document → Browse files: `r7j1-three-pages.pdf`, `r7j1-office-letter.docx`, `r7j1-email-notice.eml`, `r7j1-damaged.pdf` (first 1200 bytes of three-pages.pdf); then Choose from photos: `r7j1-gallery.png`; wait 40 s; reload (`d04`). |
| `s3`–`s5.mjs` | Open document; unsaved-edit guard via Esc, browser Back, "Open earlier copy", sidebar navigation, page reload (`d05`–`d07`). |
| `s6`–`s8.mjs` | Title/date/new sender/new tag, Save; create paper copy + sticker in "Studio scaffale / Scatola 2026"; move to "Armadio ingresso"; History; fetch sticker label; searches (`d09`–`d12`). |
| `s9`, `s12.mjs` | Render label; Paper archive; sticker Find with code, full QR URL, and malformed code (`d12`, `d15`, `d16`). |
| `s10`, `s11.mjs` | Mobile: open `/?sticker=…` (what a phone camera does with the QR), lowercase code, scanner-wedge URL, camera-input upload, mobile Back guard + discard, mobile paper-copy move, touch-target and overflow checks (`m02`, `m03`, `m06`–`m08`). |
| `s13`, `s14.mjs` | Inbox; learned suggestions on `r7j1-gallery`: accept one, reject one while an unsaved title edit is pending, correct sender in the same screen, sender search (`d17`–`d19`). |
| `s15`–`s17.mjs`, `mcp.mjs` | Agents: create "R7J1 Local" (all four permissions, all documents) and "R7J1 Cloud" (titles only, only tag `r7j1-affitto`), each with password confirmation; MCP Streamable HTTP initialize / tools/list / tools/call via `fetch`; audit list; revoke Cloud (and stale R6J1 Local, R5J1 Cloud); re-run MCP (`d20`–`d23`). |
| `s18.mjs` | it-IT desktop, keyboard only: skip link, `/` shortcut, Tab to result, Enter to open, guard after keyboard tag toggle and after a note draft, Discard, focus return (`k01`–`k03`). |
| `s19.mjs` | Mobile: Retry OCR on the damaged PDF; offline upload (`context.setOffline`) then reconnect; first POST aborted with `connectionreset` then automatic retry (`m09`–`m12`). |
| `s20.mjs` | Invalid uploads: zero-byte `.pdf`, 4 KB random bytes `.pdf`, PNG renamed `.pdf`; damaged document dialog and original download (`d24`, `d25`). |
| `s21.mjs` | Mark paper copy missing, sticker lookup while missing, Mark found; dialog heading/label audit (`d26`). |
| `s23.mjs` | Concurrency: unsaved title edit open in the dialog while the MCP agent removes a tag; then Save; read the document back through the API (`d27`). |
| `s24.mjs` | it-IT mobile: Library, `sender:` and `mittente:` search, document dialog, revoke the last grant by touch (`m14`–`m17`); `mcp.mjs revoked` confirms both new tokens → 401. |

## Fixture IDs used

`three-pages.pdf` (as r7j1-three-pages.pdf, and truncated to 1200 bytes as r7j1-damaged.pdf), `judge.png` (r7j1-gallery.png, r7j1-m-camera.png, and renamed r7j1-png-as.pdf), `office-letter.docx`, `email-notice.eml`, `office-open.odt` (r7j1-m-offline.odt), `office-sheet.xlsx` (r7j1-m-aborted.xlsx). Synthetic negatives: zero-byte `r7j1-empty.pdf`, random `r7j1-garbage.pdf`.

## Scores

| Dimension | Weight | Score | Evidence (what I exercised) | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.0** | Multi-file web upload (PDF/DOCX/EML + damaged PDF) all reached the Library immediately with status chips; gallery and camera inputs (desktop + mobile); email got its subject as title, date and auto tag "Tasse". No mandatory TODO screen: the Inbox lists only failures and exact copies. Learned suggestions ("Add tag: Utenze", "Set sender…", "Set type…") show their reason, can be accepted or rejected one tap each in the document screen, and do not discard a pending title edit; sender corrected in the same screen. Invalid uploads are refused per file with clear reasons ("File is empty", "could not be read as a PDF… not really a PDF") while the valid file in the same batch is added (`d24`). A PNG renamed .pdf is accepted and processed correctly. | Telegram and real camera hardware (out of scope D7). I did not re-exercise the watched folder this round (earlier NAS-folder imports are visible in the account). Friction: Save closes the dialog, so adding a paper copy right after filing means reopening; the damaged-file message still says "Choose Retry OCR" after Retry has already failed. |
| Retrieval and physical filing | 20% | **8.8** | OCR phrase ("first otter"), title word, sender (`sender:"…"`, also `mittente:` in Italian), exact date `2026-10-03`, month `date:2026-10`, tag and `tag:` all find the document; sticker code from Library search. Paper copy created with sticker R-M8P2DCZM, moved twice (desktop and mobile touch), history lists every placement with user and time, label printed (70x40 mm, QR + title + code + path, `d12`) and the move message tells you to reprint. `/?sticker=…` (what a phone camera opens) lands on the result; lowercase code with spaces works; Missing/Found with last-known location works and is reflected in lookup. | Physical printing and a real camera scan (out of scope). Defect: scanning/pasting the QR content into "Find a sticker" fails with a generic server error (M1). Moving a copy after a scan requires Open document and scrolling to the last section of a long dialog. |
| UX and accessibility | 20% | **8.9** | Keyboard: skip link first, `/` focuses search, 6 Tabs to the first result, Enter opens the dialog with focus on Close, Esc/Discard returns focus to the originating row. Unsaved-edit guard works for Esc, browser Back (desktop and mobile), "Open earlier copy", sidebar navigation, keyboard tag toggles and an un-added note draft, with an inline Keep editing / Discard step. Italian is complete on the screens I visited (login, Library, document dialog incl. change history, Paper archive, Agents). Mobile: no horizontal overflow, no tappable control under 40 px tall on Paper archive or the document dialog (tag checkboxes are 13 px but sit inside full-width label rows). | Real screen readers and installed PWAs (out of scope). Defects: page reload / tab close loses unsaved edits without warning (L1); the dialog does not refresh after an agent changes the open document (L2); long document dialog puts Paper copies last on mobile (L3). |
| Reliability and recovery | 20% | **9.0** | Offline upload queued with a clear banner ("1 file is waiting… Send now") and sent automatically on reconnect; an upload whose POST was reset was retried automatically and landed once; damaged PDF fails with a clear reason, Retry OCR re-runs and fails cleanly, the original (1200 bytes) still downloads; Save after a concurrent agent edit sends only changed fields, so the agent's tag removal was not overwritten (`d27`). Restore drill `.omo/evidence/restore-drill-round7.md` on this exact SHA is credible (checksums of all originals, tags, nested locations/sticker, revoked vs active grant) and I count it for hard gate 2. | Worker/service restart and my own backup/restore (not allowed on the shared stack). |
| Privacy and agent control | 15% | **9.3** | Two grants with different scopes and filters; password required to create; token shown once with MCP URL. tools/list: Local = 6 tools, Cloud = `search_documents` only. Cloud with tag filter sees only the `r7j1-affitto` document, matches titles but not OCR text ("first otter" → 0), and `get_document_text` is refused. Local reads text and changes tags; its attempt to add a tag that is another active agent's filter is refused. Audit shows each call with outcome (done/refused) and document title, no text. Revocation takes effect at once (initialize → 401) for both tokens; Italian revoke confirm on touch works. | Real cloud agent account (out of scope). The audit entry for a refused call does not say why (minor). |

**Weighted mean:** 0.25·9.0 + 0.20·8.8 + 0.20·8.9 + 0.20·9.0 + 0.15·9.3 = **8.99**

## Hard gates

| Gate | Status in this review |
| --- | --- |
| 1. Parity rows have scenarios / accepted deviations | Partially demonstrated: every capture/retrieval/physical/agent row I touched worked; I did not walk the full parity table. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Upload/OCR/search demonstrated live; install/backup/restore accepted from `restore-drill-round7.md` (same SHA, credible). |
| 3. Installed iOS/Android PWA and native Android on real devices | Out of scope by owner decision (D7). |
| 4. Security review (isolation, revocation, CSRF, upload validation, no default content transfer) | Agent isolation, tag-filter scope, text permission, immediate revocation, upload validation demonstrated. CSRF and cross-account isolation not tested by me. |
| 5. Tests, builds, journeys, migrations, deployment checks | Not run by me (judging the running build only). |
| Synology DS923+ performance/ACL/restore, real Telegram/Google/Microsoft/Dropbox | Out of scope by owner decision (D7). |

## Findings

No severe or high findings.

### Medium

**M1 — Scanning the QR content into "Find a sticker" fails with "The server sent an unexpected reply. Try again."**
The copy label's QR encodes `http://<origin>/?sticker=R-…` (`services/api/archive/physical_views.py:420`). A USB/Bluetooth barcode scanner, or a phone QR app that pastes text, puts that URL into the Paper archive "Find a sticker" box, which the card itself invites ("Scan a QR code or type the code…"). The client uppercases it and requests `/api/stickers/HTTP%3A%2F%2F…`, which returns a non-JSON 404, so the user sees a generic server error rather than the copy (and not even "Sticker not found").
Repro: Paper archive → Find a sticker → paste `http://localhost:18080/?sticker=R-M8P2DCZM` → Enter (`d16-sticker-find-full-url.png`). Typing `R-M8P2DCZM` works.
Cause: `apps/web/src/PhysicalPanel.tsx:85` — `findSticker` only trims/uppercases; it should extract the `sticker`/`location` parameter from a pasted URL (and map an HTML 404 to "Sticker not found").

### Low

**L1 — Reload or tab close silently discards unsaved document edits.** The in-app guard covers Esc, Back, links and navigation, but there is no `beforeunload` handler (`apps/web/src/DocumentPanel.tsx:122` deliberately avoids browser dialogs). Repro: open a document, change Title, press F5 → page reloads, edit lost, no prompt (s5: 0 beforeunload dialogs).

**L2 — The open document dialog shows stale values after another actor changes the document.** Repro: open "r7j1 Lease otter" (Utenze checked), have the MCP agent remove Utenze, the checkbox stays checked. Saving is safe (only changed fields are sent; server kept the removal), but what the user sees is wrong until reopening.

**L3 — Moving a paper copy after a scan is several steps away.** The sticker result (`m02`) offers only "Open document"; the move control is the last section of a long dialog (after Share, Email…; `m08`). On a phone this is a long scroll for the most common physical action. The second "No location yet / Create sticker" row directly under an existing copy also reads as if it belonged to that copy.

**L4 — Damaged-file guidance does not change after a failed retry.** After Retry OCR fails again, the row still says "Choose Retry OCR. If it fails again…" (`services/api/archive/tasks.py:35`), so the user is invited to repeat a step that already failed.

**L5 — Save closes the document dialog.** After saving filing details the user returns to the Library; adding a paper copy or note right after requires reopening the document (`d09`).

**L6 — "Keep editing" returns focus to an unnamed input** (s18 reported `INPUT ""` as the focused element after choosing Keep editing with the keyboard) rather than to the field that was being edited or the dialog heading.

## Most serious finding

**M1:** a scanned or pasted sticker QR (a URL, which is what the printed label actually contains) cannot be looked up in "Find a sticker" and produces a misleading "The server sent an unexpected reply" error — `apps/web/src/PhysicalPanel.tsx:85`.

## Cleanup

Grants created this round (R7J1 Local, R7J1 Cloud) are revoked and both tokens return 401. Two stale judge1 grants from earlier rounds (R6J1 Local, R5J1 Cloud) were also revoked. Documents uploaded this round (prefix `r7j1-`) remain in the judge1 account; no other account's data was touched.
