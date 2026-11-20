# Judge 1 — round 11 report

- Candidate: `1c823549b93d3d9f8a65866d2e2d26e192e1df5e` (branch `codex/initial-implementation`; HEAD `5925b9a` adds evidence files only). Running build: my own stack `ripiano-j1`, http://localhost:18101, built from the candidate and empty at start.
- Date: 2026-11-20 (09:30–10:15 CET).
- Browser: Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (channel `chrome`, headless). Desktop 1440x900; mobile emulation 390x844 `isMobile`, `hasTouch`, DSF 3. Languages en-GB and it-IT (plus the machine's device language, which is Italian).
- Accessibility: no screen reader installed; Playwright `locator.ariaSnapshot()` was used as the stand-in.
- Artifacts: `qa-artifacts/20261120-r11-judge-1/` (28 screenshots; no token values in any of them). Scripts, passwords, tokens and state files stayed in my scratch folder `…/scratchpad/j1r11/`, never in the repository.
- Fixture IDs used (all from `apps/web/e2e/fixtures/`, which match `corpus.sha256`): `three-pages.pdf`, `office-letter.docx`, `email-notice.eml`, `office-legacy.doc`, `office-open.odt`, `office-sheet.xlsx`, `asn-batch-desktop.pdf`, `asn-batch-mobile.pdf`, `barcode-batch-desktop.pdf`, `barcode-batch-mobile.pdf`, `tag-barcode-desktop.pdf`, `tag-barcode-mobile.pdf`, `judge.png`, `office-slides.pptx`, `outlook-notice.msg` (all 15). For edge tests I also used two files I made in scratch: `notes.txt` and `fake.pdf` (random bytes).

## Commands and scripts run

All scripts are Node ESM files in my scratch folder. I ran them from `apps/web` with `node <script>`, which loads `@playwright/test` through `createRequire`.
- `02-setup.mjs`: first-run setup through the UI (setup key read from the env file; owner password generated with `openssl rand` and kept only in scratch).
- `04-upload-batch.mjs`: desktop "Browse files" batch upload. `08-mobile-upload.mjs`: mobile "Take a photo" (`capture=environment`), "Choose from photos", and "Browse files".
- Watched folder: `docker compose -p ripiano-j1 --env-file …/j1/stack.env exec -T maintenance_worker sh -c 'cat > /consume/…'` with `office-slides.pptx` (in a subfolder) and `outlook-notice.msg`.
- `07-file.mjs`: manual filing in the document dialog. `09-suggest.mjs` and `10-correct.mjs`: suggestions, and correcting them in one screen on mobile.
- `12-search.mjs`: 22 Library queries. `14-paper.mjs`, `15-label-move.mjs`, `16-move.mjs`, `17-label2.mjs`, `18-camscan.mjs`: locations, sticker, label print, move, reprint, then the camera scan. For the scan, the reprinted label was turned into a fake camera feed with `ffmpeg … label2.y4m` and Chrome's `--use-file-for-fake-video-capture`, and the in-app "Scan with camera" read it.
- `19-agents.mjs`, `mcp.mjs` (MCP Streamable HTTP client), `20-revoke.mjs`, `34-revokeB.mjs`: two agents, their tool lists, tool calls, the audit log, and revocation. `21-person.mjs`, `22-workflow.mjs`, `27-share.mjs`: a family account, the D12 agent-started workflow hold-back, and document sharing.
- `23-keyboard.mjs`, `24-focus-return.mjs`, `11-tour.mjs` (every screen, desktop in English and mobile in Italian, with console errors and horizontal overflow recorded), `31-italian.mjs`, `29-paths.mjs`, `32-overlap.mjs`, `33-font.mjs`, `30-edge.mjs` (mixed-validity batch and edit conflict).
- Reliability:
  - `docker compose -p ripiano-j1 … kill worker` mid-split, then `start worker`.
  - `stop api` during a browser upload (`26-offline-upload.mjs` phases A and B, with a persistent browser profile and a page reload), then `start api`.
  - `stop broker` / `start broker`, and `restart db`.
  - `28-backup.mjs` (Back up now) twice, the second with the worker killed mid-split.
  - Then the drill from docs/BACKUP_RESTORE.md: `down -v` → `up -d db broker api` → `stop web worker maintenance_worker scheduler mcp api` → `run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261120T090740167388Z-99af7a87 --yes` → `up -d`. I compared the state before and after with `state.mjs`.
- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q -p no:cacheprovider` → `438 passed, 17 skipped in 76.28s`.
- Not exercised because permission was denied: plain `curl` to the stack. I made the same HTTP calls with Playwright's `request` context instead, which the brief also allows.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.3** | **Capture:** desktop batch of 6 mixed formats; mobile camera input (`accept=image/*`, `capture=environment`); gallery (multiple); mobile PDF; watched folder (subfolder plus root, imported within about 2 min and removed). Every file became `ready` without a TODO screen. The source is shown ("from NAS folder" / Overview "Watched folder 2").<br>**Suggestions:** after I filed 3 documents, a similar scan (`barcode-batch-mobile.pdf`) offered sender, type and tag, each with the example document and the shared words. In one mobile screen I accepted the sender (my unsaved title draft was kept), rejected the tag (×), chose a different type, added another tag, and pressed Save (02/03).<br>**Exceptions:** duplicates went to an exception-only Inbox (20). A mixed batch named each rejected file and its reason (16). | Real Telegram bot (out of scope by owner decision). Native Android scanner and installed PWA (out of scope). Email intake: no GreenMail in this stack. |
| Retrieval and physical filing | 20% | **9.4** | **Search:** OCR phrase (`first otter`, `otter`); sender (`sender:"Quokka Society"`, `mittente:"Comune di Esempio"`); dates (`date:2026-10`, `data:2026-10..2026-11`, `added:2026-11`); tag, `-tag:`, `OR`; ASN (`asn:900011`, `ASN00900011`, `900012`); Italian stemming (`rifiuto` finds `rifiuti`); text from Office, .eml and .msg. All correct; `quoka`/`ottobre` correctly found nothing.<br>**Paper:** nested location; sticker; lookup by a lower-case code; move with history and a "print it again" hint; reprinted label; then a real in-app camera QR scan of the reprinted label found the copy at the new place (05–08, 25). | Real phone camera (out of scope). |
| UX and accessibility | 20% | **8.9** | **Navigation:** every screen loads with 0 console errors and no horizontal scroll, on desktop in English and on mobile in Italian. Italian has no untranslated strings on 13 screens or in the document dialog.<br>**Keyboard:** skip link, `/`, Esc→J/K/Enter, `?`, `g`+letter, `n`; dialogs trap focus; Back closes the dialog; visible 3px focus rings. Mobile Library has no target under 44px. Edit-conflict merge with **Use my value** (17).<br>**Defects:** the Storage paths form is unstyled and has no visible labels; focus is not reliably returned to the row that opened the dialog; small typographic inconsistencies (see Findings). | Installed iOS/Android PWA and the Android client (out of scope). No real screen reader (I used the aria snapshot). |
| Reliability and recovery | 20% | **9.4** | **Worker killed mid-split:** the UI says "taking longer than usual…"; after `start worker` it was ready in 15 s, with no duplicate parts.<br>**API stopped during a browser upload:** the file was kept on the device ("1 file is waiting…"), survived a reload with the beforeunload prompt, and was sent exactly once by itself after the api returned (12, 13, 24).<br>**Broker stopped:** the upload was still accepted (`/healthz` 503) and processed within 30 s of the broker returning.<br>**DB restart:** api and MCP work on the next request.<br>**Backup and restore:** Back up now announced the result; a backup taken with the worker killed mid-split was restored with `down -v` into an empty stack. Afterwards: 23/23 documents with identical IDs and original SHA-256; tags, nested locations, the paper copy at its moved place, people, the workflow, Anna's share, and grant states all kept (revoked → 401, active → 200). The interrupted split finished in about 76 s without duplicates.<br>**Minus:** nothing tells the owner when the OCR worker container is not running. | Synology DS923+ restore and performance (out of scope). Killing the api mid-transfer of a large file (the fixtures are too small to time it; I covered it with api-down instead). |
| Privacy and agent control | 15% | **9.5** | **Agent A** ("Cloud assistant": titles only, all documents): `tools/list` = `search_documents` only. A search for OCR-only words (`otter`, `rifiuti 120 euro`) returned nothing, so the text cannot be probed through search. `get_document_text` → "Tool is not permitted".<br>**Agent B** (all scopes, Harbour only): sees only Harbour documents; reading text outside the filter → "Document not found within this grant".<br>**Audit log** lists done and refused calls without document text (09). Revocation answers 401 at once, and still does after the restore.<br>**D12:** an agent's tag change that met an owner workflow sharing with Anna was recorded as "skipped sharing (an agent made the change…)"; Anna saw nothing. Family-account isolation: Anna sees 0 owner documents until one is shared. | Real cloud MCP clients and Ollama semantic search (not configured; not a defect). |

**Weighted mean:** 0.25·9.3 + 0.20·9.4 + 0.20·8.9 + 0.20·9.4 + 0.15·9.5 = **9.29**

## Hard gates

| Gate | Status |
| --- | --- |
| 1 Parity scenarios | **Partly demonstrated.** I exercised the upload, consume-folder, barcode/ASN/split, Office, email, OCR, search syntax, tags, senders, types, dates, suggestions, duplicates, history, notes, versions, workflows, users, sharing, agents, Overview, jobs, backup and i18n rows in the running app. I did not verify every parity row (mail rules, cloud sources, PDF page editing, share links, custom fields and others were not exercised in this run), so I cannot certify gate 1 in full. |
| 2 Install / upload / OCR / search / backup / clean restore | **Pass, demonstrated by me.** Fresh install through the setup key, then upload, OCR and search, then backup with the worker killed, then `down -v` and a restore. Originals, tags, locations and revoked grants were checked (see Reliability). The separate drill `.omo/evidence/restore-drill-round11.md` is consistent with this. |
| 3 Installed iOS/Android PWA, native Android | Out of scope by owner decision (D7). |
| 4 Security review | **Partly demonstrated.** Agent isolation, scopes, filters, revocation, no text without text scope, account isolation, the upload validation boundary (`.txt`, fake PDF), and D12 were checked. CSRF and token-auth internals were not reviewed in depth. No content goes to model providers (semantic search is off and there is no provider configuration). |
| 5 Tests and builds | **Credible.** I re-ran the API suite: `438 passed, 17 skipped`, matching `.omo/evidence/round11-verification.md`. The web build and e2e run were not re-run, as the brief instructs; the recorded commands and result lines are plausible and consistent with the running build. |
| DS923+ performance, ACLs, NAS restore; real Telegram/cloud accounts | Out of scope by owner decision (D7). |

## Findings

No severe or high findings.

### Medium

**M1. The Storage paths form is unstyled and has no visible labels.**
- Repro: Tags & filing → scroll to **Storage paths**, on mobile or desktop.
- What happens: the two inputs use browser-default inset borders and square corners (border-radius 0, font 16px), while every other field on the page uses the app field style (8px radius). They have no visible label, only `aria-label`. The name field relies on a placeholder ("e.g. By sender"). The template field is prefilled with `{correspondent}/{year}` and has nothing on screen saying what it is. The heading also uses a different font from its sibling cards.
- Screenshots: `15-storage-paths-mobile.png` and `22-tags-mobile-italian.png`.
- Cause: `apps/web/src/StoragePathsPanel.tsx:68-70` uses bare `<input aria-label=…>` without the `Field` wrapper or input class that the rest of the forms use (e.g. `DocumentPanel.tsx:1189`).
- Impact: a non-technical user cannot tell what the second box is for, and it fails WCAG 3.3.2 (visible labels).

### Low

**L1. Focus does not reliably return to the row that opened the document dialog.**
- Repro: Library → press `j` twice → focus the "three-pages" row → Enter → press Close.
- What happens: focus lands on the row highlighted with J/K (`asn-batch-mobile (1/2)`), not on "three-pages". In another run (skip link → search → Esc → J/K → Enter → Esc), focus went to `<main>`. Two other runs returned focus correctly.
- Why it matters: USER_GUIDE says dialogs "return it afterwards".

**L2. Nothing warns the owner when the OCR worker is not running.**
- Repro: `docker compose -p ripiano-j1 kill worker` while a scan is processing.
- What happens: Overview says the document "was interrupted and will be tried again by itself" (`11-overview-worker-down.png`), but with no worker nothing ever runs. `/healthz` checks only the database and broker. The only hint is "Background queues: 9 OCR" for 3 waiting documents, and that number does not match.
- Mitigating: Compose restarts crashed containers. I killed it by hand, which Docker does not restart.

**L3. Overview counts disagree.**
- What happens: the tile says "2 being processed" while Background jobs lists 3 waiting, because the hidden split source is counted in one and not the other.
- Seen while the worker was down.

**L4. The mobile document dialog's close button overlaps the title.**
- What happens: the close button (y 20–64) overlaps the heading box (y 60) by 4px. When focused, its ring covers the end of long titles such as "(1/2)".
- Screenshots: `19-mobile-title-under-close.png` and `02-suggestions-mobile.png`.

**L5. Some empty-state paragraphs use an unstyled 16px `<p>`, larger than the surrounding card text.**
- Examples: Overview "Nothing is waiting or failed." (`OverviewPanel.tsx:108`) and the dialog's "No tags yet…" text.

**L6. Search result snippets do not highlight the matched term.**
- Example: `04-search-1.png` shows "Document text: Page 1 first otter…" with no mark on "otter".

**L7. Small inconsistencies.**
- People shows "last signed in 20/11/2026"; other screens use "20 Nov 2026".
- After a waiting upload is finally sent on reconnect, the Library shows the new row but no "Added 1 document" confirmation.

**L8. Printed copy labels include the location, so a moved copy's sticker goes stale.**
- Mitigated: the move message says "If its sticker shows the old location, print it again", and the QR still resolves correctly.

### Positive confirmations (round-10 fixes)
- A backup taken with the worker killed completes; the interrupted document recovers after restore without duplicate parts.
- An upload is kept on the device during an api outage and sent once.
- Agent-started workflows hold back sharing.
- The edit-conflict merge works.
- Suggestions ignore words that come from the file name (the shared words listed were text words only).

## Most serious finding

**M1:** the Storage paths form on Tags & filing is unstyled and has no visible labels (`StoragePathsPanel.tsx:68-70`), so its purpose is unclear and it fails WCAG 3.3.2. Nothing severe or high was found. The reliability and privacy journeys passed end to end, including my own `down -v` restore.

## Cleanup
- Both agent grants I created are revoked (both answer MCP 401).
- The family account `anna` and the workflow "Share tax papers with Anna" remain in my stack.
- The stack was left running and healthy (all 9 services up).
