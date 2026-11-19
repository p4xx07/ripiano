# Judge 2 — round 7 report

- **Candidate SHA:** 2e97ca193004cae30da90c067357f89478e135f9 (branch `codex/initial-implementation`), running stack at http://localhost:18080
- **Date:** 2026-11-19
- **Reviewer emphasis:** mobile-first, keyboard and screen-reader user working in Italian (all five dimensions scored)
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (`channel: "chrome"`), Node v26.8.1
- **Viewports:** desktop 1440x900; mobile emulation 390x844, `isMobile`, `hasTouch`, DPR 3; locale `it-IT` throughout (the app picked Italian from the device language; `<html lang="it">`)
- **Account:** judge2 (password read from the scratch `judges.env` by the scripts at runtime; it does not appear in any file or screenshot)
- **Artifacts:** `qa-artifacts/20261119-r7-judge-2/` (34 PNG screenshots; agent tokens masked in 19-*.png)

## Commands and scripts

Scripts were kept in my scratch folder outside the repository (`.../scratchpad/j2/`). Each one imports Playwright from `apps/web/node_modules/@playwright/test/index.mjs` and was run with `node <script>.mjs`.

| Script | What it did |
| --- | --- |
| `common.mjs` | Opens contexts and signs in. Helpers: focus reporter (`document.activeElement`), touch-target scan (<44 px), unnamed-control scan, English-word leak scan |
| `s1`/`s2` | Mobile Italian sign-in, Library ARIA snapshot, navigation drawer (`aria-expanded`, focus on open/Escape), Add dialog |
| `s3` | Mobile upload through each Add path: "Scegli dalle foto" (gallery input), "Scatta una foto" (camera input, `capture=environment`), "Sfoglia i file" (PDF). Live-region announcements recorded |
| `s4`/`s5` | Document panel on mobile: suggestions, unsaved-edit guard, new sender inline, tag, save, focus after each step |
| `s6`/`s7`/`s8` | Desktop keyboard-only: skip link, `/`, `?`, `j`/`k`, search operators (Italian and English aliases), focus trap and focus return |
| `s9`–`s12` | Physical archive: create a sticker, open the label, simulate a QR scan (`/?sticker=R-…`, the address the label QR holds per `physical_views.py:420`), move the copy, check history, reprint the label, scan again |
| `s13`–`s15`, `mcp.mjs`, `mcp2.mjs` | Agents: two grants created in the UI (wrong password first), MCP `initialize`/`tools/list`/`tools/call` over HTTP, filter and text-permission checks, audit list, revocation, 401 check |
| `s16` | Offline upload (context offline → file queued → offline reload → reconnect). Damaged and fake PDF in one batch |
| `s17` | Sweep of 12 pages on mobile: focus after navigation, horizontal scroll, unnamed controls, small targets, English leaks |
| `i18ncheck.mjs` | Static comparison of English and Italian strings in `apps/web/src/locales/*.ts` |
| `s18`/`s19` | Focus after server-rejected forms (password change, agent token, sign-in). Bulk selection with the keyboard |
| `s20`/`s20b`/`s21` | Session ends during an upload: (a) only `sessionid` removed, (b) all cookies removed |
| `s22`/`s23` | Inbox and OCR retry; desktop screenshots |

## Fixture IDs used

`judge.png` (unique-byte copies as r7j2-gallery.png and r7j2-camera.png), `three-pages.pdf` (r7j2-three.pdf, plus a 3000-byte truncation as r7j2-damaged.pdf), `office-letter.docx` (r7j2-offline.docx), `office-open.odt` (r7j2-expired*.odt). A 16-byte text file named r7j2-fake.pdf served as the invalid-upload probe. The unique copies only append trailing bytes, so the SHA-256 dedup does not collapse them into existing documents. Existing account documents (from `email-notice.eml` and `outlook-notice.msg`) were used only for searches.

## Scores

| Dimension | Weight | Score | Evidence (exercised) | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.2** | Gallery, camera-input, and PDF uploads on mobile were all "Pronto" in about 16 s, with no mandatory TODO screen (03–06). Focus moves to the new document card, and the live region announces "Aggiunto 1 documento" and the processing count. The camera upload got learned suggestions ("Aggiungi etichetta: Bollette…", "Imposta mittente…", with an explanation of why). Correcting in one panel worked: title, date, a new sender created inline (focus goes to the new-sender field, then back to the select), tag, then Save; the status announces "salvato" and focus returns to the card (07–09). The unsaved-edit guard works with Escape and focuses "Continua a modificare" (08). A mixed batch gives a precise Italian rejection for the fake PDF and accepts the rest (23). | Telegram (out of scope, D7). Watched folder (needs a host mount or restart, which the brief forbids). Real camera |
| Retrieval and physical filing | 20% | **9.3** | Search found the OCR phrase, `mittente:`/`sender:`, `data:`/`date:` (day and month), `etichetta:`/`tag:`, combined operators, and accent-free `citta` for "città". The empty state gives Italian syntax hints (10–11). Sticker R-BT5LH845 created with an announced status (14). The label is Italian HTML with `lang="it"` (15). The scan URL resolves the copy and its location (16). Moving the copy to "Cassetto R4J2" is announced with a reprint hint, and history lists both placements (17). The reprinted label shows the new location and no longer the old box, and a rescan shows the new location | Physical printing; scanning the QR with a real phone camera |
| UX and accessibility | 20% | **8.8** | Skip link is the first Tab stop. Drawer `aria-expanded`/`aria-controls` are correct; Escape returns focus to the toggle. Every dialog moves focus to "Chiudi", traps Tab (27 stops, no escape in 5 depths tested), and returns focus to the invoking card. Shortcuts `/`, `?`, `j`/`k`/Enter work, with an Italian help dialog (12). Page navigation focuses the h1 on all 13 pages. No unnamed controls, no horizontal scroll at 390 px, and no English strings on any visited page. Static locale check: 0 untranslated strings, with correct Italian plurals. Inline confirmation focuses "Sì, revoca". **Defects:** focus is dropped to `<body>` after server-rejected form submits (M1), focus is on `<body>` after the session-ended sign-in screen and after opening a scan URL (L2), and card icon links are 40x44 px (L3) | Real iOS/Android PWA, Android client, real VoiceOver/TalkBack (out of scope, D7). Screen-reader behaviour was inferred from the ARIA tree and live regions, not heard |
| Reliability and recovery | 20% | **9.0** | Offline: the file was queued in IndexedDB, and an offline reload showed the service-worker page "1 file è in attesa…". After reconnecting, the file was uploaded and reached Pronto (22). Session ended (sessionid gone) during an upload: the server answered 401, the file was kept, and it was uploaded after the same person signed in again (31). Damaged PDF: a clear Italian failure with steps, listed in the exception-only Inbox; "Riprova l'OCR" re-queues it with an announcement and keeps it in the Inbox when it fails again (32). The round-7 restore drill (`.omo/evidence/restore-drill-round7.md`) is credible and covers originals by checksum, tags, nested locations, and revoked grants. **Defect:** when the CSRF cookie is also gone, the queued file is dropped (M2) | Killing or restarting the worker and services, and running my own backup/restore (the shared stack must not be restarted). NAS restore (D7) |
| Privacy and agent control | 15% | **9.4** | Creating a grant needs the owner's password (a wrong one is refused). The two grants have different scopes and filters. `tools/list`: locale = search_documents, get_document_text, list_tags, change_document_tags; cloud = search_documents only. The cloud grant (filter "Bollette J2") does not see the untagged r7j2-three. Its `get_document_text` is refused ("Tool is not permitted"). Full-text probes (`9473`, `JUDGE`, OCR-only words) return nothing, so it cannot use search to infer document text. The audit list shows each call with riuscito/rifiutato and no document text. After revocation both tokens return HTTP 401 (`invalid_token`). The token is shown once, in a focused region, with the MCP URL (19–21) | Real cloud agents (Claude, Ollama); cross-account isolation against other judges' document IDs |

**Weighted mean (judge 2): 0.25·9.2 + 0.20·9.3 + 0.20·8.8 + 0.20·9.0 + 0.15·9.4 = 9.13**

## Hard gates

| Gate | Status from this review |
| --- | --- |
| 1. Feature parity | Partly demonstrated. Every capture, retrieval, physical-copy, agent, offline, and Inbox row I touched works. I did not audit every FEATURE_PARITY row |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Upload/OCR/search demonstrated live. Install, backup, and restore accepted from `.omo/evidence/restore-drill-round7.md` (same SHA; checksums, tags, nested locations, and revoked-grant 401 verified), which I find credible. I could not rerun it on the shared stack |
| 3. Installed iOS PWA, Android PWA, native Android on real devices | **Out of scope by owner decision (D7)**. Browser mobile emulation only |
| 3b. Synology DS923+ performance, ACLs, NAS restore; real Telegram/Google/Microsoft/Dropbox | **Out of scope by owner decision (D7)** |
| 4. Security (agent isolation, revocation, CSRF, upload validation, no default content transfer) | Demonstrated for agent scopes, filters, text permission, revocation, password-confirmed grant creation, and upload validation (fake PDF refused). The CSRF token is required on POST (403 without it, see M2). No cloud provider is contacted |
| 5. Tests, builds, journeys, migrations | Not run by me (scope: running-stack review) |

## Findings

### Severe
None.

### High
None.

### Medium

**M1. Keyboard and screen-reader focus is dropped to `<body>` when a server rejects a form submitted from its button.** Systemic: it affects at least the agent-token form and the password change.
- Repro A (agent): Agenti → "Collega un agente" → enter a name and a wrong password in "La tua password" → Tab to "Crea token dell'agente" → Enter. The alert "La password non è corretta" appears, but `document.activeElement` is `<body>`. The password field has no `aria-invalid` or `aria-describedby`.
- Repro B (password): Sicurezza → wrong "Password attuale", valid new password twice → focus "Cambia password" → Enter → focus is on `<body>`.
- When the form is submitted with Enter inside a field (sign-in, password change), focus stays in the field, so the cause is the button being disabled while `busy`. Nothing moves focus back on error.
- Cause: `apps/web/src/AgentPanel.tsx:111` `setBusy(true)` together with `:423` `disabled={busy || …}`. The catch at `:132` only calls `setError`. The same pattern is at `PasswordPanel.tsx:25/32/47`, and `TokensPanel.tsx:107`, `SecurityPanel.tsx:117-137`, and `PeoplePanel.tsx:116/142` follow it. Fix: on error, focus the offending field (with `aria-invalid` and `aria-describedby` pointing to the alert), or keep the button enabled and use `aria-disabled`.

**M2. A file added while the session has ended is silently dropped when the CSRF cookie is also gone.**
- Repro: signed in on mobile → remove all site cookies (as a browser "clear site data" or storage eviction does) → Aggiungi → Sfoglia i file → pick a file.
- The upload POST answers **403** (CSRF), and the app switches to the sign-in screen ("Sei stato disconnesso…"). After signing in, the file is neither in the Library nor in the waiting banner. With only `sessionid` gone, the POST answers 401 and the file resumes correctly.
- Cause: `apps/web/src/uploadQueue.ts:77` `isRetryable` treats 401 as retryable but not 403. `App.tsx` ~1613 sends 403 to `failures`, and that report is not on screen once the sign-in screen replaces the Library.
- I did not confirm whether the failure notice reappears after sign-in.

### Low

- **L1.** After the session ends, the sign-in screen does not say that a file is waiting. It shows only "Sei stato disconnesso. Accedi di nuovo per continuare." (`App.tsx:1387`). The file is kept and resumes, but the user is not told.
- **L2.** Focus lands on `<body>` in three places: on the session-ended sign-in screen, after the first sign-in, and when the app is opened from a sticker QR address (`/?sticker=…`). A screen-reader user is not taken to the result or the notice. In-app navigation does focus the h1, so this is limited to these entry points.
- **L3.** Card icon links ("Apri il PDF ricercabile di …", "Scarica …") are 40x44 px on mobile, and "Chiudi la navigazione" is 43x44. That passes WCAG 2.5.8 (24 px) but is below the 44 px the rest of the app uses.
- **L4.** The unsaved-changes guard uses `role="dialog"` rather than `alertdialog` and has no heading. It is announced as a generic dialog, although focus handling is correct.
- **L5.** The sticker-scan result offers only "Apri documento". Moving the copy you just scanned takes one more screen (open the document, scroll to Copie cartacee).
- **L6.** Italian style nits: "L'OCR non è riuscito a terminare: Il riconoscimento…" has a capital after the colon (Inbox). "Sei offline" (offline page) and "Sei offline o Ripiano non è raggiungibile" (banner) use different wording. Otherwise the Italian is natural and idiomatic throughout ("Tienilo al suo posto", plural-correct counts, Italian search operator names and hints).
- **L7.** The Agents "Attività recente" list is unbounded on mobile (dozens of entries before the "Collega un agente" form), so a phone user has to scroll a long way to reach the form.

## Most serious finding

**M1:** after a server-rejected form submitted from its button (wrong password when creating an agent token or changing the password), keyboard and screen-reader focus is dropped to `<body>`. The same busy-disabled button pattern is used across several forms. For a keyboard and screen-reader user in Italian, this is the main friction left in an otherwise very polished build.
