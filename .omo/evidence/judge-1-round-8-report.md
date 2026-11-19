# Judge 1 — round 8 report

- **Candidate SHA:** 3dd08c2497a070475a249cf485184356a3a056c3 (branch `codex/initial-implementation`); judged on the running stack at http://localhost:18080.
- **Date:** 2026-11-19 (run 12:26–12:50 CET).
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (`channel: "chrome"`). Desktop 1440x900; mobile emulation 390x844, `isMobile`, `hasTouch`, DPR 2; locales `en-US` and `it-IT`.
- **Account:** judge1 (password read from judges.env at run time, never written down).
- **Artifacts:** `qa-artifacts/20261119-r8-judge-1/` (screenshots; agent tokens blurred before capture).
- **Scripts (kept outside the repo):** `<scratchpad>/j1r8/lib.mjs`, `s1.mjs`…`s27.mjs`, `mcp.mjs`, `qr.mjs`; each run as `cd apps/web && node <scratchpad>/j1r8/sNN.mjs`. `mcp.mjs` speaks Streamable HTTP JSON-RPC (`initialize`, `tools/list`, `tools/call`) with a bearer token. Watched-folder drop: `docker exec -i ripiano-maintenance_worker-1 sh -c 'cat > /sources/r2-judge1/.r8j1-watched.tmp && mv … r8j1-watched.pdf' < fixtures/tag-barcode-mobile.pdf` (judge1's own existing NAS-folder source; no container was restarted or changed).

## Fixture IDs used

`three-pages.pdf` (as r8j1-lease.pdf), `judge.png` (as r8j1-camera.png, r8j1-m-camera.png, and renamed `r8j1-png-named.pdf`), `office-letter.docx` (r8j1-letter.docx, r8j1-aborted.docx), `email-notice.eml` (r8j1-notice.eml), `office-sheet.xlsx` (r8j1-sheet.xlsx), `office-open.odt` (r8j1-offline.odt), `tag-barcode-mobile.pdf` (r8j1-watched.pdf, watched folder). Derived damaged inputs: `r8j1-truncated.pdf` (first half of three-pages.pdf), `r8j1-garbage.pdf` (4 KB random bytes), `r8j1-empty.pdf` (0 bytes).

## What I exercised

**Capture (desktop):** camera input with judge.png; one 8-file batch through "Browse files" (PDF, DOCX, EML, XLSX, truncated PDF, garbage PDF, empty PDF, PNG named .pdf). Result: 6 added, and one clear summary for the two refused files ("could not be read as a PDF. It may be damaged, or it is not really a PDF." / "File is empty"). The two 400 responses in the console are those refusals. The EML got its subject as title, a tag, and its date. Every stored original downloaded byte-identical to its input (SHA-256 compared for 8 documents). The PNG named `.pdf` downloads as `r8j1-png-named.png`. The truncated PDF ends `failed` with an honest message ("kept the original and made the pages it could read searchable"), and its page‑1 word "otter" is findable.

**Capture (mobile):** the "Add" sheet's camera input; then an aborted upload (first POST reset): the item queued with "Ripiano couldn't be reached; trying again… Send now" and arrived. An offline upload: the offline banner plus "1 file is waiting… sends it when the connection is back"; it arrived after reconnecting. No horizontal scroll (scrollWidth 390).

**Filing / suggestion correction in one screen:** in the lease document I typed a title and date, then tapped the suggestion "Set sender: R7J1 Lontra Immobiliare". The sender was saved at once and my unsaved title and date stayed in place ("Sender … saved. Other edits still need Save changes."). Then Save changes.

**Unsaved-edit handling:** a confirmation ("You have unsaved changes. Close without saving them? Keep editing / Discard changes") appeared on Close, Esc, browser Back (mobile), "Open earlier copy" (Italian), an unadded note, and tag or follow-up toggles. Reload triggered the native `beforeunload` prompt. Esc on the confirmation returns to editing with the edits intact.

**Physical filing:** created sticker R‑PSVZDFBA with no location; moved it to Studio scaffale / Scatola 2026 with a "print it again" hint; history; printed the label (HTML, 70x40 mm, QR plus code plus path, updated after the move). Marked missing, then found, in Italian on mobile. The sticker lookup shows "missing / last known location". Moved it again on mobile to Armadio ingresso. Location label L‑7LXXV6U8 and the location lookup list the 6 copies in nested locations.

**Scanning a sticker QR into "Find a sticker":** the label QR encodes `PUBLIC_ORIGIN/?sticker=<code>` (`physical_views.py:420`). I could not decode the PNG locally (no decoder installed; Chrome's BarcodeDetector is unavailable on macOS headless), so I simulated both scan paths with that exact address:
- (a) a keyboard-wedge scanner typing the full URL in lowercase into "Find a sticker" plus Enter: the field normalised to `R-PSVZDFBA` and the copy was found;
- (b) a phone QR app opening the URL: it redirected to `/paper?sticker=…` with the result shown, on desktop and on mobile in Italian.
An unknown code gives "Sticker not found".

**Retrieval:** OCR words ("heron badger", with a text snippet), sender, title, sticker code, `tag:`; the search tips explain the `date:` syntax. A free-text "lontra 2026-10" finds nothing, and "heronn" has no typo tolerance.

**Keyboard:** `/`, `j`, Enter, and Esc (focus returns to the row), the `?` help, `g p` navigation, and a focus trap inside the dialog.

**Italian:** no English strings left on Library, Paper, Inbox, Agents, Overview, Trash, or the document dialog; the printed labels are in Italian.

**Agents/MCP:** creating each agent asked for my password.
- **R8J1b Cloud** (titles only, filter tag r7j1-affitto): `tools/list` = `[search_documents]`. The OCR-word search returns nothing and `get_document_text` is refused ("Tool is not permitted").
- **R8J1b Local** (titles + OCR + tags): 4 tools, and it reads the text.
The audit lists "done" and "refused" entries without any text. After revoking Cloud, its token gets 401 while Local keeps working; after revoking Local it gets 401 too. All 4 grants I created (2 created blind when the token was in an input value I did not read) are revoked.

**Security probes:** a PATCH without the CSRF header gets 403 "could not be verified"; a cross-origin `fetch` POST to trash is blocked and the document is unchanged.

**Watched folder:** I dropped `r8j1-watched.pdf` into judge1's NAS-folder source with an atomic rename. About 80 s later (the 1‑minute stable-file rule plus the poll interval) it had been moved to `processed/` and appeared as `r8j1-watched`, ready, "from NAS folder", not flagged as a duplicate (screenshot 38). It got no tag, which is expected: judge1 has no mapping for the fixture's tag barcode.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | Steps 03–05 and 20–22, 27–29: camera, PDF, Office, EML, batch with mixed validity, damaged files, offline and aborted uploads, one-screen suggestion; no mandatory TODO screen (the Inbox only lists failures and exact copies). Deductions: a damaged-but-salvaged PDF is shown as "Processing failed / Needs attention" with a futile "Retry OCR" and no preview (M2); the row Retry button is unstyled (M1). | Telegram (real account), native Android scanner, installed PWA (D7) |
| Retrieval and physical filing | 20% | 9.0 | 09–12, 24–26, 32–33, 36: create, move, missing/found, history, print and re-print, location label, URL normalisation for wedge scanners and QR apps, search by OCR, sender, sticker, and tag. Deductions: "Scan a QR code" offers no scan action in the PWA (M3); the open history goes stale after a move (L1); free-text dates need `date:`. | Decoding the printed QR image itself; real phone camera |
| UX and accessibility | 20% | 9.0 | Unsaved-edit guard on every exit path; keyboard shortcuts and focus return; Italian complete; mobile has no overflow and touch-size controls. Deductions: M1 (unstyled button on every failed row, desktop and mobile), M2, mobile copy-card spacing, Italian "Segna"/"Segnala" wording mismatch (L3). | Screen reader (no VoiceOver run), installed PWAs, Android client |
| Reliability and recovery | 20% | 9.1 | Aborted and offline uploads recover automatically; refused files are reported per file; originals byte-identical; retried OCR on the damaged PDF is stable; the round‑8 restore drill (`.omo/evidence/restore-drill-round8.md`, same SHA) is credible: checksums, tags, locations, and revoked grants verified after restoring into an empty stack. | Killing the worker or restarting services on the shared stack (forbidden by the brief); my own backup/restore |
| Privacy and agent control | 15% | 9.4 | Two scoped agents, tool lists, document filter, refusal of text without permission, audit without text, password on creation, revocation → 401, CSRF 403. | Semantic search with a real Ollama |

**Weighted mean:** 0.25·9.0 + 0.20·9.0 + 0.20·9.0 + 0.20·9.1 + 0.15·9.4 = **9.08**

## Hard gates

| Gate | Demonstrated in this run? | Notes |
| --- | --- | --- |
| 1. Parity scenarios | Partly | Every scenario I touched worked. I did not walk the whole FEATURE_PARITY matrix (focus run). |
| 2. Install / upload / OCR / search / backup / clean restore | Yes, via the drill evidence plus my upload/OCR/search | `.omo/evidence/restore-drill-round8.md` on 3dd08c2; I could not restart the shared stack myself. |
| 3. Installed iOS/Android PWA, native Android | Out of scope by owner decision (D7) | Not counted against scores. |
| 4. Security review | Partly | Agent isolation, revocation, CSRF, upload validation, and no document text to a cloud agent without permission were checked live. No code-level security review. |
| 5. Tests / builds / journeys / migrations | Not run by me | I judged the running build. |
| DS923+ performance, ACLs, NAS restore; real Telegram and cloud accounts | Out of scope by owner decision (D7) | |

## Findings

No severe and no high findings.

### Medium

- **M1 — The Retry OCR button on failed Library rows uses the browser's default button look.** It has a grey background (`rgb(239,239,239)`) and an outset border, next to the flat eye and download icons. It is visible on every "Needs attention" row on desktop and mobile (screenshot 20-mobile-library.png).
  - Repro: Library → any failed row → computed style of `button[aria-label^="Retry OCR for"]`.
  - Cause: `apps/web/src/App.tsx:2376-2383` reuses `className="download-link"`, which is styled for `<a>`; there is no button reset.
- **M2 — A damaged PDF that was partly salvaged is presented as a plain failure, and the remedy offered does not work.** The row and Inbox say "Processing failed" / "OCR could not finish" and "Needs attention", and offer **Retry OCR**. Retrying gives the same result (verified). Meanwhile the message says the readable pages *were* made searchable, and they are ("otter" finds it). The document dialog shows "No preview for this document.": `/pages` and `/pages/1.png` return 400 "This PDF could not be read", and `/archive` returns 409. A first-time owner gets mixed signals and cannot see what was saved.
  - Repro: upload the first half of `three-pages.pdf` → wait → Library row, Inbox, document dialog.
  - Cause area: `DocumentPreview.tsx:20` gates the preview on `status === "ready"` or a PDF the renderer can open; the status and Retry button come from the `failed` status.
- **M3 — "Find a sticker" says "Scan a QR code…" but the PWA has no scan action.** There is no camera button and no hint to use the phone's camera app. Scanning works only if the owner opens the QR with another app (which then deep-links correctly) or uses a keyboard-wedge scanner. On a phone, a first-time owner will tap around for a scanner.
  - Repro: mobile → Paper archive (screenshot 36-mobile-find-sticker.png).
  - Cause: `PhysicalPanel.tsx` "Find a sticker" form, about lines 263–285 (text input only).

### Low

- **L1 — The open copy history goes stale after Move.** After moving a copy with its history open, the list does not include the new move (screenshot 26-mobile-it-moved.png: the top entry is still "found", in Scatola 2026, while the card says Armadio ingresso). The API history is correct. Cause: `DocumentPanel.tsx` `moveCopy` (about lines 434–462) calls `refreshCopies()` but not `showHistory(copy)`, unlike `setCopyMissing`.
- **L2 — The history has no "created" entry for a sticker created without a location.** The first entry is the later move "from [] → …".
- **L3 — Italian wording mismatch:** the button says "Segna come ritrovata" but the hint says "Segnala come ritrovata prima di cambiarne la posizione".
- **L4 — Search has no free-text date or typo tolerance.** "lontra 2026-10" and "heronn" return nothing; the tips do explain `date:2026-10`.
- **L5 — Mobile copy card spacing.** A large empty gap separates "Print sticker / History" from "Mark missing" (screenshot 26).

## Single most serious finding

**M2.** For a damaged PDF, the app's status, Inbox entry, and suggested action (Retry OCR) contradict its own message that the readable pages were salvaged and are searchable. There is also no preview of the salvaged pages, so the owner cannot check what was kept.
