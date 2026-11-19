# Judge 2 — round 5 report

- Candidate SHA: `95e6f6d4d0893157ae63cb33541e6b5d53636dd7` (branch `codex/initial-implementation`), running stack at http://localhost:18080
- Date: 2026-11-18
- Account: `judge2` (admin). Persona: mobile-first, keyboard and screen-reader-minded, working in Italian.
- Browser: Playwright 1.64.1 (`npx playwright --version`), Chrome channel, Google Chrome 157.0.8103.79. Desktop 1440x900; mobile emulation 390x844 (isMobile, hasTouch, DPR 2); reflow check at 320x640. Locale `it-IT` (one run in `en-US` to test the language switch).
- Artifacts: `qa-artifacts/20261118-r5-judge-2/` (37 PNGs; agent tokens masked; no password anywhere).
- Independence: I did not read any judge-/round-/round3/parity-audit- evidence or other judges' qa-artifacts. `.omo/evidence/restore-drill-round5.md` did not exist by the time my run ended, so I did not use it.

## Commands and scripts

All scripts are in my scratch folder (outside the repo): `<scratchpad>/j2/` (lib.mjs, s1–s18.mjs). `node_modules` is a symlink to `apps/web/node_modules`. I ran each one with `node sN.mjs`. I used curl/HTTP only through Playwright `ctx.request`, because shell curl was blocked by the sandbox.

| Script | What it did |
| --- | --- |
| s1, s6 | Italian mobile sign-in, then every navigation screen: audits for unlabelled controls, missing alt, target size, horizontal scroll and leftover English |
| s2, s3 | Add dialog; gallery upload (judge.png); two files at once (three-pages.pdf + office-letter.docx); processing wait |
| s4 | Desktop keyboard-only sign-in, Tab order and focus styles, `/` shortcut, OCR phrase search |
| s5 | Document dialog: headings, focus trap (80 Tabs), Escape returns focus |
| s7, s8 | Sticker create → print label → move → history → lookup; QR URL (`/?sticker=`) while signed out, then after sign-in; 15 search queries (sender/date/tag/Italian field aliases/negation/sticker) |
| s9, s10 | Synthetic camera scan (derived input, see fixtures) → learned suggestions → dismiss / accept / correct in one screen |
| s11 | Wrong-password announcement; 320 px reflow on five screens; drawer keyboard/inert/Escape; WCAG contrast scan; dark mode |
| s12, s13 | Two agents (local: titles+OCR+tags, all documents; cloud: titles only, tag filter); MCP initialize/tools/list/tools/call; audit list; revoke; revoked token → 401 |
| s14, s15 | Upload with the connection reset mid-request → queued + "Riprova ora"; offline upload queue; queue persists after closing the page; unsupported file; `N` shortcut keyboard upload |
| s16, s17 | Overview counters/chart accessibility; manual backup to completion |
| s18 | Device-English → switch to Italiano → reload persistence; list semantics; selection mode; browser Back closes dialog; dark mode |

## Fixture IDs used

`judge.png`, `three-pages.pdf`, `office-letter.docx`, `office-open.odt`, `office-slides.pptx`, `office-sheet.xlsx` (copied under the unique prefix `r5j2mwmejq95-`). Earlier judge2 data from previous rounds (from `email-notice.eml` / `outlook-notice.msg`) was used for searches. Derived inputs that are not corpus files: `r5j2mwmejq95-bolletta.png`, a text image rendered by Playwright, used to trigger learned suggestions because every corpus file was already in the account as an exact duplicate; and `r5j2mwmejq95-note.txt`, an unsupported-type probe.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | Gallery, file-browser (2 files at once) and camera-input uploads land directly in the Library with "Aggiunto 1 documento" live notices. OCR was ready in about 15 s (03–07). No mandatory TODO screen: Inbox only holds duplicates/errors, and "Da fare" is empty unless chosen. A date was detected from the scan (14 mar 2026). Learned suggestions explain themselves ("Simile a … · in comune: acquedotto, zafferano…"), each has a 44 px dismiss button, and accepting one moves focus to the field and announces it. The correction (other sender + tag) is saved in the same dialog (26–27). Unsupported files get a clear Italian error. Friction: the dismissal is session-only (M2); 19–22 duplicate items in Inbox can only be resolved one at a time with "Tienili entrambi" (L1); the sender was not detected from the scan. | Telegram, watched folder (no mount access from the browser), real camera hardware, native Android |
| Retrieval and physical filing | 20% | 9.1 | The OCR phrase "9473" shows a text snippet. These all returned the right document: sender (`Acquedotto Zafferano`, `sender:`, Italian `mittente:`), date (`date:2026-03`, `data:2026-03`, "marzo 2026"), tag (`tag:`, `etichetta:`), accent-insensitive "perche", negation, `sticker:`. Sticker created → label (Italian, QR + code + location) → moved → history (2 entries) → lookup by lower-case code shows the current location (20–24). Opening the QR URL while signed out lands on the lookup result after sign-in (24). Friction: titles are cut to about 17 characters on mobile (M1); the Italian advanced-search help shows only English field names even though Italian aliases work (L2). | Camera QR scanning in the app (the app relies on the phone camera opening the URL); real printing |
| UX and accessibility | 20% | 9.0 | `lang` follows the UI language. Skip link. Every visible control has an accessible name (0 unlabelled on 15 screens). Visible 3 px focus ring. Dialog: aria-modal, focus starts on Close, focus never escaped in 80 Tabs, Escape returns focus to the title button, browser Back closes it. Drawer: aria-expanded/aria-controls, main is `inert` while open, Escape returns focus. No horizontal scroll at 390 or 320 px. Only one contrast failure (a decorative heading period, 2.51:1). Live regions for upload, queue, sticker move, suggestion and revoke. Wrong password announced ("Credenziali non valide"). Italian copy is complete and natural: no English leftovers found on 15 screens. Friction: M1; results are not a list (L3); "Ricerca avanzata" `<summary>` uses the browser default focus ring, not the 3 px ring (L4); "Data del documento: nessuno → …" gender agreement (L5); mixed date formats (L6). | Installed iOS/Android PWA, Android client, real VoiceOver/TalkBack (out of scope by owner decision) |
| Reliability and recovery | 20% | 9.0 | A connection reset mid-upload queued the file ("1 file è in attesa… Riprova ora") and the retry succeeded. Offline upload was queued and sent on reconnect. A file queued offline survived closing the tab and was uploaded by a new page. Manual backup went from queued to completed in about 9 s, with a cancel option while queued. No console errors apart from the intentional network failures. | Restarting the worker or services (forbidden on the shared stack); clean-stack restore (the round-5 drill file was not present) |
| Privacy and agent control | 15% | 9.3 | The UI defaults to the least scope (titles only) and has a cloud warning. Local agent tools: search_documents, get_document_text, list_tags, change_document_tags. Cloud agent: search_documents only. It returned no OCR-only hits ("9473", "Zafferano"), returned only documents tagged Utenze, its get_document_text was refused, and responses hold metadata only. Random-ID text read: "Document not found within this grant". Revoking asks for confirmation (focus goes to "Sì, revoca"); afterwards the revoked token gets 401 at once and the other agent keeps working. The audit list records each call with riuscito/negato/non riuscito and no document text. Friction: L7, L8. | Real cloud agent (Claude/ChatGPT connector) |

**Weighted mean: 0.25·9.0 + 0.20·9.1 + 0.20·9.0 + 0.20·9.0 + 0.15·9.3 = 9.07**

## Hard gates

| Gate | Status from my run |
| --- | --- |
| 1 Parity scenarios | Partly demonstrated for the rows I exercised: upload channels (web), OCR, search syntax, tags/senders/types, suggestions, duplicates, physical copies, agents/MCP, backup. I did not audit the full matrix. |
| 2 Install/upload/OCR/search/backup/restore | Upload/OCR/search/backup demonstrated. Clean-stack restore not demonstrated by me (`restore-drill-round5.md` absent during my run). |
| 3 Installed iOS/Android PWA, native Android, real devices | Out of scope by owner decision (D7) |
| 4 Security (isolation, revocation, CSRF, upload validation, no default content transfer) | Agent scope/filter isolation, revocation and upload type validation demonstrated. CSRF and cross-account isolation not probed. Semantic search is off by default; no provider calls. |
| 5 Tests/builds/journeys on candidate | Not run by me (judge-only run against the live build) |
| Real Telegram/Google/Microsoft/Dropbox accounts, DS923+ performance/ACL/restore | Out of scope by owner decision (D7) |

## Findings

No severe or high findings.

### Medium

- **M1 — Mobile result titles cut to about 17 characters.** Repro: 390x844, Library → rows show "r5j2mwmejq95-per…", "Avviso condominio …", "j2r4-179501993602…" while the metadata line wraps to three lines (03, 38). Documents with similar titles can't be told apart on a phone, and the title is the main retrieval cue. Cause: single-line ellipsis in the mobile rule, `apps/web/src/style.css:1328-1334` (HEAD: `white-space: nowrap; text-overflow: ellipsis; line-height: 44px`). Suggest allowing 2 lines (line-clamp) and keeping the 44 px minimum height.
- **M2 — "Non è giusto" (dismiss suggestion) is forgotten after the session and teaches nothing.** Repro: open a document with learned suggestions → click the dismiss (×) on "Aggiungi etichetta: Utenze…" → close the browser/new session → reopen: the same suggestion is back (seen across runs s10 #1 → #2). Cause: stored only in `sessionStorage`, per the code's own comment, `apps/web/src/DocumentPanel.tsx:35-50`. For "correct an uncertain suggestion" a rejected suggestion should stay rejected per document and ideally count as a negative example.

### Low

- L1 Inbox duplicates: the only action is "Tienili entrambi", one item at a time, with no bulk action and no "move this copy to Cestino" in place. The explanation ("Entrambi gli originali sono salvati") is cut off on mobile (12). `apps/web/src/InboxPanel.tsx:125`.
- L2 The Italian "Ricerca avanzata" help lists only `tag:`, `sender:`, `date:` and other English keys, although `mittente:`, `etichetta:` and `data:` work. `apps/web/src/locales/AppLibrary.ts:231` and nearby.
- L3 Library results are not in a `ul/li`/list role, so screen readers don't announce "list, N items" (titles are h3, so heading navigation works).
- L4 The `summary` "Ricerca avanzata" has the browser default 1 px auto outline; every other control has the 3 px ring (s4 Tab order).
- L5 History shows "Data del documento: nessuno → 14 mar 2026"; feminine agreement needs "nessuna", or use a neutral "—". `apps/web/src/locales/DocumentHistory.ts:83`.
- L6 Mixed date formats: Overview "18/11/2026, 18:39:00" and paper-copy history "18/11/2026" (`DocumentPanel.tsx:826`, `toLocaleDateString()` without the app language) vs "18 nov 2026" elsewhere. Backup snapshots show only the date plus a raw ID, so same-day snapshots can only be told apart by the ID.
- L7 An agent calling an ungranted tool (`semantic_search`) is logged as "non riuscito" with "La ricerca per significato è disattivata" instead of "negato / not permitted". The feature-off check runs before the scope check (`services/api/archive/semantic.py:95`).
- L8 The agent page lists every revoked agent and an unpaginated activity log (80+ rows) with no per-agent filter. The Semantic panel shows the technical text "L'immagine del database non ha l'estensione pgvector… pgvector/pgvector:pg17".
- L9 The login error does not set `aria-invalid` on the fields (the message is announced, though).
- L10 Overview "Code in background: 3 OCR" counts the whole stack's queue while "0 in elaborazione" is per user. They briefly disagreed during my run.

## Most serious finding

M1 — on a phone, document titles in the Library are cut to about 17 characters, so similar documents are hard to tell apart in the main retrieval view.
