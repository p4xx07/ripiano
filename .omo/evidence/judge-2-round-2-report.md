# Judge 2: round 2 report

- **Candidate SHA:** `f2b94168ff7af0bb914bb3f644eef7ee7490394a` (branch `codex/initial-implementation`)
- **Date:** 2026-11-18
- **Reviewer focus:** a user who works mainly on a phone, uses a keyboard and screen reader, and works in Italian. All five dimensions are still scored.
- **Stack:** http://localhost:18080 (running stack; I did not restart or rebuild it). Account `judge2` (archive owner/admin).
- **Browser:** Playwright `Version 1.64.1`, `Google Chrome 157.0.8103.79` (channel `chrome`, headless). Desktop context 1440x900. Mobile emulation 390x844 (`isMobile`, `hasTouch`, DPR 2), plus 320x640 and 360x640 reflow checks. Locale `it-IT` throughout, so the app followed the device language (Italian). Light and dark color schemes.
- **Artifacts:** `qa-artifacts/20261118-r2-judge-2/`: 39 screenshots plus `scripts.txt`, which holds every script verbatim. Token values are masked. The password is read from `judges.env` at runtime and never printed.

## Commands and scripts

All scripts are in `scripts.txt`. `lib.mjs` resolves `@playwright/test` from `apps/web` with `createRequire`.

```
cd apps/web && npx playwright --version
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version
node s1.mjs        # sign-in + home, IT, desktop+mobile, aria snapshots
node sweep.mjs mobile   # every nav screen: unnamed controls, unlabeled inputs, <44px targets, heading skips, h-scroll, English-text heuristic
node kb.mjs; node kb2.mjs  # skip link, ?, g+letter, /, J/K/Enter, dialog focus trap (120 tabs), Esc focus return, browser Back
node up1.mjs; node up2.mjs # mobile Add sheet; camera input, gallery input, file input (3 files); live-region log; processing time
node search.mjs    # OCR phrase, sender:, date:, tag:, Italian aliases, OR, exclusion, inflection
node doc.mjs; node sugg.mjs # one-screen correction: date/sender/tag, history; learned suggestion apply + undo
node phys.mjs; node phys2.mjs # sticker create, move to box, movement history, print label, ?sticker= lookup
node agents1.mjs; node agents2.mjs; node agents3.mjs # 2 grants (text+all docs / search-only+tag filter), MCP initialize/tools/list/tools/call, revoke -> 401, audit
node offline.mjs   # offline upload queue, reload while offline, reconnect auto-send
node errs.mjs      # invalid uploads + API errors with Accept-Language: it
node a11y2.mjs; node drawer.mjs; node reflow.mjs; node reflow2.mjs # live regions, aria-expanded, drawer focus, contrast heuristic, 320px reflow
node inbox.mjs; node inbox2.mjs # exception Inbox, keyboard "Tienili entrambi"
node texts.mjs; node backup.mjs # Overview/Backup/Sources/Trash text; manual backup run
esbuild bundle of src/locales/*.ts -> en/it key comparison (all 1,748 IT strings dumped)
```

## Fixture IDs used

`judge.png` (two copies with bytes appended so the hashes differ: one through the camera input, one through the gallery input), `three-pages.pdf` (copy with a trailing comment), `office-letter.docx`, `email-notice.eml`, and `office-open.odt` (offline queue). All of these went in as `r2j21010-*` copies. I also uploaded a made-up invalid `r2j21010-finto.pdf` and an `.eml` renamed to `.txt` to check upload validation. Documents in the account from the earlier `j2*-mwluqc5v` session served as duplicate targets and search background.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **7.5** | On mobile in Italian, I added files through the camera input (`capture=environment`), the gallery input, and the file picker (3 files at once). All 5 were Ready in about 12 s with no mandatory TODO screen. A phrase rule auto-tagged the `.eml` and the email date was used. Exact copies went to the exception-only Inbox, and "Tienili entrambi" works by keyboard. The learned suggestion ("Imposta mittente", with an explanation of why it appeared) saves with one tap, focus stays put, and a status message is announced. I corrected it back in the same dialog. The offline queue survived a reload and sent the file automatically after reconnect. Invalid files got a per-file Italian report (24). | Friction: no document preview in the edit dialog; on mobile nothing visible or announced tells you the upload finished; titles come from the file name. Not exercised: real camera, Telegram, watched folder, consume folder, IMAP, Android client. |
| Retrieval and physical filing | 20% | **7.5** | OCR phrase "RIPIANO JUDGE 9473" found both new images (snippet shown). `sender:"Comune di Esempio"`, `date:2026-11-10`, `date:2026-11`, `tag:Bollette`, `-tag:`, and `OR` all worked. On the physical side, I created a sticker, moved the copy into Scaffale/Scatola, checked the movement history, printed the label (QR encodes `PUBLIC_ORIGIN/?sticker=CODE`), and found the copy again with `/?sticker=R-…`. | Friction: no Italian stemming ("tassa rifiuto" finds 0, "rifiuti" finds 3); Italian field names (`mittente:`, `etichetta:`, `data:`) give 0 results; "Initial placement" appears in English. Not exercisable: printing on paper and scanning with a real phone camera; no in-app QR scanner exists in the PWA. |
| UX and accessibility | 20% | **6.0** | Good: skip link, `aria-current`, focus moves to the h1 on each view, the document dialog traps focus (120 Tabs, 0 escaped) and Esc returns focus to the row, labeled form controls, no unnamed buttons or images, no heading skips on 15 screens, Italian `lang`, complete IT catalog (no missing keys), dark mode. | Failures: browser/OS Back leaves the app; the closed mobile drawer stays focusable and readable by screen readers; the menu toggle has no `aria-expanded`, no Esc, and does not move focus; focus drops to `<body>` after creating or revoking an agent token; many touch targets are under 44 px; several English strings leak through. Not exercisable: installed iOS/Android PWA, Android client, real VoiceOver/TalkBack (I checked the accessibility tree and focus, not spoken output). |
| Reliability and recovery | 20% | **6.5** | Interrupted upload, emulated: an offline upload was queued, persisted across a page reload, and was delivered on reconnect. Manual backup: queued, then a completed checksum-verified snapshot in under 10 s. The upload batch reported a partial failure clearly. | The Backup list shows a raw `[Errno 13] Permission denied: '/backup/staging'` and an untranslated trigger "schedule". Not exercisable under the brief's rules: worker interruption, service restart, clean-stack restore, NAS/ACL. |
| Privacy and agent control | 15% | **8.0** | Grant A (search + OCR text, all docs) listed `search_documents,get_document_text`. Grant B (search only, tag filter) listed only `search_documents`. B's search for "9473" (outside its filter) returned `[]`; B's text and semantic calls were refused ("Tool is not permitted"). A revoke done by keyboard took effect immediately (HTTP 401 on the next call). The audit shows each grant, action, and outcome (riuscito/negato/non riuscito), and the warning about cloud agents and OCR text is clear. | Friction: audit entries don't name the document or query and can't be filtered; revoked grants pile up with no way to remove them; duplicate grant names are allowed; after creating a token the token card is off-screen and focus is lost. Not exercisable: a real cloud MCP client. |

**Weighted mean:** 0.25·7.5 + 0.20·7.5 + 0.20·6.0 + 0.20·6.5 + 0.15·8.0 = **7.08**

## Hard gates

| Gate | Status |
| --- | --- |
| 1. Every parity row has a working scenario or an accepted deviation | **Partially demonstrated.** I exercised upload/OCR/Office/email formats, search syntax, tags/senders/types, notes, history, physical copies, duplicates, agents/MCP, backups, and Trash/Inbox screens. I did not verify row by row: workflows, mail rules, cloud sources, versions/page edits, share links/bundles, or OIDC. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **Partially demonstrated.** Upload/OCR/search and backup creation passed. Fresh install and restore were not demonstrated (restarts and restores are not permitted on the shared stack). |
| 3. Installed iOS PWA, installed Android PWA, native Android with real-device capture and interrupted upload | **Not demonstrated** (needs owner hardware). Only emulation and an emulated offline queue. |
| 4. Security review (isolation, revocation, CSRF, upload validation, external input, no default content transfer) | **Partially demonstrated.** Agent scope/filter isolation, immediate revocation, and upload validation passed. CSRF and cross-account isolation were not probed in depth. Note: this judge stack serves the Django DEBUG 404 page (`/api/tokens` shows the URL list). The compose default is `RIPIANO_DEBUG=0`, so this is a stack configuration issue, not a candidate default. |
| 5. Unit/API tests, builds, browser journeys, migrations, deployment checks on the candidate | **Not demonstrated by me.** I did not run the test suites or builds. |

## Findings

### Severe
None.

### High

**H1. Back and Android back exit the app; no screen or dialog has a history entry.**
- Repro: open about:blank, sign in, open Agenti, then Cestino, then press browser Back. You land on `about:blank` (kb2.mjs output `back -> about:blank`).
- In an installed PWA on Android, the system back gesture closes Ripiano from any screen, including with an open document dialog that has unsaved edits.
- No screen can be bookmarked or shared; the URL stays `/` everywhere.
- Cause: views live only in React state (`App.tsx:607-609` `useState<"documents"|…>`), and the only history calls are `replaceState` (`App.tsx:596,604,632`).

**H2. The closed mobile navigation drawer stays focusable and readable by screen readers.**
- Repro at 390x844: sign in and press Tab twice. Focus lands on "Chiudi la navigazione" at x=-69, outside the viewport (drawer.mjs). The 15 nav buttons, two selects, and "Esci" are also in the Tab and VoiceOver swipe order while invisible.
- The toggle "Apri o chiudi il menu" has no `aria-expanded` or `aria-controls`.
- Opening the drawer leaves focus in `<main>`; Tab walks the hidden-behind content first (drawer tab sequence: `MAIN:Aggiorna > … > NAV:…`); Esc does not close the drawer.
- Cause: `App.tsx:1201` (`aside` only moved by CSS, no `inert`/`hidden`) and `App.tsx:1266-1270` (toggle button).
- Fails WCAG 2.4.3, 2.4.7, and 4.1.2.

### Medium

**M1. Focus is lost to `<body>` after creating an agent token and after confirming a revoke. The new token card appears off-screen with no announcement.**
- Repro: on mobile, go to Agenti, fill Nome, press "Crea token dell'agente". Result: `focus after create: BODY`, `token card in viewport: false`. Then press Revoca and "Sì, revoca": `focus after confirm: BODY`.
- A screen-reader user cannot tell that a one-time secret was shown.
- Cause: `AgentPanel.tsx:87-111` and `113-128`; the submit button is disabled while busy and nothing moves focus to `.agent-token-card` (`AgentPanel.tsx:163`).

**M2. Upload completion is neither announced nor visible on mobile.**
- The `role=status` region exists only while uploading (`App.tsx:1492-1496`). The live log showed only "Aggiunta 1 di 3…", with no completion message.
- On a 390 px screen the new document card sits below the hero, stats, saved searches, and search controls, about 1,600 px down (07-mobile-after-camera-upload.png). A blind or mobile user gets no confirmation that the file went in.

**M3. The edit dialog has no document preview.**
- When you correct date, sender, or tags in "one screen", you cannot see the document; the only option is "Apri il PDF ricercabile" in another tab. The dialog contains 0 `img/iframe/embed/canvas` elements (doc.mjs).
- On a phone this means switching tabs back and forth for every correction.

**M4. Search uses no Italian language processing.**
- `views.py:469-470,510-511` use `config="simple"`.
- Repro: "tassa rifiuti" finds 3 results, "tassa rifiuto" finds 0. In the same way, "bolletta" does not match "bollette".
- For an Italian archive this is a daily miss.

**M5. English and raw strings leak into the Italian UI.**
- Panoramica shows "No type" (`stats_views.py:47`).
- Backup shows trigger "schedule": the backend value is `schedule` but the IT map has the key `scheduled` (`locales/AppBackups.ts:11-14`).
- Backup shows the raw error `[Errno 13] Permission denied: '/backup/staging'` (`App.tsx:492`).
- Copy movement history shows "Initial placement", stored as a note (`physical_views.py:315`).
- The hard-coded message `“X” is connected. Use Preview to check the folder.` appears after a source OAuth return (`App.tsx:605`).
- Search snippets show the email header label "Subject".

**M6. Touch targets under 44 px on mobile** (sweep.mjs):
- tag delete 24x24 and share 32x32 (Etichette);
- "Sposta <tag>" 161x13;
- "Aggiungi frase di riconoscimento" 210x22;
- console links 13 px tall (Sorgenti);
- "Riferimento API" 16 px;
- password fields 183x24 (Sicurezza "Cambia password", Persone);
- agent "Revoca" 62x27;
- color input 34x29.

**M7. The keyboard-shortcut help names screens differently from the navigation.**
- Help says "g poi l — Vai a Archivio" and "g poi a — Vai a Cose da fare"; the nav says "Tutti i documenti" and "Da fare".
- "Archivio" is easily confused with the "Archivio cartaceo" screen, which has no shortcut.
- "Vai a Archivio" is ungrammatical (should be "Vai all'Archivio"), and "Enter" is not translated ("Invio").
- Cause: `locales/KeyboardHelp.ts:26-36`.

### Low
- **L1.** No Italian search field names. `mittente:`, `etichetta:`, and `data:` return 0 results, and the IT help only teaches `sender:`/`tag:`/`date:` (`search_syntax.py:22`).
- **L2.** Printable labels are served with `<html lang="en">` (`physical_views.py:264`, `metadata_views.py:497`).
- **L3.** At 320 px width the layout needs 337 px, so mobile browsers zoom out slightly.
- **L4.** Repeated identical button names ("Tienili entrambi" ×5, "Sposta") with no document context. Long field hints are folded into accessible names (for example "Numero di archivio (ASN) Facoltativo · la tua numerazione…") instead of `aria-describedby`.
- **L5.** In the mobile Add sheet the close button overlaps the heading's last letters (06-mobile-add-sheet-it.png). The search field shows a "/" key hint on touch devices.
- **L6.** Saving the document dialog closes it with no confirmation message. Agent audit rows are not a list and don't name the document or query.
- **L7.** Revoked agent grants cannot be removed, and duplicate grant names are allowed (I accidentally created two grants with the same name).
- **L8.** Stack configuration (not a code default): the judge stack runs with DEBUG, so unknown `/api/*` paths return Django's technical 404 page.

## Most serious finding
**H1:** there is no history navigation, so the Android/browser Back gesture exits Ripiano from any screen or open dialog. Together with **H2** (the hidden mobile drawer is still in focus and screen-reader order), this is what keeps the mobile, keyboard, and screen-reader experience from release quality.
