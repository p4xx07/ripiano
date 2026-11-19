# Judge 2 — quality round 9

- **Candidate:** `1a365f35c12509f79da9cd9c459b426dca1f4ec4` (running images; repository HEAD `c2156fc` adds evidence only). File:line references checked with `git show HEAD:<path>`.
- **Date:** 2026-11-19
- **Stack:** my own Compose project `ripiano-j2`, http://localhost:18102, started empty. First-time setup done by me in Italian on emulated mobile.
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Chrome channel (stable Google Chrome). The Chrome binary's `--version` call was refused by the sandbox, so the exact Chrome build is not recorded. Desktop 1440x900; mobile 390x844 with `isMobile`, `hasTouch` and DPR 2. Locale `it-IT` throughout, so the interface followed the device language (Italian).
- **Screen reader stand-in:** no screen reader is installed. I used Playwright `locator.ariaSnapshot()` and Chrome's own accessibility tree (CDP `Accessibility.getFullAXTree`). I logged the focused element after every action and read live regions (`role=status|alert`, `aria-live`).
- **Emphasis (as assigned):** mobile, keyboard-only use, assistive technology, the Italian interface, session expiry during an edit, the unsaved-changes dialog, Inbox retries, offline and interrupted uploads, and recovery after service restarts.

## Commands and scripts

All scripts are in `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j2r9/`. They run with `node sNN-*.mjs`, and a `node_modules` symlink points to `apps/web/node_modules`, so nothing was written into the repository. The owner and family passwords and the agent tokens are kept only in that folder.

| Script | What it does |
|---|---|
| `s1-setup.mjs` | Italian first-time setup on mobile, keyboard only: short password, wrong setup key, then success |
| `s2/s3-*.mjs` | Desktop sign-in, `?` shortcut dialog, `n` opens Add, Add dialog semantics |
| `s4-upload.mjs` | Keyboard-only upload through the Add dialog's file chooser; records live regions over time |
| `s5/s6/s7-*.mjs` | Opens a document with `j` and Enter; files sender, type and tag inline by keyboard; probes the unsaved-changes dialog |
| `s8-mobile-upload.mjs` | Mobile upload of a `.msg` file and a gallery image (`judge.png`) |
| `s10/s11-*.mjs` | Filing-suggestion API per document; on mobile, reject a tag suggestion and accept a sender suggestion, checking focus and announcements |
| `s12-expiry.mjs` | Session deleted on the server mid-edit (`manage.py shell`: `Session.objects.all().delete()`), then Save; a second session changes the title; sign in again: draft restored with a conflict |
| `s13-offline.mjs` | Mobile upload while offline (`context.setOffline`) and back online; upload while the `api` service is stopped, then started |
| `s14/s15-*.mjs` | Kill `worker` mid-OCR, start it again; Inbox: OCR retry of a broken file, then "Keep both" for an exact copy |
| `s16-italian.mjs` | Visits all 15 screens and looks for English strings and console errors |
| `s17-focus-conflict.mjs` | Focus after a desktop upload; two tabs save the same document |
| `s18-unsaved.mjs` | Mobile unsaved-changes dialog: Close, browser Back, reload (beforeunload), Discard |
| `s19-search.mjs` | Italian search on mobile: OCR words, stemming, sender, tag; filter panel |
| `s20/s21/s22-*.mjs` | Nested locations, sticker creation, camera with no camera available, typed lookup, move the copy, print the label |
| `s23–s27-*.mjs` | Two agents with different scopes, MCP `tools/list` and calls, audit log, keyboard revocation on mobile |
| `s28-restart.mjs` | `stop db` during a search, then start; `stop broker` during an upload, then start |
| `s29-backup.mjs` | "Esegui backup ora" by keyboard; I then checked all manifest SHA-256 values against the snapshot (50/50 files and `database.dump` OK) |
| `s30-targets.mjs` | Mobile touch-target (<24 px) and horizontal-overflow audit; drawer and dialog Esc/focus |
| `s31–s33-*.mjs` | Add a family account; Chrome AX-name scan of every screen |
| `s34-draft-users.mjs` | A kept draft when a different person signs in on the same device |
| `s35-cleanup.mjs` | Revoke the remaining agent; confirm both tokens return 401 |

I also ran:

- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` → `372 passed, 15 skipped in 58.38s`
- Compose commands on my own project only: `exec api …manage.py shell`, `kill worker`, `start worker`, `stop/start api`, `stop/start db`, `stop/start broker`, `restart mcp`, `logs mcp`.

## Fixture IDs used

`three-pages.pdf`, `office-letter.docx`, `email-notice.eml`, `outlook-notice.msg`, `judge.png` (gallery, and again as an exact copy), `office-open.odt`, `office-sheet.xlsx`, `office-slides.pptx`, `office-legacy.doc`, `tag-barcode-desktop.pdf`, `tag-barcode-mobile.pdf` (offline upload), `asn-batch-desktop.pdf`, `asn-batch-mobile.pdf` (upload while the api was down), `barcode-batch-mobile.pdf` (worker killed), `barcode-batch-desktop.pdf` (broker down).

One file was derived, not taken directly from the corpus: `three-pages-truncated.pdf`, the first 3000 bytes of `three-pages.pdf`, used to force an OCR failure.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable |
|---|---:|---:|---|---|
| Capture and filing friction | 25% | **9.0** | PDF, DOCX/ODT/XLSX/PPTX/DOC, EML/MSG, gallery PNG and barcode/ASN splits all became `ready` with nothing to review; there is no mandatory to-do screen. Sender, type and tag can be created inline by keyboard, and focus lands on the new value (screenshot 06). An uncertain suggestion (`office-legacy`, similarity 0.33) shows "Simile a “office-letter” · in comune: …" and can be rejected or accepted in the same dialog. Both outcomes are announced, and a rejection keeps focus in the list (11, 12). Offline uploads are queued and sent when the connection returns (15, 16). Friction: on an empty tag list, the prominent "Crea la tua prima etichetta" leaves the document (and opens the unsaved-changes dialog), while the inline "Crea un'etichetta" sits next to it. | Real camera capture, Telegram, watched folder on the NAS, native Android scanner (out of scope by owner decision). The camera button exists; emulation has no camera. |
| Retrieval and physical filing | 20% | **9.1** | Search finds OCR words (`girasole`), Italian stemming ("polizze assicurative" → "Polizza"), sender (`mittente:"Comune di Lampone"`) and tag; the result count is announced ("2 documenti trovati"). Nested locations, sticker creation, typed lookup (case-insensitive), moving the copy, and printing the HTML label all work (27–30). With no camera, the scanner shows a clear alert and a "Digita il codice" fallback, and Esc returns focus to the opener (28). Friction: a successful sticker lookup is not announced (L2 below). | Scanning a real QR code with a camera, physical printing. |
| UX and accessibility | 20% | **8.7** | The Italian interface is complete: no English strings on any of the 15 screens and no console errors. There is a skip link; every view change moves focus to its h1. Dialogs use `aria-modal`, trap Tab, and return focus to their opener on Esc. The unsaved-changes dialog is an `alertdialog`, opens with focus on "Continua a modificare", traps Tab, and also catches browser Back and reload (24). The drawer handles Esc and focus. No touch targets under 24 px and no horizontal overflow on 6 mobile screens. Deductions: M2 (backup start drops focus to `<body>` with nothing announced), M3 (an Inbox retry gives no outcome), L1 (four fields with run-together AX names), L2, L3, L4. | Real VoiceOver, TalkBack and NVDA; installed PWAs (out of scope). |
| Reliability and recovery | 20% | **8.5** | Killing the worker mid-OCR: all 4 jobs finished after the restart. Stopping the api during a mobile upload: the file was retried and stored once (no duplicate). Stopping the broker during an upload: processing resumed about 40 s after the broker came back. Stopping the db: the search shows an error with Retry and works again afterwards. Session ended mid-edit: the draft is kept, restored after sign-in with focus on the restored-draft notice, and a field changed elsewhere is reported as a conflict, with the newer value kept (13, 14). A different person signing in never sees the draft. My manual backup verified 50/50 file checksums and the database dump. Deductions: H1 (MCP is dead after a db restart until it is restarted by hand), M1 (silent lost update between two tabs), M3. | Full `down -v` restore on my stack (I relied on the separate drill, `restore-drill-round9.md`, which is credible and on this commit); NAS restore (out of scope). |
| Privacy and agent control | 15% | **9.2** | The "Cloud titoli" agent (titles only, Tasse documents only) sees only `search_documents`. It cannot find documents by OCR words ("contribuente" → empty), cannot see `office-open` (outside its scope), and gets "Tool is not permitted" for text and tag tools. The "Locale completo" agent sees 4 tools and reads text. The audit log in Italian lists refused attempts with the document title. Keyboard revocation needs an inline confirmation, then announces "Accesso per “Cloud titoli” revocato." and the token returns 401. Creating an agent requires the owner's password. Deduction: L5 (the form keeps the previous agent's permissions and scope). | Real cloud MCP clients (out of scope). |

**Weighted mean:** 0.25·9.0 + 0.20·9.1 + 0.20·8.7 + 0.20·8.5 + 0.15·9.2 = 2.25 + 1.82 + 1.74 + 1.70 + 1.38 = **8.89**

## Hard gates

| Gate | Status |
|---|---|
| 1. Parity: every capability has a scenario or an accepted deviation | Not re-audited in full. Every parity area I exercised (capture formats, OCR/search, filing, physical copies, Inbox exceptions, agents, backups, people) worked. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Install, upload, OCR, search and backup **demonstrated** on my empty stack; backup checksums verified (50/50 files plus the database). The clean restore is taken from `.omo/evidence/restore-drill-round9.md` (same commit, credible: checksums, stickers, revoked grants). I did not run `down -v` myself. |
| 3. Installed iOS/Android PWA and native Android on real devices | **Out of scope by owner decision (D7).** Browser emulation only. |
| 4. Security: isolation, token revocation, CSRF, upload validation, no default transfer to providers | Partly demonstrated: agent scope and tool isolation, revocation (401), password for agent creation, family account isolation for drafts. CSRF and upload validation not probed. |
| 5. Tests, builds, journeys, migrations | `round9-verification.md` is credible (commands and result lines; the one e2e failure is explained as a shared-account flake and re-run green). I re-ran the API suite: `372 passed, 15 skipped`. I did not run the build or the e2e suite (brief). |
| Out of scope by owner decision | Real phones (installed PWAs, native Android capture), real Telegram/Google/Microsoft/Dropbox accounts, and DS923+ checks (performance, ACLs, a restore on the NAS). |

## Findings

### Severe

None.

### High

**H1 — The MCP service stays broken after the database restarts: every agent request returns HTTP 500 until `mcp` is restarted by hand.**

- **Reproduce:**
  1. Create an agent and confirm `POST /mcp tools/list` with its token returns 200 (or 401 once revoked).
  2. Run `docker compose -p ripiano-j2 … stop db`, then `start db`.
  3. Send any MCP request: it returns 500. `logs mcp` shows `django.db.utils.OperationalError: the connection is closed`.
  4. Run `restart mcp`: requests answer correctly again (401 for the revoked tokens).
- **Contrast:** after the same database restart, the `api`, `worker` and `maintenance_worker` recovered without help. Nothing in the UI shows that agents have stopped working.
- **Cause:** `services/api/archive/mcp_server.py:108,321,332`. ORM calls run in `sync_to_async` threads inside a plain ASGI app (`services/api/mcp_asgi.py`). Django's request signals never fire there, and nothing calls `close_old_connections()`, so the dead connection is reused forever.
- **Impact:** a database container update or restart on the NAS (a common case) quietly breaks every agent until someone restarts `mcp`.

### Medium

**M1 — Two tabs (or two family members with edit access) editing the same document: the last save silently overwrites the first.**

- **Reproduce:**
  1. Open `office-sheet` in tabs A and B.
  2. In A, set the title to "Foglio tab A" and save.
  3. In B, set the title to "Foglio tab B" and save.
- **Result:** B shows "“Foglio tab B” salvato.", with no warning that A's change was replaced. The server now holds "Foglio tab B".
- **Cause:** the document PATCH (`services/api/archive/views.py:974-985`) has no version or If-Match check. The field-level conflict detection only runs on the kept-draft path (`apps/web/src/DocumentPanel.tsx:69-83`).

**M2 — "Esegui backup ora" drops keyboard and screen-reader users to `<body>` and announces nothing.**

- **Reproduce:**
  1. Open Backup.
  2. Focus "Esegui backup ora" and press Enter.
- **Result:** the button becomes `disabled` while the request runs, so focus falls to `<body>`. No live region announces that the backup started or finished; the new snapshot just appears in the list as "manuale completato" (36).
- **Cause:** `apps/web/src/App.tsx:395-407` (`start()`) and the `disabled={busy}` button at about `App.tsx:452-457`.

**M3 — An Inbox OCR retry gives no outcome.**

- **Reproduce:**
  1. Upload a damaged PDF (`three-pages-truncated.pdf`), which ends as `failed` in Inbox.
  2. Press "Riprova l'OCR".
- **Result:**
  - The status says "OCR riavviato. L'originale resta al sicuro nell'Archivio.", the card disappears, and focus moves to the next card.
  - When OCR fails again a few seconds later, nothing is announced and the card does not come back. It reappears ("non è riuscito di nuovo…") only after another Inbox action or Aggiorna.
  - A non-technical user, or a screen-reader user, will believe the problem was fixed.
- **Cause:** `apps/web/src/InboxPanel.tsx:168-185`. The Inbox has no polling for documents being reprocessed, unlike the Library's "in elaborazione" counter.

### Low

**L1 — Accessible names run together in Chrome's accessibility tree on People and Security**, for example "NomeFacoltativo", "PasswordAlmeno 12 caratteri · …", "La tua passwordServe per…", "Nuova passwordAlmeno 12 caratteri". The cause is `apps/web/src/ui.tsx:59`: `Field` renders `{label}<small>{hint}</small>` with no separator, and where the `<small>` is inline the name merges. The hint also belongs in `aria-describedby`, not in the name. Other screens render a space and are fine.

**L2 — A successful sticker lookup is not announced, and focus stays in the code field.** A failed lookup is announced as "Adesivo non trovato". Cause: `apps/web/src/PhysicalPanel.tsx:310-331`; the result block has no live region and no focus move.

**L3 — Entering a wrong setup key during first-time setup marks the wrong fields.** Username and Password get `aria-invalid`, while the Setup key field does not (the `credentialsInvalid` logic in `App.tsx`, around lines 228 and 297-308). The setup intro also says the key "si trova nelle impostazioni di Portainer", which is wrong for the README's `.env` install.

**L4 — Italian copy.** The Inbox eyebrow "SOLO QUANDO SERVI TU" is ungrammatical; it should be something like "Solo quando serve" (`apps/web/src/locales/InboxPanel.ts:45`). The DB-down error "Il server ha inviato una risposta inattesa." is generic where "temporarily unavailable" would be clearer.

**L5 — The agent-creation form keeps the previous agent's permissions and scope.** After creating "Locale completo" with "Leggere il testo OCR", that box and the scope stay selected for the next agent. A family member creating a second, cloud agent can grant text access without noticing.

**L6 — Kept-draft edge cases.**
- If a different person signs in on the device, the first person's kept draft is silently discarded, although the sign-in notice says the changes stay "per un giorno". This is privacy-safe, but the wording should say so.
- When a draft field conflicts, the user's own typed value (my title "Polizza casa girasole") is dropped and never shown, so it cannot be copied back.

**L7 — On an empty tag list the document dialog offers two tag buttons**, "Crea la tua prima etichetta" (leaves the dialog) and "Crea un'etichetta" (inline). The first is the more prominent one and interrupts filing.

## What worked well (confirmed, not assumed)

- First-time setup in Italian:
  - Keyboard-only; native validation for a short password.
  - An alert for a wrong key.
  - After setup, focus lands on the Library h1.
- Focus management throughout:
  - Every view change focuses its h1, and the `g`+letter shortcuts work.
  - `j`/Enter opens a document.
  - Saving returns focus to the document's title button and announces "“…” salvato.".
  - Inline creation of sender, type or tag moves focus to the new value.
- Unsaved changes are caught for Close, Esc, browser Back and reload; "Scarta" returns focus to the document.
- Recovery:
  - Offline queue, an api restart during upload (no duplicate), a worker killed mid-OCR, and a broker outage all recovered without any action from me.
  - The kept draft and its per-field conflict notice after a session ended mid-edit work as designed.
- Agent isolation is tight. The Italian audit log is readable and records refused attempts.

## Most serious finding

**H1:** after a database restart, the MCP service answers every request with 500 until someone restarts it by hand (`archive/mcp_server.py` never discards dead connections).

## Cleanup

Both agent grants I created are revoked (both tokens return 401). My stack is running (`mcp` was restarted to recover from H1). The family account `marta` remains on my stack. Screenshots are in `qa-artifacts/20261119-r9-judge-2/` (40 files; agent tokens masked).
