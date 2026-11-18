# Judge 2 report — Ripiano quality gate

- **Candidate SHA:** 901d491828b1eb9df5d674a23e6115c0dd7bc3be (branch `codex/initial-implementation`)
- **Date:** 2026-11-18 (runs between about 08:15 and 09:40 Europe/Rome)
- **Judge:** judge2 (account `judge2`). Emphasis: a mobile-first, keyboard and screen-reader user who works in Italian.
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (`channel: "chrome"`, headless)
- **Stack:** http://localhost:18080 (PWA, `/api`, `/mcp`). I did not restart or rebuild anything.
- **Contexts:** mobile = 390x844, `isMobile`, `hasTouch`, DPR 3, iOS Safari user agent, `it-IT`, Europe/Rome. I also checked 375x667 and 320x640. Desktop = 1440x900 and 1280x720, `it-IT`. The interface language was set to **Italiano** for every run.
- **Note on the working tree:** `git status` was clean at the start. During my run, someone else made uncommitted changes to many files, including `App.tsx`, `DocumentPanel.tsx`, `api.ts`, `messages_it.py`, a new `uploadQueue.ts`, and a new `search_syntax.py`. I did not make those changes. I scored the **running stack**. Every file:line below was checked against `git show 901d491:<path>`, not against the dirty tree.

## Commands and scripts

All scripts live in my scratch folder. They import `@playwright/test` through a symlink to `apps/web/node_modules`, so I added no files to the repository. A copy of every script is in `qa-artifacts/20261118-judge-2/judge2-scripts.tgz`. The scripts read the password from `judges.env` at runtime and do not contain it.

| Script | Purpose |
| --- | --- |
| `node tour.mjs mobile` / `node tour.mjs desktop` | Italian sign-in, then every screen. For each screen: accessibility audit (names, labels, duplicate ids, alt text, targets under 24 px, horizontal overflow), an English-leak scan, and an ARIA snapshot |
| `node probe2.mjs` | Add dialog accessibility tree and initial focus |
| `node capture.mjs` | Upload 7 fixtures through the Italian mobile Add dialog, then wait for processing |
| `node probe3.mjs` | OCR/text searches and the document dialog tree |
| `node probe4.mjs`, `node filing.mjs` | Create a sender, type, date, and tag in the document dialog; create a rule tag; example suggestions; re-upload to test rule filing |
| `node retrieve.mjs` | Remove a rule tag as a correction; `sender:`, `tag:`, `date:`, and OCR searches; create nested locations; create a sticker |
| `node physical.mjs` | Move the paper copy into a nested box; print the label page; open the QR target URL (`/?sticker=`); manual sticker lookup |
| `node keyboard.mjs desktop`, `node probe5.mjs` | Tab order, skip link, `? / n j k Enter g+letter`, dialog focus trap, focus return, focus visibility, contrast samples, 320 px reflow |
| `node probe6-9.mjs` | Reachability of the sidebar or menu at 320x640, 375x667, 390x844, 1280x720, and 1440x900 |
| `node agents.mjs` | Two MCP grants in the Italian UI; MCP `initialize`, `tools/list`, and `tools/call` over HTTP with each bearer token; revoke one; check the audit log |
| `node reliab.mjs` | Offline upload, upload aborted by connection reset, PDF with fake content, unsupported extension, mixed batch, Inbox |
| `node backup.mjs`, `node backup2.mjs` | Manual backup from Backup → "Esegui backup ora", then the completed snapshot in the list |

`curl` was blocked in this environment, so every HTTP and MCP call went through Playwright's `page.request` with my own session or the agent bearer tokens.

## Fixture IDs used

From `apps/web/e2e/fixtures/`:

| Fixture | How I used it |
| --- | --- |
| `judge.png` | Uploaded through the "Scatta una foto" (camera) input and the "Scegli dalle foto" (gallery) input; also used for the offline test |
| `three-pages.pdf` | Upload, and the aborted upload |
| `office-letter.docx` | Upload |
| `email-notice.eml` | Uploaded twice: once plain, once to test rule filing and duplicate detection |
| `outlook-notice.msg` | Upload |
| `office-sheet.xlsx` | Upload |
| `office-legacy.doc` | Sent as `.pdf` (fake content) and as `.exe` inside a mixed batch |
| `office-slides.pptx` | Sent as `.zip` (unsupported) |
| `office-open.odt` | The valid half of the mixed batch |

Not used: the barcode and ASN PDFs (`asn-batch-*`, `barcode-batch-*`, `tag-barcode-*`).

My test objects all carry the suffix `mwluqc5v`, so they are easy to find and remove.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable or not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **7.0** | **What worked:** 7 uploads through the Italian mobile dialog (camera input, gallery input, file input; PNG, PDF, DOCX, EML, MSG, XLSX). All showed "Pronto" within about 20 s. No mandatory to-do screen; documents go straight to the Library. A rule tag ("lampone") was applied on intake and shown with a "Regola" badge. Unchecking it and saving removed it (a correction). On an identical copy, example suggestions appeared, and tapping "Imposta mittente" saved the sender at once with an Italian live-region confirmation. The exact duplicate was flagged in the Library and Inbox. **Problems:** the suggestion explanations are in English ("Like … · shared: …"). Focus is lost after "Aggiungi un mittente". "Crea la tua prima etichetta" leaves the document dialog for the Tags screen. The most common upload rejection message is in English. An offline upload shows "Failed to fetch" and is not queued. | Real camera capture; installed PWA; Android native scanner; Telegram (needs a real bot); watched or consume folder (a Docker named volume owned by the first archive owner, which I could not reach without Docker); OCR quality on real phone photos |
| Retrieval and physical filing | 20% | **7.5** | **What worked:** OCR phrase `9473` found both images, with an Italian snippet "Testo del documento: RIPIANO JUDGE 9473". `lampone`, `condominio`, and `Office conversion` each found the right document. `sender:"…"`, `tag:"…"`, and `date:2026-04-15` each returned exactly the expected documents. Nested locations (Scaffale › Scatola) were created. A sticker was created (R-ESDXMGHB), moved into the box, printed as a label page with a QR code, and found again through `sticker:`. The QR target URL `/?sticker=` opened the paper archive with the correct document and path. **Problems:** the move `<select>` on the copy card has no accessible name. There is no in-app QR scanner, although the Italian text says "Scansiona un codice QR". Manual lookup rejects a code typed without its dash. Field keywords exist only in English (`mittente:` returns nothing). Search results are not announced to screen readers. The original file name is not searchable. | Scanning a printed sticker with a real phone camera; physical printing |
| UX and accessibility | 20% | **5.5** | **What worked:** skip link; focus trap in dialogs (80 Tabs, none escaped); Escape closes dialogs; focus returns to the opener when the dialog was opened from a focused button; Italian shortcut list (`?`); `/`, `n`, and `g`+letter work; sampled text contrast is ≥ 5.3:1; most screens are fully Italian. **Problems:** the sidebar or menu cannot scroll, so language, appearance, and sign-out cannot be reached by pointer at any tested size, including 1440x900. The sign-out control is announced only as "J judge2 Amministratore". There is no `<nav>` landmark and no `aria-current` on the current screen. Every document dialog has the same name ("Tienilo al suo posto."). The hidden file inputs appear as three English "Choose File" buttons. Many touch targets are 13–18 px tall. The date input has no focus ring. The page `<title>` is English and never changes. Screen changes do not move focus. `j`/`k` do not move focus. At 320 px the Library overflows to 337 px. An Italian device still starts in English, and the option there is labelled "Italiano (preview)". | Real VoiceOver/TalkBack; installed iOS/Android PWA; Android client; 200% text zoom |
| Reliability and recovery | 20% | **6.0** | **What worked:** an offline upload and an upload aborted by connection reset each produced a visible per-file failure report and a "Riprova" button. A legacy `.doc` sent as `.pdf` was rejected by content checks. An unsupported `.zip` was rejected. A mixed batch accepted the `.odt` and rejected the `.exe`. A manual backup completed and appears as "manuale · completato". **Problems:** the failure text is the raw browser string "Failed to fetch". The PWA keeps no queue, so the user must pick the file again. A message in the English rejection text was untranslated (see H2). The Backup list shows a raw `[Errno 13] Permission denied: '/backup/staging'` from an earlier run, and the origin label "schedule" is untranslated. | Interrupting or restarting the worker and services (not allowed); restoring to an empty stack; retrying a failed OCR (I could not produce a processing failure from the corpus, because uploads with bad content were rejected up front) |
| Privacy and agent control | 15% | **8.5** | **Grant A** (cloud): search scope only. `tools/list` returned `[search_documents]`. `get_document_text` → "Tool is not permitted"; title-only search (`9473` returned nothing, `lampone` matched by title). **Grant B** (local): search and OCR text, limited to the tag "Bollette J2". `tools/list` returned `[search_documents, get_document_text, semantic_search]`. It read the text of a tagged document, and a document outside the tag gave "Document not found within this grant". **Revoking A:** its next call returned 401 `invalid_token`, re-initialising also returned 401, and B still got 200. The activity log recorded ok, denied, and error per agent. **Problems:** the log shows raw English tool names and outcomes. Revoke happens on one tap with no confirmation. `semantic_search` is listed while semantic search is off. | A real cloud MCP client; network-level proof that no content leaves the NAS |

**Weighted mean:** 0.25×7.0 + 0.20×7.5 + 0.20×5.5 + 0.20×6.0 + 0.15×8.5 = **6.83 / 10**

## Hard gates

| Gate | Status |
| --- | --- |
| 1. Every FEATURE_PARITY row has a scenario or an accepted deviation | **Partially demonstrated.** I exercised these rows: upload channels (web only), OCR and search, tags, senders, types and dates, matching and suggestions, duplicate flag, physical copies and labels, MCP grants, backup, localization, and keyboard. I did not check the other rows one by one. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **Partially demonstrated.** Upload, OCR, search, and a manual backup work. I did not demonstrate a fresh install or a restore. |
| 3. Installed iOS/Android PWA and native Android on real devices | **Not demonstrated.** Needs the owner's hardware. Emulation only. |
| 4. Security review (isolation, revocation, CSRF, upload validation, external inputs, no default content transfer) | **Partially demonstrated.** Demonstrated: agent scope and tag-filter isolation, immediate token revocation, content-checked upload validation, and no model provider called by default (semantic search is off). Not covered: CSRF, account isolation between people, and external inputs (Telegram and cloud need real accounts). |
| 5. Unit/API tests, production builds, browser journeys, migrations, deployment checks on the candidate | **Not demonstrated by me.** I did not run the suites. Published digest-pinned images and DS923+ deployment need the owner. |

## Findings

### Severe

None that I could prove would cause data loss or a security breach.

### High

**H1 — The sidebar or mobile menu cannot scroll, so the language selector, appearance, and sign-out cannot be reached by pointer or touch. On small phones, Agenti, Persone, and Backup are also out of reach.**
- **Cause:** `apps/web/src/style.css:177-188`. `.sidebar` has `height: 100vh`, `position: sticky` (and `position: fixed` on mobile at `style.css:1212-1217`), and no `overflow-y: auto`. Its content is 1157 px tall.
- **Measured with `elementFromPoint`:**

  | Viewport | Out of reach |
  | --- | --- |
  | 1440x900 | Lingua (y=885), sign-out (y=1100) |
  | 1280x720 | Backup, Aspetto, Lingua, sign-out |
  | 390x844 | Lingua, sign-out |
  | 375x667 | Agenti, Persone, Backup, Aspetto, Lingua, sign-out (scroll gestures do nothing) |

  Keyboard Tab still reaches these controls, but they stay off-screen, which also fails "focus not obscured".
- **Repro:** sign in on a 375x667 touch device and tap ☰. The list ends at "Cestino" and nothing below it can be scrolled into view.
- **Evidence:** `mobile320-menu.png`, `desktop1280x720-sidebar.png`, and `desktop-agents-created.png` (full-page: the sidebar background ends at 900 px, and the note and account text below it become invisible).

**H2 — The most common upload rejection is shown in English in the Italian interface.**
- **Message:** "Use PDF, JPEG, PNG, an email (.eml or .msg), or an Office/OpenDocument/RTF file".
- **Cause:** `services/api/archive/storage.py:14` (`UNSUPPORTED`), raised at lines 59 and 65. It has no entry in `messages_it.py`, and `test_api_language.py` does not catch module-level constants. This contradicts the README claim that "every API error message is translated".
- **Repro:** in Italian, Aggiungi → Sfoglia i file → choose any `.zip` or `.exe` (I used `office-slides.pptx` renamed to `.zip`). The banner reads "1 file su 1 non sono stati aggiunti. …: Use PDF, JPEG, …".
- **Evidence:** `mobile-upload-errors.png`.

### Medium

1. **Hard-coded English in suggestion explanations.** The text reads "Like “…” · shared: …", and "NN% likely, learned from your filing".
   - Cause: `apps/web/src/api.ts:175-179` (`suggestionBasis`).
   - Repro: file document A with a sender, type, and tag. Open an identical document B in Italian. Each suggestion card reads "Like “A” · shared: …".
   - Evidence: `mobile-suggestions.png`.
2. **The sign-out control's accessible name gives no hint that it signs out.** It is announced as "J judge2 Amministratore". "Esci" is only a `title`, which is overridden by the text content. One tap signs out with no confirmation.
   - Cause: `App.tsx:1197`.
3. **Focus is lost when adding a sender or type inline.** After "Aggiungi un mittente", focus falls to `<body>`, and `#root` is inert under the dialog, so keyboard and screen-reader focus is stranded. The new field has no `autoFocus`.
   - Cause: `DocumentPanel.tsx:502-506` (same pattern for the type field).
   - Repro: open a document, press "Aggiungi un mittente", then check `document.activeElement`.
4. **Every document dialog has the same accessible name and heading** ("Tienilo al suo posto."), not the document title, so a screen-reader user cannot tell which document is open.
   - Evidence: `doc-dialog.yml` snapshot, `mobile-doc-dialog.png`.
5. **The paper-copy "move" `<select>` has no label.**
   - Cause: `DocumentPanel.tsx:684-686`.
   - Repro: create a sticker, then inspect the copy card. The combobox has no name. The project's own `e2e/accessibility.spec.ts` does not open a document that has a copy, so it misses this.
6. **The hidden file inputs are exposed to assistive technology as three unnamed English "Choose File" buttons** at the start of the Add dialog. They have `tabindex=-1` but no `aria-hidden`, so they are still in the accessibility tree.
   - Cause: `App.tsx:1680-1705`.
   - Evidence: `probe2` output and `mobile-add-dialog.png`.
7. **No navigation landmark or current-page state.**
   - The sidebar is an `<aside>` with buttons, with no `<nav>` and no `aria-current` (`App.tsx:1088`).
   - The page `<title>` is the fixed English "Ripiano — your documents, in place" (`apps/web/index.html:20`).
   - Screen changes made with `g`+letter or the menu leave focus on `<body>` with no announcement.
8. **Touch targets below 24 px on mobile**, which fails WCAG 2.5.8 and is well below the 44 pt iOS guideline:
   - "Ricerca avanzata" summary: 13 px
   - "Seleziona documenti": 13 px
   - Document title buttons: 16 px
   - "Vedi contenuto": 13 px
   - Clear-search ×: 28x18
   - Every `.text-action` and `<summary>` in the document dialog: 15–18 px
   - The search `<input>` itself: 17 px, inside a larger wrapper
9. **Offline or interrupted uploads in the PWA are lost** and show the raw browser error. The banner reads "…: Failed to fetch" plus "Failed to fetch Riprova". The selected file is not queued, so the user must pick it again. This is the main mobile-capture failure mode.
   - Repro: `context.setOffline(true)` → Aggiungi → Scegli dalle foto.
   - Evidence: `mobile-offline-upload.png`.
10. **The agent activity log is untranslated.** It shows "get document text", "search documents", "ok", "denied", "error".
    - Cause: `AgentPanel.tsx:248-250`.
11. **Italian is labelled as a preview, and Italian devices start in English.** The sign-in language list shows "Italiano (preview)" (`locales/App.ts:12`), although Italian is claimed complete. With an `it-IT` browser the interface still opens in English (`i18n.ts:20`). The owner may have decided this, but it adds friction for an Italian-first user.

### Low

- The Library overflows horizontally at a 320 px viewport (scrollWidth 337), which fails reflow.
- The document-date `<input type=date>` has no visible focus ring (`desktop-focus-missing.png`).
- `j`/`k` move a highlight (`aria-current`) but not focus, so a screen reader announces nothing. Closing a dialog opened with `j`+Enter returns focus to `<body>`.
- The Backup list shows the raw origin "schedule completato" and an untranslated exception "[Errno 13] Permission denied: '/backup/staging'". Snapshot headings are raw IDs such as "20261118T083121…Z-054cc743".
- Italian wording:
  - "SOLO QUANDO SERVI TU" (Inbox eyebrow) literally means "only when *you* serve"; "Solo quando c'è bisogno di te" says what is meant.
  - The shortcuts list says "Vai a Archivio" (should be "Vai all'Archivio"), uses "Cose da fare" while the menu says "Da fare", uses "Archivio" while the menu says "Tutti i documenti", and shows the key as "Enter" instead of "Invio".
  - Mixed-batch grammar: "1 file su 2 non sono stati aggiunti" (should be "non è stato aggiunto").
  - "Bentornato." is masculine only.
- Search field keywords are English-only (`sender:`, `tag:`, `date:`), and `mittente:` returns nothing silently.
- Manual sticker lookup rejects a code typed without its dash (`resdxmghb`). Only upper-casing is normalised (`PhysicalPanel.tsx:62`).
- No search-result count or "nessun risultato" live announcement.
- Saving the document dialog closes it with no confirmation message.
- Moving a paper copy gives no status message.
- Revoking an agent happens on one tap with no confirmation.
- Note timestamps use `toLocaleString()` without the interface locale (`DocumentPanel.tsx:600`).
- The label page is served with `lang="en"`.
- `semantic_search` is listed for a text-scoped grant while semantic search is off, although `AGENT_ACCESS.md` says "only while the optional semantic search is on".
- The pgvector warning box wraps its inline `<code>` badly on desktop (`desktop-agents-created.png`).

## Most serious finding

**H1: the sidebar and mobile menu cannot scroll.**
- At every tested size, including the 1440x900 desktop, the language selector and sign-out cannot be reached by pointer or touch.
- On a 375x667 phone, Agenti, Persone, and Backup are also out of reach.
- A mobile Italian user cannot change language or sign out from inside the app.
- The fix is probably a single CSS change: `overflow-y: auto` on `.sidebar`, in `style.css:177`.

## Artifacts

Folder: `qa-artifacts/20261118-judge-2/` (31 files: screenshots, the label PDF, and `judge2-scripts.tgz`). The agent token is masked in `desktop-agents-created.png`, and no password appears in any artifact.
