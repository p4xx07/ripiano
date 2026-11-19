# Judge 2 — round 3 report

- Candidate: `d8724ff32baa77fb5f58c35a49fa0ee933b75576` (branch `codex/initial-implementation`), running stack at `http://localhost:18080`.
- Date: 2026-11-18. Account: `judge2` (archive owner role in this stack).
- Browser: Google Chrome 157.0.8103.79 (headless, `channel: "chrome"`) driven by Playwright 1.64.1 on macOS (Darwin 25.6.0).
- Emphasis: mobile-first, keyboard and screen-reader-minded user working in Italian.
- Viewports: mobile emulation 390x844 (`isMobile`, `hasTouch`, locale `it-IT`), reflow check 320x568, desktop 1440x900 (locale `it-IT`), one English pass (`en-GB`).
- Artifacts: `qa-artifacts/20261118-r3-judge-2/` (38 screenshots plus `scripts.mjs.txt`, the scripts concatenated; no token or password values).

Independence notes: I did not read any `judge-*` or `parity-audit-*` evidence file or another judge's artifact folder. The brief told me to read `docs/DECISIONS.md`; its uncommitted D7 text states the earlier rounds' weighted means, so I saw those two numbers. The account already held 15 documents from an earlier session; I added my own (prefix `r3j2m64j`) and changed nothing I did not create.

## Commands and scripts

Each script was run as `cd apps/web && node <scratch>/j2/<name>.mjs`; `curl` was blocked by the session's permissions, so HTTP/MCP calls were made with Node `fetch` inside the scripts.

| Script | What it did |
| --- | --- |
| `s1`, `s2` | Italian sign-in on mobile; opened the menu; visited all 15 screens with a structural audit (accessible names, labels, duplicate ids, alt text, heading order, landmarks, touch-target size, horizontal overflow) and dumped the Italian text |
| `s4` | Mobile capture: camera input, gallery input, 4-file batch with one unsupported file, an upload made offline, reload while offline, reconnect; recorded every live-region message |
| `s5`, `s7` | Document dialog on mobile: corrected title, created a sender and a tag inline, saved, created a paper sticker in a location |
| `s8`, `s9` | 25 searches (OCR phrase, accents, stems, sender, date, tag, sticker, invalid input), filter panel, sticker lookup, printable label |
| `s10`, `s11` | Created two agent grants, called MCP (`initialize`, `tools/list`, `tools/call`) with each token, with no token and with a bad token; revoked one in the UI; read the activity log |
| `s12` | Desktop keyboard-only: tab order, focus ring, skip link, `?`, `/`, `j`/Enter, `g`+letter, `n`, 120-Tab focus-trap test, browser Back, contrast scan in the three themes |
| `s13`, `s14`, `s15` | Mobile: Back closes dialog, move/missing/found paper copy, re-run OCR, upload aborted mid-request then retried, bulk Trash and restore, manual backup, Inbox, 320 px reflow, English-mode leak check |

Also: `npx playwright --version`, Chrome `--version`, `git show HEAD:<path>` for the file:line references below. I did not run the repository's own unit/API/e2e suites.

## Fixture IDs used

`judge.png` (gallery), `three-pages.pdf`, `office-letter.docx`, `email-notice.eml`, `office-open.odt` (offline upload), `office-slides.pptx` (interrupted upload). One supplementary input that is not a fixture: a generated Italian "camera scan" PNG (`r3j2m64j-camera.png`, rendered in the browser with accented words, a date, and a unique keyword), because every fixture is byte-identical to a document already in the account and the fixtures contain no accented Italian text. A 4-byte `.txt` was used as the unsupported file.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 8.5 | Camera, gallery and file inputs all landed in the Library as "Pronto" without any mandatory screen; focus moved to the new document; mixed batch reported "1 of 4" rejected with the reason; date 12 mar 2026 detected from Italian text; title, new sender and new tag corrected and saved in the one dialog (screens 10–22). Friction: title stays the file name, the sender printed on the scan was not proposed, no suggestion appeared to correct, Italian singular/plural error in the rejection message, clipped titles in the mobile list | Telegram file (real account, out of scope). Watched/consume folder: not exercised, I had no way to place a file in the mount without touching the stack. "Uncertain suggestion" was not produced by this small archive |
| Retrieval and physical filing | 20% | 8.0 | OCR phrase, quoted phrase, sender (`sender:` and `mittente:`), date (`date:`/`data:` month and day), tag (`tag:`/`etichetta:`), sticker code all returned the right document with a passage; sticker lookup on the Paper screen, move, history, missing/found all worked; label page is in Italian. Defects: typing without accents finds nothing (`perche`, `citta qualita` → 0), `melograni` does not find `melograno`, moving a copy is not announced | Scanning a QR with a camera and re-scanning a printed label: not exercised (no camera; my in-browser QR decode attempt failed for tooling reasons, so the QR content is unverified) |
| UX and accessibility | 20% | 8.5 | Italian is natural and complete on all 15 screens, no English leaks in Italian and none the other way; `lang`, per-screen titles, one `h1`, focus moved to the `h1` on navigation, dialogs trap focus (0 escapes in 120 Tabs) and return it, Back closes a dialog, visible 3 px focus ring, working skip link and shortcuts, status/alert regions for uploads, saves, Trash. Defects: touch targets of 16–28 px on mobile, skip link at 1.94:1 contrast in dark themes, horizontal overflow at 320 px on four screens, result count not announced, several identically named buttons | Installed iOS/Android PWA and Android client (out of scope). No real screen reader was run; findings are from the accessibility tree and live regions |
| Reliability and recovery | 20% | 8.5 | Offline upload queued on the device, survived a reload while offline, and was sent on reconnect; an upload aborted mid-request was queued and sent on retry, no duplicate; re-run OCR queued from the original; bulk Trash and restore; manual backup went from "in attesa" to "completato" (snapshot `20261118T124206478714Z-126ff2dc`) | Stopping the worker and restarting services (forbidden on the shared stack). Restore: only the separate drill, which ran on `f2b9416`, not this commit, and did not check locations or revoked grants on the restored stack |
| Privacy and agent control | 15% | 9.0 | Grant A (titles only, tag filter): `tools/list` = `search_documents` only; saw exactly the one tagged document; OCR-only words returned nothing; `get_document_text`, `list_tags`, `change_document_tags` refused. Grant B (titles + OCR text, all documents): two tools, text readable, tag change refused, `semantic_search` reports it is off. No token and bad token: 401. After revoking A in the UI (with a confirm step): 401 for A, B unaffected. Every call, including refusals, is in the activity log with agent, action, outcome, time | A text-scoped grant with a tag filter reading a document outside the filter was not tested. The activity entries I saw name the action but not the document |

**Weighted mean: 8.48** (8.5×0.25 + 8.0×0.20 + 8.5×0.20 + 8.5×0.20 + 9.0×0.15 = 8.475).

No dimension reaches 9.0. Nothing I found loses data or leaks content.

## Hard gates

| Gate | Demonstrated? | Note |
| --- | --- | --- |
| 1. Every parity row has a working scenario or accepted deviation | Not demonstrated by me | I exercised the capture, search, filing, paper, Trash, backup, agent, localisation and keyboard rows only; no row-by-row parity pass |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Partly | Upload/OCR/search and backup shown on the running stack. Restore relies on `.omo/evidence/restore-drill-20261118.md`, which I find credible for originals and tags, but it ran on `f2b9416` and says itself that locations and revoked grants were not checked live. NAS restore: out of scope by owner decision |
| 3. Installed iOS PWA, Android PWA, native Android client on real devices | Out of scope by owner decision | Browser emulation only |
| 4. Security review | Partly | Agent isolation, scope enforcement and token revocation shown. CSRF, upload validation beyond one unsupported type, and account isolation between people were not probed by me |
| 5. Tests, builds, journeys, migrations, deployment checks on the candidate | Not demonstrated by me | I did not run the suites |

## Findings

No severe or high findings.

### Medium

**M1. Search is accent-sensitive, so Italian typed without accents finds nothing.**
Repro: upload a scan containing "perché più città qualità"; in the Library search `perche` → "0 documenti trovati"; `citta qualita` → 0; `città` → 1. Phone keyboards and quick typing routinely drop accents, and OCR itself sometimes drops them. Cause: no accent folding anywhere in the search path (`grep -n unaccent services/api/archive/*.py` returns nothing; see `archive/fulltext.py`).

**M2. Touch targets well under 24 px on mobile for frequently used actions.**
Repro at 390x844, Italian: (a) document dialog → Copie cartacee: "Cronologia" 77x16, "Stampa adesivo" 100x26, "Segna come mancante" 115x26, set side by side as small wrapped text (screen 23); (b) document dialog → File: "Scarica l'originale", "Esporta il documento in ZIP", "Apri il PDF ricercabile" are 17 px tall, stacked; (c) Etichette e archiviazione → Mittenti/Tipi: "Rinomina …" and "Elimina …" icon buttons are 28x21 and adjacent. The delete next to rename at that size is an easy mis-tap.

**M3. Four screens overflow horizontally at 320 px width.**
Repro: 320x568 mobile emulation, open `/paper` (layout grows to 353 px), `/people` (356), `/backups` (337), `/agents` (331). On `/paper` the "Posizioni" card runs to x=353; on `/people` the person rows run to x=339 (screen 72). The other five screens checked and the document dialog fit. No overflow at 390 px.

### Low

**L1. Italian plural error in the upload rejection message.** Upload 4 files with one unsupported → "1 file su 4 non sono stati aggiunti." Should be singular for 1 ("non è stato aggiunto"). `apps/web/src/locales/AppLibrary.ts:259`.

**L2. Skip link fails contrast in the dark and AMOLED themes.** Aspetto → Scuro, press Tab: white text on `rgb(134,201,149)`, 1.94:1. `apps/web/src/style.css:4401-4402` (`background: var(--color-primary); color: #fff`). Light theme passes.

**L3. Search result count is not announced.** After a search the "1 documento trovato" line (`apps/web/src/App.tsx:1678`, `p.library-counts`) is not in a live region and the three live regions stay empty; a screen-reader user hears nothing, including for "0 documenti trovati".

**L4. Moving a paper copy gives no status message.** Document dialog → choose a new location → "Sposta": the location text changes silently. Marking missing/found on the same card does announce.

**L5. Identically named buttons.** Inbox: every row's button is just "Tienili entrambi"; Trash: "Ripristina" / "Elimina definitivamente" carry no document name. Elsewhere (Revoca, Rinomina, Seleziona) the name includes the object.

**L6. `melograni` does not find `melograno`.** Search `melograni` → 0 while `melograno r3j2m64j` → 1; other stems work (`disponibili` finds "disponibile", `bollette` finds "bolletta"). I did not locate the cause.

**L7. Long titles are cut mid-letter in the mobile list.** "Avviso TARI 2026 lampone" renders as "Avviso TARI 2026 lampo" with no ellipsis while the status pill sits beside it (screen 12).

**L8. Capture leaves obvious filing undone.** The generated scan's title stayed `r3j2m64j-camera` and the sender printed at the top was not proposed; the history entry is named "Rilevamento di data e mittente" but only the date was set. A new user with no senders yet gets no help here.

**L9. Smaller items.** Mixed date styles in Italian ("18 nov 2026" in most places, "18/11/2026, 10:48:27" on Overview, People and paper history); the QR on the printable label is an unnamed `svg`; the browser tab title does not change when a document is open; no `prefers-reduced-motion` rule in `style.css` (only three transitions/animations exist); the search hint shows the English field names only although `mittente:`, `etichetta:`, `data:` work; an invalid `date:` query is retried seven times before the (clear, Italian) error settles.

## Single most serious finding

M1: accent-sensitive search. For an Italian archive it is the defect most likely to make a real document look missing.
