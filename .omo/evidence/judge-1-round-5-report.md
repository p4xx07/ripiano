# Judge 1 — round 5 report

- Candidate SHA: `95e6f6d4d0893157ae63cb33541e6b5d53636dd7` (branch `codex/initial-implementation`), running stack at http://localhost:18080
- Date: 2026-11-18 (run 18:33–18:55 CET)
- Reviewer: Judge 1 (account `judge1`, Admin). Emphasis: first-time owner on desktop, then the key journeys again on mobile emulation.
- Browser: Playwright `Version 1.64.1` (`npx playwright --version`), Google Chrome channel `157.0.8103.79` (headless)
- Viewports: desktop 1440x900; mobile 390x844 (`isMobile`, `hasTouch`, DPR 2). Locales: `en-US`, and `it-IT` for the Italian pass.
- Artifacts: `qa-artifacts/20261118-r5-judge-1/` (39 screenshots plus one printed sticker label `label-R-95CQG2M3.html`; agent tokens are blurred in `d24`, and none appear in any file).
- Independence: I read no `judge-*`, `round-*`, `round3*`, or `parity-audit-*` evidence files and no other judges' qa-artifacts folders. `.omo/evidence/restore-drill-round5.md` did not exist when I finished, so I could not use it.

## Commands and scripts

The scripts are in my scratch folder (`…/scratchpad/j1/`), outside the repository. Each one imports Playwright by absolute path from `apps/web/node_modules` and runs as `cd apps/web && node <scratch>/<script>.mjs`.

| Script | What it did |
| --- | --- |
| `lib.mjs` | Signs in (reads the password from judges.env at runtime and never prints it), sets up desktop/mobile contexts, and takes screenshots |
| `s2`/`s3.mjs` | Add dialog; batch upload of 4 files through Browse files; polling until Ready |
| `docker exec -i -u ripiano ripiano-maintenance_worker-1 sh -c 'cat > /sources/r2-judge1/r5j1-watched-tagbarcode.pdf' < fixtures/tag-barcode-desktop.pdf` | Watched NAS-folder import (my own folder source) |
| `s5`–`s8.mjs` | Document panel; searches; filing a document by hand, then a suggestion on its twin plus a sender correction |
| `s9`/`s10.mjs`, `m2.mjs` | Sticker create, move, history, label print (GET `/api/copies/<id>/label`), sticker search, `/?sticker=` QR deep link, Paper archive Find, location contents |
| `s11`–`s13.mjs` | Keyboard only: Tab order, focus rings, `?`, `/`, `j`/`k`/Enter, dialog focus trap and focus return, `n` |
| `m1.mjs` | Mobile camera (`capture=environment` input) and gallery inputs; touch-target and horizontal-overflow check |
| `m3`/`m4.mjs` | Offline upload, reload while offline, recovery; one `connectionreset` abort of a POST and its automatic retry |
| `s14.mjs` | Truncated PDF (made from three-pages.pdf) plus a fake PDF: upload validation, OCR failure, Inbox |
| `m5.mjs`, `s25.mjs` | Italian on mobile and desktop; Inbox "Keep both" |
| `s15`–`s19.mjs`, `mcp.mjs` | Two agents created in the UI; MCP `initialize`, `tools/list`, `tools/call` over HTTP; denied calls; revoke, then 401 |
| `s20`/`s21.mjs` | Backups: Back up now, then the new snapshot; Overview and background jobs |
| `s22.mjs` | CSRF (PATCH without token, same origin and foreign origin), anonymous API access, 404 |
| `m6`/`m7.mjs` | Mobile filing with touch; Move to Trash, confirm, Undo offered, Trash, Restore |
| `s23`/`s24.mjs` | Sidebar clipping measurement at 1440x900 |

## Fixture IDs used

`three-pages.pdf` (uploaded as r5j1-three-pages.pdf; a truncated copy as r5j1-damaged.pdf), `office-letter.docx` (r5j1-letter), `email-notice.eml` (r5j1-notice), `office-slides.pptx` (r5j1-slides), `judge.png` (r5j1-camera through the camera input, r5j1-gallery through the gallery input), `tag-barcode-desktop.pdf` (watched folder), `asn-batch-mobile.pdf` (offline queue; it was split into 2 documents), `office-open.odt` (aborted upload, r5j1-aborted2). One synthetic non-PDF named r5j1-fake.pdf was used to test rejection.

## Scores

| Dimension | Weight | Score | Evidence (what I exercised) | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.0** | All 4 batch files (PDF, DOCX, EML, PPTX) were Ready in about 13 s. The EML got its title from the subject, its date detected, and a tag from a rule. The camera input (`capture=environment`) and the gallery input both worked on mobile. The watched NAS-folder file was imported within about 2 min and marked "from NAS folder". Everything went straight to the Library; Inbox shows only failures and exact copies. Correcting a suggestion took one screen: on r5j1-gallery, "Suggested from your documents" offered tag, sender, and type with an explanation. I accepted the tag and type, overrode the sender with a different one, and saved (d12/d13). A fake PDF was refused with a clear per-file message. | Telegram (real bot), native Android scanner, installed PWA camera: out of scope by owner decision |
| Retrieval and physical filing | 20% | **9.0** | OCR phrase (`9473`, `lampone`, `fattura luce ottobre`), `sender:"Energia Girasole"`, `date:2026-11-01..2026-11-12`, and `tag:Tasse` all worked, with snippets. Italian stemming worked ("bollette" found "Bolletta"). Sticker R-95CQG2M3: created in Scatola 2026, moved to Armadio ingresso with a confirmation and a history entry. The label printed as a 70x40 mm page with a QR code, title, code, and path. Searching the sticker code in the Library found the document. Paper archive Find accepted a lowercase code. The QR deep link `/?sticker=` opens the copy card. Location contents list nested copies. | Physical printing and a camera scan of the printed label (simulated by opening the QR URL) |
| UX and accessibility | 20% | **8.6** | Skip link, visible 3 px focus rings, a logical Tab order, dialog focus trap (0 escapes in 80 Tabs) with focus returned to the row, and shortcuts `?`, `/`, `n`, `g`+letter, `j`/`k`/Enter. Italian covered every screen I visited, with no English left over (shortcuts dialog and document panel included). Mobile had no horizontal overflow, touch targets of at least 40x44, a clear Add sheet, and an inline Trash confirmation with Undo. Several friction points remain (findings M1, M2, L1–L4). | Screen reader (VoiceOver/TalkBack) by ear; installed iOS/Android PWA and Android client: out of scope |
| Reliability and recovery | 20% | **8.9** | Offline upload was queued with a clear banner, survived a reload while offline, and was sent on reconnect. A POST aborted with `connectionreset` was retried automatically (after about 60 s; see M3). The damaged PDF gave a plain-language OCR failure in the Library, Inbox, and Overview, with Retry. Trash, Undo, and Restore worked. Back up now produced a verified "complete" snapshot in 9 s. CSRF-less PATCH returned 403; anonymous document, original, search, and label requests returned 401. | Worker/service restart and an empty-stack restore (the shared stack must not be restarted; `restore-drill-round5.md` was not present at report time) |
| Privacy and agent control | 15% | **9.2** | Created "R5J1 Local" (find, text, tags; all documents) and "R5J1 Cloud" (find only; only Utenze). The token is shown once, with a copy warning and the MCP URL. `tools/list` returned 4 tools vs 1. The cloud agent's search found only Utenze documents and did **not** match OCR-only words (`9473`, `RIPIANO JUDGE`), so text cannot leak through search. Its `get_document_text` and `semantic_search` were denied, and each denial appears in Recent activity as "denied". The local agent read text and changed tags, which was audited. Revoking needs a "Yes, revoke" confirmation; afterwards `initialize` and `tools/list` return 401 while the other agent keeps working. | Real cloud MCP client (Claude Desktop etc.) |

**Weighted mean: 0.25·9.0 + 0.20·9.0 + 0.20·8.6 + 0.20·8.9 + 0.15·9.2 = 8.93**

## Hard gates

| Gate | Demonstrated by me? | Notes |
| --- | --- | --- |
| 1. Every parity capability has a working scenario or accepted deviation | Partially | I sampled upload/consume-folder/formats, OCR/reprocess, search syntax, tags/senders/types/dates, suggestions, duplicates, trash/restore, backups, MCP agents, and Italian. I did not verify the matrix row by row. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Partially | Upload, OCR, search, and backup (snapshot created and verified) passed on the shared stack. I could not run a fresh install or restore, and `restore-drill-round5.md` did not exist when I finished, so restore is **not demonstrated** for this round. |
| 3. Installed iOS/Android PWA and native Android on real devices | **Out of scope by owner decision (D7)** | Not scored down |
| 4. Security review (isolation, revocation, CSRF, upload validation, no default content transfer) | Partially | Agent scope and filter isolation, the absence of an OCR-text oracle for the find-only agent, immediate revocation (401), CSRF 403, anonymous 401, fake-PDF refusal. Semantic search is off by default. I did not probe cross-account access with another judge's IDs. |
| 5. Unit/API tests, builds, browser journeys, migrations, deployment checks on candidate | Not demonstrated by me | I did not run test suites or builds, because they would write into the repository. |
| Synology DS923+ performance, ACLs, and NAS restore; real Telegram/Google/Microsoft/Dropbox accounts | **Out of scope by owner decision (D7)** | — |

## Findings

No severe or high findings.

### Medium

**M1 — Escape does not leave the Library search field, so `j`/`k` row navigation cannot be reached after a `/` search.**
Repro (desktop): press `/`, type `r5j1`, press Escape twice, then `j`. Escape neither blurs nor clears the field, and `j` is typed into the query (`r5j1j`). The only route to the results is about 6 Tabs. The global handler correctly ignores keys typed in inputs (`apps/web/src/App.tsx:895-896`), but the search input has no Escape handling to hand focus back. The shortcuts sheet advertises `/` and `j`/`k` as one flow.

**M2 — On a standard 1440x900 desktop, the sidebar clips the Appearance selector and hides the Language selector behind the user footer.**
Repro: sign in at 1440x900 and look at the bottom of the sidebar (`d33-sidebar-bottom.png`). The Appearance `<select>` is cut off. The Language `<select>` sits at y=873–917, and at that point `elementFromPoint` hits the footer ("judge1 / Sign out"). The sidebar scrolls internally (`apps/web/src/style.css:195-202`, `.sidebar-scroll`), but nothing shows that it does. A first-time owner looking for Italian will not find the switch on this screen.

**M3 — After a transient upload failure while the device is online, the file waits up to 60 s, the message blames the connection, and there is no "Send now".**
Repro (mobile): abort one `POST /api/documents` with `connectionreset` (`m4.mjs`). The banner reads "1 file is waiting to upload. Ripiano sends it when the connection is back." for about 55 s. No `online` event fires, so the retry waits for the 60 s interval (`apps/web/src/App.tsx:1441-1448`, `setInterval(retry, 60000)`). Nothing is lost, but the user cannot retry by hand, and the message is misleading when the network is fine.

### Low

- **L1 — The Paper archive says "Scan a QR code", but the PWA has no in-app scanner.** The card shows a scan icon (`apps/web/src/PhysicalPanel.tsx:246-262`), but only a text field and Find. A scan works only through the OS camera opening the `/?sticker=` URL, which in an installed iOS PWA usually opens Safari instead of the app. (This depends on a device, so I did not score it down beyond Low.)
- **L2 — Mobile Library rows are very tall (about 280–330 CSS px each).** The title sits on its own line above the icon and leaves a blank gutter, and titles are cut short ("Avviso TARI 2026 la…") despite free width. Only about 2.5 documents are visible on the first screen (`m01-library.png`, `m15-after-save.png`). On desktop, the hero, stat cards, and saved-search band push the list mostly below the fold (`d05-batch-ready.png`).
- **L3 — The same action has three names:** "Retry OCR" (Library row and Overview), "Try OCR again" (Inbox), and "Run OCR again" (document panel).
- **L4 — Revoked agents can never be removed.** The Agents screen lists every revoked agent (17 here) above the create form, and the activity log has no filter.
- **L5 — Email snippets show raw header text.** Search snippets for `.eml` documents start with "…+0100 Subject Avviso TARI…".
- **L6 — Paper-copy history shows only the date.** Each entry has the date but no time or actor ("11/18/2026 · Studio scaffale / Armadio ingresso").
- **L7 — An Inbox exact-copy item offers only "Keep both".** To discard the extra copy you must open it and use Move to Trash (two more steps).
- **L8 — The MCP `change_document_tags` tool rejects tag names** with "Invalid or conflicting tag IDs", so an agent first has to call `list_tags`. This is agent ergonomics, not a security problem.

## Most serious finding

**M2/M1 together: keyboard and desktop discoverability.** The Language switch is hidden behind the sidebar footer on a 1440x900 desktop, and keyboard users cannot get from search to `j`/`k` navigation with Escape. Neither loses data; both are friction a first-time owner hits in the first minutes. Taken alone, the most impactful defect is **M2**.

## Data I created (for cleanup)

Documents titled `r5j1-*` (plus "Avviso TARI 2026 lampone" from r5j1-notice.eml, and "r5j1-offline (1/2)" and "(2/2)"), sender "R5J1 Giudice Srl", sticker R-95CQG2M3, agents "R5J1 Local" (revoked) and "R5J1 Cloud" (active, expires 2026-11-20), and one manual backup snapshot `20261118T174824051578Z-e5d814e8`. I changed nothing owned by other accounts.
