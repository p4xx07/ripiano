# Judge 2 — round 8 report

- **Candidate:** `3dd08c2497a070475a249cf485184356a3a056c3` (branch `codex/initial-implementation`), running stack at http://localhost:18080 (PWA + /api + /mcp; OCR, maintenance worker and scheduler running).
- **Date:** 2026-11-19
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), channel `chrome` = Google Chrome 157.0.8103.79. Desktop 1440x900; mobile emulation 390x844, `isMobile`, `hasTouch`, DPR 2. Locale `it-IT` throughout (UI language "Lingua del dispositivo" resolved to Italian, `<html lang="it">`). Service workers blocked.
- **Account:** judge2 (password from judges.env, never written down).
- **Emphasis:** mobile-first, keyboard and screen-reader minded, Italian; focus after every action including server errors; accessible names; touch targets; offline and expired-session upload recovery.
- **Artifacts:** `qa-artifacts/20261119-r8-judge-2/` (37 PNGs; agent token field blurred, both tokens revoked).

## Commands and scripts

Scripts were kept in the session scratch folder (`.../scratchpad/judge2-r8/`, with a `node_modules` symlink to `apps/web/node_modules`), run as `node <script>.mjs [m|d]`:

| Script | What it did |
| --- | --- |
| `lib.mjs` | launch (desktop or mobile, it-IT), Italian sign-in, focus probe, audit (unnamed controls, targets under 44 px, horizontal scroll) |
| `api.mjs`, `mcp.mjs`, `mcp2.mjs` | session API client (Playwright `request`); MCP Streamable HTTP client: `initialize`, `tools/list`, `tools/call` |
| `s1-login`, `s2-shell`, `s3-add` | sign-in screen, home, Add dialog (keyboard focus, Esc return, file input labels and `capture`) |
| `s4-upload` | mobile camera / gallery / PDF upload via the three Add buttons, focus and live-region log |
| `s5-doc`, `s6-file`, `s7-guard`, `s8-expire` | filing in the document dialog; simulated 500 and offline on save; save; unsaved-changes guard; expired session mid-edit and sign-in again |
| `s9-upq` | upload while offline, then reconnect; upload after the session cookie was deleted, then sign in again |
| `s10-sweep` | all 15 sections on mobile in Italian: focus on entry, text dump, audit, screenshots |
| `s11-search` | OCR phrase, quoted phrase, title word, sender, `tag:`, `mittente:`, `data:`, bare date, stemmed Italian word; Filters panel |
| `s12-phys`, `s13-move`, `s14-scan`, `s16` | create paper copy sticker, move it, print label, look up by code (case-insensitive), by QR URL, direct QR URL navigation, unknown sticker |
| `s17`–`s21` | Agents panel; two grants created in the UI with the password, different scopes and tag filter; MCP checks; revoke in the UI; D10 removal with a wrong, then right password |
| `s22` | keyboard-only desktop: Tab, skip link, `/`, `j`/`Enter`, Tab cycle inside the unsaved-changes confirmation |
| `s23` | lost answer (server stored the upload, client saw a reset), then 502, then success: scan-ID reuse and duplicates |
| `s24`, `s25` | desktop batch of 7 fixtures plus one refused `.exe`; barcode/ASN results via API |
| `s26` | `lang`/`title`, mobile menu focus and Esc, In arrivo, "Riprova l'OCR" with simulated 500 |

## Fixture IDs used

`judge.png` (as camera `r8j2-camera-m.png` and gallery `r8j2-gallery-m.png`), `three-pages.pdf` (`r8j2-pdf-m.pdf`), `office-letter.docx` (offline upload), `office-open.odt` (expired-session upload), `office-sheet.xlsx` (lost-answer retry), `email-notice.eml`, `outlook-notice.msg`, `office-slides.pptx`, `office-legacy.doc`, `tag-barcode-desktop.pdf`, `asn-batch-desktop.pdf`, `barcode-batch-desktop.pdf` (desktop batch). Not used: `*-mobile.pdf` variants and `office-sheet.xlsx` as a plain upload.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.0** | Mobile camera, gallery and PDF buttons each open the right picker (`capture=environment` on the camera input, labelled). After each upload the dialog closes and focus goes to the new row; "Aggiunto 1 documento." is in a live region. Desktop batch of 8: 7 added, the `.exe` refused with a clear Italian reason; email/Outlook bodies dated 10 nov 2026; split barcode batches (1/2, 2/2) and ASNs 900011/900012/900001 assigned. No mandatory TODO screen: everything goes straight to the Library, In arrivo only lists failures and exact copies. Sender, date and tag set in one dialog, saved, focus returns to the row, status "“…” salvato." announced. | Telegram (real account) and watched folder (the `/sources` volume is read-only to me; I may not alter the stack): not exercised. No uncertain suggestion arose on my uploads (judge.png has no sender/date), so "correct an uncertain suggestion" was not exercised. `tag-barcode-desktop.pdf` got no tag; I did not check whether tag barcodes are opt-in. |
| Retrieval and physical filing | 20% | **9.2** | Search finds OCR phrase `judge 9473`, quoted phrase, title word, `tag:`, `mittente:`, `data:2026-03-14`, bare date, and stems Italian ("giudici" → "Giudice"). Filters panel complete. Sticker R-DLJXJ5U9 created from the document; moved to "Scaffale / Scatola" with a reminder to reprint; label opens in a new tab with title, code and new location; lookup works lowercase, uppercase, by the QR URL in the field, and by opening `/?sticker=…` directly (lands on Archivio cartaceo with the copy). | Physical printing and a real camera QR scan. |
| UX and accessibility | 20% | **8.6** | Italian is natural and complete across all 15 sections (no English leaks except developer placeholders and one raw tool name, L3). `<html lang="it">`, translated `<title>` per section, focus to the H1 on every section change, skip link, mobile menu with `aria-expanded` and Esc returning focus to the toggle, 44 px targets almost everywhere, no horizontal scroll at 390 px, server errors in `role=alert` with focus kept on the control that failed (save, agent creation; D10 wrong password focuses the password field). Defects: M1 (session end throws away edits), M2 (confirmation is not modal), M3 (In arrivo OCR retry error), L1/L2. | Real iOS/Android installed PWA and a real screen reader (VoiceOver/TalkBack/NVDA); announcements were inferred from roles/live regions. |
| Reliability and recovery | 20% | **9.0** | Upload offline → "1 file è in attesa…" → sent when back online, nothing left on the device. Upload after the session ended → sign-in screen says "1 file è in attesa su questo dispositivo e verrà caricato quando judge2 accede di nuovo" → sent after sign-in. Lost answer (server stored the file, client got a connection reset) then 502 then success: the same scan ID all three times, **one** document in the Library. Save with simulated 500 and with no connection: clear Italian alerts, nothing lost while the dialog stays open. Restore drill `.omo/evidence/restore-drill-round8.md` (this SHA, empty target, checksums, tags, sticker, revoked grant still 401) reads as credible; counted for gate 2. Lowered for M1. | Worker kill / service restart (not allowed on the shared stack); I did not create a backup myself. |
| Privacy and agent control | 15% | **9.3** | Two grants created in the UI, each needing the password. `tools/list`: local = `search_documents, get_document_text, list_tags, change_document_tags`; cloud = `search_documents` only. Cloud grant (filter "Bollette J2"): documents outside the tag invisible, `get_document_text` and `change_document_tags` refused ("Tool is not permitted for this agent") and logged as "rifiutato", and full-text search does not match OCR-only words (no content leak through search). Revoking cloud → MCP 401 at once, local still 200. Audit list shows each call with result and document title, no text. D10: removing a revoked agent with its log asks for the password; wrong password refused and focused. All four of my grants revoked; one removed. | Real cloud agent / real Ollama. |

**Weighted mean:** 0.25×9.0 + 0.20×9.2 + 0.20×8.6 + 0.20×9.0 + 0.15×9.3 = **9.01**

## Hard gates

| Gate | Status |
| --- | --- |
| 1. Parity rows have a scenario or accepted deviation | Not re-audited in full; every row I touched (upload channels, email, Office, barcode split/ASN, search syntax, physical copies, agents, Trash links) worked. Not demonstrated by me. |
| 2. Fresh install, upload/OCR/search, backup, clean restore | Demonstrated by the separate drill on this SHA (`.omo/evidence/restore-drill-round8.md`), which I find credible; upload/OCR/search demonstrated by me. |
| 3. Installed iOS/Android PWA and native Android on real devices | **Out of scope by owner decision (D7).** Browser emulation only. |
| 4. Security review items | Partially demonstrated: agent isolation, scope filter, revocation 401, password re-confirmation, upload type validation, CSRF-loss retry path. Note L4 (quickstart runs Django DEBUG). |
| 5. Tests/builds/migrations on candidate | Not run by me. |
| Out of scope by owner decision | Real phones, real Telegram/Google/Microsoft/Dropbox accounts, DS923+ performance/ACL/restore. |

## Findings

### Severe
None.

### High
None.

### Medium

**M1 — When the session ends during an edit, the document's unsaved changes (and an unsent note) are discarded without warning, and signing in again does not return to the document.**
Repro (mobile, Italian): open a document → change Titolo and type in "Nuova nota" → session ends (I deleted the `sessionid` cookie) → tap "Salva modifiche". The sign-in screen says "Sei stato disconnesso…"; sign in → you land on Tutti i documenti, no dialog, title and note gone (`s8-expire.mjs`, `07-expired-save-m.png`).
Cause: `apps/web/src/App.tsx:1411` `setSelectedDocument(null)` inside the session-ended handler, which also drops `?document=` from the address, although the comment at `App.tsx:1400-1402` says the screen address is kept so signing in again returns to it. Uploads in the same situation are kept (good); edits are not.

**M2 — The "unsaved changes" confirmation is not modal: Tab leaves it and reaches the document form behind it.**
Repro (desktop or mobile, keyboard): open a document, edit Titolo, press Esc → "Ci sono modifiche non salvate" appears with focus on "Continua a modificare" (good) → Tab → "Scarta le modifiche" → Tab → "Apri a grandezza intera" / "Copia identica…" in the document dialog underneath, which is neither `inert` nor `aria-hidden`. A screen-reader or keyboard user can wander into the form and edit while the question is pending (`s22.mjs`, `22-alertdialog-trap-d.png`, also seen on mobile in `s7-guard.mjs`).
Cause: `apps/web/src/DocumentPanel.tsx:621` renders `role="alertdialog"` inline in the panel without `aria-modal`, focus containment, or making the rest of the dialog inert.

**M3 — In arrivo: when "Riprova l'OCR" fails, focus is lost to `<body>` and the error's "Riprova" button does something else (reloads the list from the next page cursor) in a 54x17 target.**
Repro (mobile): In arrivo → a failed document (my `r7j2-damaged`) → "Riprova l'OCR" with the retry endpoint answering 500 (simulated with `page.route`) → alert "Il server ha inviato una risposta inattesa. Riprova." appears, `document.activeElement` is `BODY`, and the alert's "Riprova" button calls `load(documents.length ? nextCursor : null)` instead of retrying OCR (`s26.mjs`, `26-retry-500-m.png`).
Cause: `apps/web/src/InboxPanel.tsx:139-151` (button disabled while busy loses focus; nothing restores it on error) and `InboxPanel.tsx:165` (the shared inline-error retry handler is a list load, not the failed action).

### Low

- **L1 — Error dismiss buttons are tiny touch targets.** "Chiudi errore" on Archivio cartaceo after an unknown sticker is 28x18 px; the In arrivo "Riprova" is 54x17. `.inline-error button` in `apps/web/src/style.css:807-813` and `1064-1066` sets no minimum size (`16-sticker-notfound-m.png`).
- **L2 — Some status messages are mounted already filled in, so screen readers may stay silent.** The queued-upload notice ("1 file è in attesa di caricamento…") and the offline notice are conditional `role="status"` elements rendered with their text (`App.tsx:2148-2159`); my live-region observer never saw them change, unlike the document count and "Aggiunto 1 documento.". The sticker-created and copy-moved confirmations did reach live regions. The `UploadCloud` icon at `App.tsx:2157` lacks `aria-hidden`.
- **L3 — Small Italian polish issues.** "Sei stato disconnesso" is masculine while the rest of the UI avoids gender ("Ti diamo il bentornato"); "Elaborazione non riuscita: Il riconoscimento…" has a capital after the colon; "La password non è corretta" and the upload refusal have no final period, unlike other messages; an audit entry for an unknown tool shows the raw English name ("read document text", `AgentPanel.tsx:386` fallback). The People password field reads "La tua passwordServe per…" to text extraction (label and hint not separated), which may reach screen readers as one run.
- **L4 — The README quickstart runs Django in DEBUG.** `.env.example` sets `RIPIANO_DEBUG=1`; on this stack any unknown `/api/...` path returns Django's debug 404 listing every URL pattern. Production mode refuses to start without HTTPS, and `.env.example` says "Local quickstart only", so this is low, but the README install step does not mention it.
- **L5 — Search on Enter gives no result count to screen readers.** After a search, focus stays in the field (fine) but the count is only in the list header; I could not confirm a live announcement of the new count for search (the document count status did update for uploads).

## Single most serious finding

**M1**: an ended session silently throws away the person's unsaved document edits and unsent note, and signing in again does not return to the document (`apps/web/src/App.tsx:1411`, contrary to the comment at 1400-1402). Uploads already survive this case; edits should too, or the user should at least be returned to the document with the draft.
