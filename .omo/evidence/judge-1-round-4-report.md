# Judge 1 — round 4 report

- Candidate SHA: `b57e14e6c529d7fdeb5b9b7ff6b023d28fe88a7b` (branch `codex/initial-implementation`); running stack at http://localhost:18080 (containers restarted about 13 minutes before this run started; I did not restart anything)
- Date: 2026-11-18 (run 17:30–18:05 Europe/Rome)
- Account: `judge1`. The password was read at runtime from judges.env and is not written in any file here.
- Browser: Playwright `Version 1.64.1` (`npx playwright --version` in apps/web), Google Chrome channel `157.0.8103.79`
- Profiles: desktop 1440x900 (en-US); mobile emulation 390x844 with `isMobile`, `hasTouch` and DSF 3 (en-US and it-IT); keyboard-only on desktop
- Emphasis: a first-time owner on desktop, then the key journeys again on mobile emulation
- Artifacts: `qa-artifacts/20261118-r4-judge-1/` (41 screenshots, `scripts/` holds every script I ran). The agent-token screenshot is masked.

## Commands and scripts

Every script imports `@playwright/test` from `apps/web/node_modules` and runs with `node <script>.mjs`. `lib.mjs` handles login, screenshots and Chrome launch.

| Script | Purpose |
| --- | --- |
| s1, s2 | Login, first look at the Library, Add dialog and its file inputs |
| s3 | "Take a photo" input with `judge.png`, then "Browse files" with `three-pages.pdf`, `outlook-notice.msg` and `office-open.odt`; wait until processed |
| s4, s5 | API list and document detail drawer |
| s6, s7 | Library search: OCR phrase, sender, tag, date, typo; Filters panel |
| s8 | Inbox, Needs action, Paper archive |
| s9, s10 | Filing suggestions on the new `.msg` document; one-tap accept; create a sticker in a box |
| s11 | Print the sticker label, move the copy, check its history, look up the sticker code on the Paper archive |
| s12, s13 | Agents page; create "R4J1b Local" (titles, OCR text, tags; all documents) and "R4J1b Cloud" (titles only; only Condominio) |
| mcp.mjs, mcp2, mcp3 | MCP Streamable HTTP: initialize, tools/list, search_documents, get_document_text, list_tags, change_document_tags; no-token and bad-token requests |
| s14, p3 | Revoke through the UI (with confirmation), check the audit list, retest MCP; revoke a token while its MCP session is open |
| m1, m2 | Mobile: login, overflow check, gallery upload, search, detail drawer, menu, sticker lookup; computed style of a clipped title |
| k1–k3 | Keyboard: skip link, `/`, Tab order, focus ring, focus trap in the drawer, Esc and focus return, `?` shortcut list |
| i1 | Italian on mobile: login, Library, Add, detail, Archivio cartaceo, Agenti, Backup; scan for leftover English strings |
| r1 | Mobile upload while offline, then back online |
| (docker cp) | `three-pages.pdf` copied as `r4j1-watched.pdf` into my own NAS-folder source `/sources/r2-judge1` in `ripiano-maintenance_worker-1` |
| r2 | Wait for the watched-folder import; Sources card |
| b1, b2 | Backups and Sources pages; "Try OCR again" on a failed document; "Back up now" |

Shell commands outside the scripts: `docker ps`; `docker exec … ls /sources` (read-only, on each container); `docker exec -u ripiano ripiano-worker-1 mkdir /sources/r2-judge1`, then `docker cp` and `rm` of that same file. That container has no sources volume mounted, so the copy went nowhere and I removed it. I then ran `docker cp` plus `chown` into `ripiano-maintenance_worker-1:/sources/r2-judge1/`.

## Fixture IDs used

`judge.png` (camera input on desktop, gallery input on mobile, offline upload as `r4j1-offline.png`), `three-pages.pdf` (browse files and watched folder as `r4j1-watched.pdf`), `outlook-notice.msg`, `office-open.odt`. I also used existing documents from my account's earlier sessions, which were built from `email-notice.eml` and the same fixtures.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | All of these reached Ready with no review step: the camera input, the gallery input on mobile, a batch of PDF, .msg and .odt files ("Added 3 documents", all processed in about 6 s), an offline mobile upload (queued with "1 file is waiting to upload…" and sent on reconnect), and a watched-folder file (imported about 50 s after the drop, moved to `processed/`). On the new `.msg` copy, sender and type suggestions appeared in the detail drawer with a reason ("shared: amministrazione, condominiale…"). One tap saved each one, with a live status message. The tag rule had already applied Condominio. Screens 03–06, 15–16, 33, 46–48. | Telegram (no real account; out of scope by D7). Real camera and Android scanner. |
| Retrieval and physical filing | 20% | 8.6 | Results with snippets for an OCR phrase ("9473" → "RIPIANO JUDGE 9473"), a sender ("Acquedotto Mirto"), a tag (`tag:Condominio`), dates (`date:2026-10`, "14/10/2026") and Italian words ("ottobre", "lampone"). The Filters panel has tag, paper copy, sender, type, custom detail and a date range. Sticker created in "Studio scaffale / Scatola 2026" (R-F9YNKLWW). The printed label carries a QR code, title, code and location. Moving the copy updated the Library row and the history; the lookup is case-insensitive (typed `r-f9ynklww`) on desktop and mobile. Friction: an ISO date or a misspelling in the main search finds nothing (M2). Screens 08–11, 17–19, 38. | A real QR scan with a camera (the lookup has no in-app scan button; I typed the code). Printing to paper. |
| UX and accessibility | 20% | 8.6 | Desktop: a skip link is the first Tab stop; `/` focuses search; the focus ring is 3 px plus a halo; the drawer traps focus (60 Tabs stayed inside); Esc returns focus to the row (3 of 3 controlled trials); `?` lists the shortcuts. No unlabeled buttons, inputs or images on the Library. Mobile: no horizontal overflow at 390 px, and touch targets are at least 32 px. Italian is complete on every screen I scanned (no English leftovers). Defects: long titles in the mobile list are cut mid-word with no ellipsis (M1); the drawer's close button overlaps the large title on mobile (L1); small copy issues (L2, L3). Screens 31, 35, 40–43. | Installed iOS and Android PWAs, the native Android client, a real screen reader (out of scope by D7 or not available). |
| Reliability and recovery | 20% | 8.8 | The offline upload queue and reconnect, "Try OCR again" on the damaged document (clear feedback; it fails again with the same plain message), and the offline banner with a Retry. "Back up now" produced a complete snapshot (`20261118T165437…`). The snapshot list also shows an earlier failure with a plain-language cause and a "Try again" button. The restore-drill evidence `.omo/evidence/restore-drill-round4.md` is for this exact SHA: an empty-stack restore with SHA-256 identical originals, tags, a nested location sticker lookup, the revoked grant still refused (401) and the active grant still working. It is consistent and specific, so I count it as credible. | Restarting or killing the worker or services (forbidden on the shared stack). Doing the restore myself. The NAS. |
| Privacy and agent control | 15% | 9.2 | Two grants: Local (search, text, tags; all documents) and Cloud (titles only; Condominio only). `tools/list`: Local gets search_documents, get_document_text, list_tags, change_document_tags; Cloud gets only search_documents. Cloud cannot find an OCR-only phrase ("9473", "riunione") or a Tasse document ("lampone"), and get_document_text returns "Tool is not permitted". Local cannot add the Condominio tag, which is another active agent's filter ("only a person can add or remove it"), but can add and remove Tasse. MCP returns 401 with no token or a wrong token. Revocation asks for confirmation ("Its token stops working at once"). The revoked token is refused on a new initialize (401), and also on a session opened before revocation (401). The audit lists every call with done, failed or denied status and stores no document text. Screens 20–22a. | Real cloud MCP clients. Semantic search (off). |

**Weighted mean (judge 1): 0.25·9.0 + 0.20·8.6 + 0.20·8.6 + 0.20·8.8 + 0.15·9.2 = 8.83**

## Hard gates

| Gate | Status | Notes |
| --- | --- | --- |
| 1. Parity: each row has a working scenario | Partly demonstrated | The rows I touched work: web, drag/browse, consume or NAS folder, mail files, Office, OCR search, tags, senders, types, filters, physical copies, agents. I did not verify the parity matrix row by row. |
| 2. Fresh install, upload/OCR/search, backup, clean restore | Demonstrated by evidence | Upload, OCR, search and backup I ran myself. Install and clean-stack restore come from `restore-drill-round4.md` (same SHA; credible). |
| 3. Real-device iOS and Android PWA, native Android | Out of scope by owner decision (D7) | Not scored down. |
| 4. Security review (isolation, revocation, CSRF, uploads, no default content to providers) | Partly demonstrated | Agent isolation, filter guard, revocation including open sessions, and token refusal: yes. CSRF and upload-validation review: not done by me. |
| 5. Tests, builds, journeys, migrations, deploy checks on the candidate | Not demonstrated by me | I did not run the suites, by design of this brief. |
| Synology DS923+ performance, ACLs, NAS restore; Telegram, Google, Microsoft, Dropbox real accounts | Out of scope by owner decision (D7) | — |

## Findings

### Severe
None.

### High
None.

### Medium

**M1 — On touch phones, long document titles are cut mid-word with no ellipsis.**
- Repro: mobile emulation (390x844, hasTouch), All documents. "Avviso condominio mirtillo" shows as "Avviso condominio mirt" (screens 31 and 33).
- Measured: the `button.document-title-button` is 170 px wide and sits inside an `h3` 149 px wide. The `h3` has `overflow:hidden; text-overflow:ellipsis`, but the button inside it is `display:inline-flex`, so the ellipsis never renders.
- Cause: `apps/web/src/style.css:1326-1329` (HEAD), the `@media (pointer: coarse)` rule `.document-title-button { display:inline-flex; align-items:center; }` combined with `.document-info h3` at `style.css:908-915`.
- Impact: similar Italian titles (for example "Bolletta acqua novembre/ottobre 2026") become hard to tell apart, and the clipped word looks like a bug.
- Suggested fix: make the button a block or flex child with `min-width:0; overflow:hidden; text-overflow:ellipsis`, or allow 2-line wrapping.

**M2 — The main search does not match a typed ISO date or a near-miss spelling.**
- Repro: All documents, search `2026-10-14` → "Nothing found yet", although two documents are dated Oct 14, 2026. Search `bolleta` → nothing.
- What does work: `date:2026-10` and `14/10/2026` (the latter only because that string appears in the OCR text).
- Impact: a first-time owner types a date the way the date picker shows it, or makes a typo, and is told nothing exists. The empty state does not suggest `date:` or the Filters date range.
- Suggested fix: treat a bare ISO or locale date as a document-date filter, or point to "Date from/to" in the empty state.

### Low

- **L1 — The detail drawer's close button overlaps the title on mobile.** On a phone, the 44 px close button sits on top of the last word of a long serif title ("mirtillo"). Open any document on mobile to see it (screen 35).
- **L2 — Pluralization error on the Sources card.** The NAS-folder card reads "Checked every 1 minutes." Open Sources → NAS folder card.
- **L3 — Error messages point owners to a log they cannot reach.** The OCR failure text in the Library and Inbox ends with "Details are in the worker log." A non-technical owner cannot open the worker log, so there is nothing actionable in the UI (`j1r3-damaged`).
- **L4 — The printed sticker shows a location that goes stale.** The label prints the current location ("Studio scaffale / Scatola 2026"). After a Move, the paper sticker shows the old place. The sticker code still resolves correctly, but the printed location is misleading unless the user reprints.
- **L5 — The agent audit list is hard to follow.** It shows "failed" and "denied" without the reason or the document, and has no paging (the list is long after many calls). Agents → Recent activity.
- **L6 — The paper-copy actions are ambiguous.** After a sticker exists, the second row "No location yet + Create sticker" (which creates another copy) sits right under the existing copy's Move control without a label such as "Add another paper copy" (screen 36).
- **L7 — Re-uploads add Inbox items.** Every re-upload of an identical file adds an "Exact copy · Keep both" item to the Inbox. The Inbox is not mandatory and the documents are still filed, but routine re-imports create review noise.

## Single most serious finding

M1: on touch phones, long titles in the document list are clipped mid-word with no ellipsis (`style.css:1326-1329` overrides the `h3` ellipsis from `style.css:908-915`). It is cosmetic, but it shows on the main screen of every phone session.
