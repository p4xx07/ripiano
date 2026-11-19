# Judge 2 — Round 4 report

- Candidate SHA: `b57e14e6c529d7fdeb5b9b7ff6b023d28fe88a7b` (branch `codex/initial-implementation`); running stack at http://localhost:18080
- Date: 2026-11-18
- Judge account: `judge2` (password from judges.env, not recorded)
- Browser: Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (channel `chrome`)
- Profiles: desktop 1440x900 `it-IT`; mobile 390x844 `isMobile`/`hasTouch`/DPR 2 `it-IT`; extra reflow check at 320x640
- Emphasis for this judge: mobile-first, keyboard and screen-reader-minded user who works in Italian.

## Commands and scripts

All scripts are under `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j2/`. Each was run from `apps/web` as `node <scratch>/j2/sNN.mjs`. `lib.mjs` signs in through the real UI (Italian labels `Nome utente`/`Accedi`) and reads the password from judges.env at runtime.

| Script | What it does |
| --- | --- |
| s1 | Mobile Italian sign-in, Library aria snapshot |
| s2 | Mobile Italian Add dialog, 6-file batch upload through `Sfoglia i file` |
| s3 | Waits for processing, OCR search `9473`, opens the detail dialog |
| s4 | Italian search probes via API (stemming, phrases, accents); desktop keyboard-only journey (Tab order, `/`, Enter, Esc, `?`) |
| s5 | Mobile drawer focus behaviour, landmarks/h1, touch-target and contrast heuristics, URL routing/Back |
| s6–s8 | Physical filing: create location, create sticker, printable label (lang), sticker lookup (lowercase), QR deep link `/?sticker=…`, move, mark missing, history |
| s9–s11 | Agents: two grants (titles-only + tag filter "cloud"; OCR+tags "locale"), MCP `initialize`/`tools/list`/`tools/call` against `/mcp`, denial, audit, revoke → 401, REST with agent token |
| s12 | Offline upload queue (context offline, reload while offline, reconnect), mixed-validity batch (invalid "PDF") |
| s13 | Sweep of all 15 navigation screens in Italian for English leftovers in visible text and aria-label/placeholder/title; Inbox |
| s14 | Field search (`sender:`, `mittente:`, `date:`, `data:`, ranges, `tag:`, `etichetta:`, negation, accents, sticker code, `asn:`), Filters panel |
| s15 | Trash and restore on mobile via keyboard, focus tracking |
| s16 | 320 px reflow on 14 routes, 200 % root font size |
| s17 | 390 px overflow re-check; automatic tag-origin badge in detail |

Also used: `git show HEAD:<path>` for code references; a scripted coverage check of `services/api/archive/messages_it.py` against all `"error": "…"` literals in `services/api/archive/*.py` (264 unique; 7 untranslated, all technical: `invalid request`, `not found`, `request too large`, `invalid_grant`, `only_if_empty must be a boolean`, `embedding failed; see the embedder log`, and an empty string). `curl` was blocked by the harness, so all HTTP and MCP calls went through Playwright's request context.

## Fixture IDs used

`judge.png`, `three-pages.pdf`, `office-letter.docx`, `email-notice.eml`, `outlook-notice.msg`, `office-sheet.xlsx`, `office-open.odt` (offline queue), plus a synthetic invalid `*-bad.pdf` (24 bytes of text) for the mixed-validity check. My documents use the prefixes `j2r4-1795019936022-` and `j2off-mwmcr1l3`; I created the location `Cassetto R4J2`, sticker `R-MN7UXQ54`, and agents `R4J2 cloud mwmcq7xf` (active) and `R4J2 locale mwmcq7xf` (revoked).

Artifacts: `/Users/debotta/dbrepos/ripiano/qa-artifacts/20261118-r4-judge-2/` (30 PNGs; the agent-token field is masked).

## Scores

| Dimension | Weight | Score | Evidence (exercised) | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 8.8 | Six-format batch upload on mobile Italian (PNG, PDF, DOCX, EML, MSG, XLSX). All reached `ready`, and nothing required a TODO screen. Email subject became the title and its Date header the document date (2026-11-10). A rule tag shows a `Regola` origin badge and can be removed on the same detail screen. Duplicates are flagged as "Copia identica di …". A mixed-validity batch reports the bad file in Italian. Live ingestion status: "6 in elaborazione". (s2, s3, s12, s17) | Real camera, Telegram, watched folder and S3/Drive sources (out of scope or not reachable from the browser). "Uncertain suggestion" not triggered: no low-confidence learned suggestion appeared on the corpus. |
| Retrieval and physical filing | 20% | 9.1 | Italian stemming (`rifiuto`, `contribuenti`, `tasse rifiuti`), accent-insensitive search (`perche`/`perché`), phrase search, Italian field aliases (`mittente:`, `data:`, `etichetta:`), ranges, negation and sticker-code search all work. Sticker lookup accepts lowercase. The QR deep link `/?sticker=` opens the lookup result. Move, mark missing (move locked until found), and a dated history all work. The printable label is `lang="it"`. (s4, s6–s8, s14) | Physical printing and camera QR scanning (emulated through the URL the QR encodes). |
| UX and accessibility | 20% | 8.4 | Italian coverage is essentially complete: no English found on 15 screens in visible text or ARIA attributes. Skip link, 3 px focus outlines, `nav`/`main`/`header` landmarks, one h1 per screen, real URLs with working Back. Shortcuts `/`, `?`, `g`-chords and `j/k` (help dialog in Italian). Dialogs focus Close, close on Esc, and return focus to the opener. Live-region statuses are in Italian. Defects: findings M1–M3 and L1–L4. | Installed iOS/Android PWA and the native Android client (out of scope). No real screen reader (VoiceOver/TalkBack); judged from the accessibility tree. No axe (installing it was not allowed). |
| Reliability and recovery | 20% | 8.5 | The offline queue survived a reload while offline and sent the files after reconnecting. The invalid file was reported per file and the valid one reached `ready`. Trash → restore keeps the document. Retry/queue banners are clear. (s12, s15) | Worker or service restart, backup and clean-stack restore: the brief forbids restarting the shared stack, and `.omo/evidence/restore-drill-round4.md` did not exist when I finished. Score reflects only the narrow slice exercised; M4 noted. |
| Privacy and agent control | 15% | 9.4 | Two grants: the titles-only + tag-filtered agent got `tools/list` = `search_documents` only. It could not find documents by OCR text (`9473` → 0) and only saw tag-filtered titles. `get_document_text` → "Tool is not permitted" and was audited as `negato`. The OCR agent got 4 tools and read text. Revoking needs a confirmation (focus moves to "Sì, revoca"), then MCP → 401. An agent token on `/api/documents` → 401. The audit keeps no document text. (s10, s11) | Real cloud MCP clients. |

**Weighted mean (judge 2): 0.25·8.8 + 0.20·9.1 + 0.20·8.4 + 0.20·8.5 + 0.15·9.4 = 8.81**

## Hard gates

| Gate | Demonstrated by judge 2? | Notes |
| --- | --- | --- |
| 1. Feature parity scenarios | Partially | Upload/Office/email/OCR/search/tags/sender/type/dates/physical/agents/trash exercised. Mail accounts, sources, workflows, sharing, custom fields and barcodes were not run in this session. |
| 2. Fresh install / backup / clean-stack restore | Not demonstrated | Restarting the stack was forbidden. `.omo/evidence/restore-drill-round4.md` was absent at the time of writing, so I could not count it. |
| 3. Installed iOS PWA, Android PWA, native Android on real devices | Out of scope by owner decision (D7) | Not scored down. Emulation only. |
| 4. Security (isolation, revocation, CSRF, upload validation, no default transfer) | Partially | Agent isolation, scope enforcement, tag filter, revocation → 401, agent token rejected on REST, upload type validation. CSRF and cross-account isolation not exercised. |
| 5. Tests/builds/journeys/migrations on candidate | Not run by me | Judged the running build only. |
| Synology DS923+ performance/ACL/restore, real Telegram/Google/Microsoft/Dropbox | Out of scope by owner decision (D7) | — |

## Findings

No severe or high findings.

### Medium

**M1 — Moving a document to the Trash drops keyboard/screen-reader focus to `<body>` twice and gives no confirmation or undo.**
Repro (mobile or desktop, Italian):
1. Open a document with the keyboard (Enter on its title).
2. Activate **Sposta nel Cestino**. The button is replaced by the confirmation, and `document.activeElement` becomes `BODY` instead of **Conferma spostamento**.
3. Activate **Conferma spostamento**. The dialog closes, focus is `BODY` again (the opener card no longer exists), and the only announcement is the list count ("0 documenti trovati"). No "moved to Trash" message and no Undo.

Cause: `apps/web/src/DocumentPanel.tsx:851-856` toggles `confirmTrash` without moving focus. `moveToTrash()` at `:238-249` calls `onTrashed(); onClose();`, and `App.tsx:2144` only reloads lists. Agent revoke does this correctly: focus goes to "Sì, revoca" and a status is announced, so the two flows behave differently.
Evidence: `25-mobile-it-trashed.png`, s15 output.

**M2 — The mobile navigation drawer does not contain focus.**
Repro: on 390x844, tap **Apri o chiudi il menu**, then press Tab repeatedly. After **Esci**, focus moves to the dimmed page behind the scrim (**Aggiungi**, **Aggiorna**, search, filters, document cards) while the drawer stays open. Screen-reader swipe navigation reaches the covered content the same way. Esc does close the drawer and return focus to the menu button.
Cause: `apps/web/src/App.tsx:805-823` focuses the current link and handles Esc but adds no focus trap. `:1478-1479` sets `inert` only on the closed sidebar, never on `main` while the drawer is open.
Evidence: `08-mobile-it-menu.png`, s5 Tab trace.

**M3 — Error for a damaged file is misleading.**
Repro: upload a file named `x.pdf` that is not a valid PDF (mixed with a valid ODT). The result is "1 file su 2 non è stato aggiunto. x-bad.pdf: Usa un file PDF, JPEG, PNG, …". The user did choose a PDF; the message should say the file is damaged or unreadable. The same English source string is in `services/api/archive/messages_it.py:9`.
Evidence: s12 output.

**M4 — Reloading while offline loses the useful offline view.**
Repro: with uploads queued and the connection off, reload the PWA. Instead of the cached Library and the "2 file in attesa" banner seen before the reload, the screen shows only "Impossibile raggiungere Ripiano. Controlla la connessione e riprova." + **Riprova**. The queued files did survive and were sent after reconnecting, so no data was lost; the user just cannot see that they are pending.
Evidence: `21-mobile-it-offline-queue.png`, `22-mobile-it-after-reconnect.png`, s12.

### Low

- **L1 — Lists without list markup.** The agent activity feed (`AgentPanel.tsx:~291-300`, plain `<div>` rows) and the paper-copy history read as one run-on text in the accessibility tree; in the activity feed the next row's agent name runs into the previous row's outcome ("riuscito · 18 nov 2026, 17:44 R4J2 cloud …"). Use `<ul>/<li>` (or `<ol>` with `<time>`).
- **L2 — Reflow at 320 px.** On `/backups` the **Esegui backup ora** header button is cut off at the right edge (page scrollWidth 337 vs 320). `/paper` (328) and `/agents` (331) overflow slightly. At 390 px all pages fit. Evidence: `27-320px-overflow_backups.png`.
- **L3 — Small touch targets on Agents (mobile).** Permission checkboxes are 16x16 and radio-like inputs 13x16. The wrapping labels enlarge the hit area, but the visible control is under 24 px.
- **L4 — Filename search misses email documents.** The library card shows the original file name, but searching the uploaded file-name prefix found 4 of 6 uploads. The EML/MSG items, whose titles come from the subject, are not matched by file name.
- **L5 — Duplicates in the Inbox only offer "Tienili entrambi".** Discarding the duplicate requires opening it and going to Trash.
- **L6 — Wording inconsistency.** "Segnalata come mancante" and "Segnata come mancante" appear side by side in the paper-copy panel. The ASN field's accessible name includes its long hint ("Numero di archivio (ASN) Facoltativo · la tua numerazione progressiva; i codici a barre ASN lo compilano"), which is verbose for screen readers; prefer `aria-describedby`.
- **L7 — MCP tool errors are English only** ("Tool is not permitted for this agent"). Acceptable for agents; noted for completeness.

### Positive notes (for calibration)

The Italian translation is idiomatic and complete: dates (`18 nov 2026`, `gg/mm/aaaa`), plurals, Italian search aliases, and Italian server errors (257/264 covered). The keyboard model is unusually good (shortcuts dialog, `j/k`, `/`, focus return from dialogs). The physical-copy workflow (QR deep link, missing/found locking, history) is excellent. Agent scoping is strict and visible.

## Most serious finding

**M1:** The Trash flow loses focus to `<body>` at both steps and closes the dialog with no confirmation or undo. A keyboard or screen-reader user cannot tell what happened or where they are after a destructive action. (M2, the drawer without focus containment, is a close second.)
