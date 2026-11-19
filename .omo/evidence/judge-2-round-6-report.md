# Judge 2 — round 6 report

- **Candidate SHA:** 635be8edb4768499d627eae922c1ab5a463cfeb3 (`codex/initial-implementation`), running stack at http://localhost:18080
- **Date:** 2026-11-19
- **Reviewer emphasis:** mobile-first, keyboard and screen-reader user who works in Italian (all five dimensions scored)
- **Account:** `judge2` (admin). The account holds data from earlier sessions; only documents, stickers, and agent grants created in this run were changed.
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (`channel: "chrome"`). Desktop 1440x900; mobile emulation 390x844 with `isMobile`, `hasTouch`, DPR 2, and an iOS Safari user agent; narrow 320 px reflow check. Locale `it-IT`, time zone Europe/Rome, app language "Lingua del dispositivo" (resolved to Italian).
- **Artifacts:** `qa-artifacts/20261118-r6-judge-2/` (39 PNGs; the agent token field is masked in 25-*.png).

## Commands and scripts

Scripts are kept outside the repository, in the session scratch folder `…/scratchpad/j2/`. Each one imports `@playwright/test` by absolute path from `apps/web/node_modules` and is run as `node <script>.mjs`:

| Script | What it does |
| --- | --- |
| common.mjs | Context options (desktop/mobile, it-IT) and login. The password is read from judges.env at run time and never printed. |
| s1 | Italian login and home screens on mobile and desktop, plus ARIA snapshots |
| s2, s3 | Mobile Add sheet. Gallery upload of `judge.png`; file upload of `three-pages.pdf`, `email-notice.eml`, `office-letter.docx`, `outlook-notice.msg`; live-region polling |
| s4 | Desktop keyboard: Tab order, `?` help, `/` search; searches for an OCR phrase, sender, date, tag, and Italian accent folding |
| s5, s6 | Mobile document dialog: ARIA, `aria-modal`, Esc returns focus |
| s7, s8, s9 | Mobile correction in one screen (title, date, sender, tag); sticker creation; sticker search; copy move; label print; QR deep link `/?sticker=`; manual sticker lookup; unknown sticker |
| s10 | Translation sweep across all 15 nav screens in Italian (heuristic for English words; `<details>` expanded) |
| s11–s14 + mcp.mjs | Two MCP grants created in the UI. Streamable-HTTP `initialize`, `tools/list`, `tools/call` (Node `fetch`); audit list; keyboard revocation; 401 check |
| s15 | Offline upload queue (`context.setOffline`) with `office-sheet.xlsx` and a non-PDF named `.pdf` (scratch file `finto-documento.pdf`, not a fixture); reconnect |
| s16 | Desktop keyboard: `n` dialog focus trap, Esc, `/`, Esc to first result, Enter to open, dialog trap, move a copy by keyboard |
| s17 | Automated checks on mobile/320 px: contrast, target size, duplicate accessible names, horizontal overflow |
| s18 | Looks for learned suggestions on the six newest documents |
| s19 | OCR retry, note add, Inbox |
| s20 | Isolated reproduction of the copy-move defect, with move history |
| s21 | Manifest/service worker/meta check; Italian login error; empty-form validation |

**Fixture IDs used:** `judge.png`, `three-pages.pdf`, `email-notice.eml`, `office-letter.docx`, `outlook-notice.msg`, `office-sheet.xlsx`. The corpus was already present in the account from earlier sessions, so each re-upload was correctly flagged as an identical copy.

## Scores

| Dimension | Weight | Score | Evidence (this run) | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **8.6** | **Mobile Add sheet (03):** 3 clear choices, fully in Italian, initial focus on Close, focus trapped. **Uploads:** gallery plus 4 files reached "Pronto" within about 15 s (04–06). Nothing went through a mandatory TODO screen; duplicates appear only in the exception Inbox (33). **Auto-filing:** a matching rule tagged `email-notice.eml` automatically. **Correction in one screen:** title, date, sender, and tag were fixed in the document dialog with one Save, announced as "“…” salvato." (11). **Offline:** files queued while offline with a clear Italian status, then sent on reconnect without user action. **Validation:** the bad file got an Italian `role=alert` ("1 file su 2 non è stato aggiunto … non è davvero un PDF") (27–28). | **Real camera:** only the file-chooser path was tested. **Telegram, watched folder, cloud sources:** need real accounts or container access. **Learned suggestions:** none appeared on any of 6 new documents (s18), so the "uncertain suggestion" flow could not be judged. **Friction:** Save closes the dialog, so adding a sticker after a correction needs a reopen. |
| Retrieval and physical filing | 20% | **7.8** | **Search:** found the OCR phrase "judge 9473" with a highlighted text snippet, `sender:`, `date:2026-03`, `tag:`, accent-insensitive `citta`/`città`, and a sticker code in any case (08, 13). **Paper copies:** created a sticker in a location (12). Scanning the QR URL `/?sticker=R-…` opens the Paper archive with the copy and its location (18); manual lookup works, and an unknown code is announced (19). Labels print as Italian HTML with QR, title, code, and path (15). **Defect:** the **move-copy defect (H1)** silently wiped the copy's location twice during normal use (34–35). | Physical printing and a real camera scan of the printed label; the QR deep link was emulated by navigation. |
| UX and accessibility | 20% | **8.4** | **Italian:** coverage is close to complete across all 15 screens, and the wording is natural and idiomatic. `<html lang="it">`; localized date input (`gg/mm/aaaa`) and browser validation. **Keyboard and focus:** a skip link; visible 3 px focus rings; shortcuts with a help dialog (07); `/`, Esc to the first result, Enter to open; `aria-modal` dialogs with focus trap and focus return to the opener. **Announcements and layout:** live regions for search counts, saves, revocations, and upload errors. No horizontal overflow at 320 px. No text contrast failures, and no undersized targets apart from native 13 px tag checkboxes that have labels. **Defects:** focus drops to `<body>` after several async actions (M1); ambiguous repeated control names (M2); smaller gaps (L1–L5). | Installed iOS/Android PWA, the native Android client, and real VoiceOver/TalkBack: out of scope by owner decision (D7). I checked semantics through the accessibility tree, not with a live screen reader. |
| Reliability and recovery | 20% | **8.8** | **Offline queue:** an upload interrupted by going offline resumed automatically; a mixed-validity batch reported each file. **OCR retry:** worked from the preserved original and was announced ("OCR in coda… / Il PDF ricercabile è pronto"). **Restore drill:** the clean-stack drill in `.omo/evidence/restore-drill-round6.md` on this SHA is credible and specific (originals SHA-256, tags, nested location, sticker, revoked grant 401). I count it for gate 2, though it has no raw command log. **Defect:** the **H1 defect** also counts as a data-integrity regression for physical records. | Killing the worker or restarting services (forbidden on the shared stack). Session-expiry resume. A restore I ran myself. |
| Privacy and agent control | 15% | **9.3** | **Two grants:** created in the UI with a password confirmation, an expiry, and a one-time token card (focus moves to the card; announced) (25). **`tools/list` scoping:** locale = search, get_document_text, list_tags, change_document_tags; cloud = search_documents only. **No content without text scope:** the cloud grant (no text scope, tag filter) got `[]` for the OCR phrase "judge 9473", even on an in-filter document, and "Tool is not permitted" for text and semantic tools. **Audit:** in Italian, records success, denial, and failure with no document text. **Revocation:** inline confirmation, focus to "Sì, revoca", announcement; the next MCP request returned **401**, and the other grant kept working. | Real cloud agent clients; CSRF probing. |

**Weighted mean (Judge 2):** 0.25·8.6 + 0.20·7.8 + 0.20·8.4 + 0.20·8.8 + 0.15·9.3 = **8.55**

## Hard gates

| Gate | Status in this review |
| --- | --- |
| 1. Parity matrix | **Not demonstrated by me.** I did not verify FEATURE_PARITY.md row by row. The rows I touched (upload, OCR, search, tags, senders, paper copies, labels, MCP, notes, duplicates, offline queue) behave as described, except H1. |
| 2. Fresh install / upload-OCR-search / backup / clean restore | **Demonstrated, partly via evidence.** I ran upload, OCR, and search myself. Install, backup, and restore (with locations and revoked grants) are accepted from `restore-drill-round6.md` on this SHA. |
| 3. Installed iOS/Android PWA and native Android on real devices | **Out of scope by owner decision (D7).** Synology DS923+ performance, ACL, and restore checks are also out of scope by D7. |
| 4. Security review | **Partly demonstrated:** agent isolation by scope and tag filter, no text without text scope, immediate token revocation, upload validation of a fake PDF, and a password required to mint tokens. I did not test CSRF or account isolation between people. |
| 5. Tests/builds/journeys/migrations on candidate | **Not run by me.** |

## Findings

### Severe

None found.

### High

**H1 — Pressing "Sposta" without changing the dropdown silently removes a paper copy's location, and announces success.**

The location dropdown shows the copy's current location, but the request sends `null` unless the user changed the dropdown first. The copy becomes "Posizione non assegnata", and the status says "Copia cartacea R-… spostata." A user who taps Move to confirm, or a keyboard user whose arrow key doesn't fire `change`, loses the shelf record. That breaks the product's core "know which shelf" promise. History keeps the old entry, but nothing warns the user.

- **Reproduce (mobile, Italian):**
  1. Open a document that has a paper copy in "Cassetto R4J2".
  2. In "Copie cartacee" the combobox "Nuova posizione per la copia cartacea R-…" already shows "Cassetto R4J2". Tap **Sposta**.
  3. The copy now shows "Posizione non assegnata". The Library chip reads "Copia cartacea in attesa di una posizione", and history logs "Nessuna posizione".
- **Evidence:** script s20; 34-mobile-move-bug-before.png, 35-mobile-move-bug-after.png. This also happened accidentally in s16 during a keyboard run.
- **Cause:** `apps/web/src/DocumentPanel.tsx:793` displays `moveChoices[copy.id] ?? copy.location_id ?? ""`, but `DocumentPanel.tsx:378` sends `location_id: moveChoices[copy.id] || null`.
- **Fix:** send the same value that is displayed; disable Sposta when it equals the current location.

### Medium

**M1 — Keyboard and screen-reader focus is lost to `<body>` after async actions.**

After pressing **Sposta**, **Riprova l'OCR**, **Aggiungi nota**, or **Accedi** (failed sign-in), `document.activeElement` becomes `<body>`. Inside the modal dialog, VoiceOver/TalkBack users lose their place; the next Tab happens to land back inside the dialog.

- **Reproduce:** desktop, open a document with the keyboard, Tab to "Riprova l'OCR", press Enter. Focus is on `body` (s16, s19, s21).
- **Cause:** the pressed button gets `disabled={busy}` while the request runs; Chrome blurs a focused element when it becomes disabled. See `DocumentPanel.tsx:737` (OCR), `:785`/`:792` and the Move button at `~:807`, and the suggestion buttons at `:552–578`; the login button uses the same pattern.
- **Fix:** use `aria-disabled` plus a guard, or restore focus after the request.

**M2 — Repeated controls have identical accessible names.**

On "Archivio cartaceo", each location has "Vedi contenuto" (×3) and "Stampa etichetta" (×3) with no location in the name. In a screen reader's link or button list they can't be told apart (WCAG 2.4.6 / 2.4.9). "Modifica" already gets the location name ("Modifica Cassetto R4J2"), so the pattern exists.

- **Cause:** `apps/web/src/PhysicalPanel.tsx:324–325`.
- **Related:** the move button inside a copy is just "Sposta", while its combobox has the code.

### Low

- **L1 — Creating a sticker is not announced.** After "Crea adesivo" no status message is set (live regions are unchanged), so a screen-reader user gets no confirmation that R-… was created. `createCopy` (`DocumentPanel.tsx:352`) never calls `setCopyNotice`, unlike move and missing.
- **L2 — The PWA manifest is English only** (`"description":"Your documents, in place."`, `"lang":"en"`), so an Italian install shows English metadata. See `apps/web/public/manifest*.webmanifest`.
- **L3 — Untranslated search operators in the Italian help.** The search help mixes Italian operators (`etichetta:`, `mittente:`, `titolo:`) with untranslated `is:untagged` / `is:tagged`.
- **L4 — Failed sign-in gives no field-level error.** The alert "Credenziali non valide" is announced, but the fields don't get `aria-invalid` and focus goes to `body`.
- **L5 — Cosmetic Italian and minor UX.**
  - "Bentornato." is masculine only; "Ti diamo il bentornato" would be neutral.
  - Save closes the document dialog, so a correction followed by adding a sticker takes two openings.
  - The label page has no visible print button on mobile.
- **L6 — MCP `semantic_search` call vs. tool list.** `semantic_search` is hidden from `tools/list` when semantic search is off, but calling it with a text-scoped grant returns "Semantic search is off" rather than a not-permitted error. This is consistent and harmless, noted only for completeness.

## Single most serious finding

**H1:** "Sposta" without an explicit change silently clears a paper copy's location while announcing success (`DocumentPanel.tsx:378` vs `:793`).
