# Judge 3 — round 11 report

- **Candidate:** `1c823549b93d3d9f8a65866d2e2d26e192e1df5e` (`1c82354`). HEAD during the review was `5925b9a`, which only adds `.omo/evidence/restore-drill-round11.md` and `.omo/evidence/round11-verification.md` (`git diff --stat 1c82354 HEAD`: 2 files, 100 insertions). The working tree had no source changes.
- **Date:** 2026-11-20 (about 09:30–10:00 CET)
- **Stack:** my own Compose project `ripiano-j3` at http://localhost:18103. It was built from the candidate and empty when I started. I did the first-time setup myself with the setup key.
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (channel `chrome`, headless), Node v26.8.1. Contexts: desktop 1440×900 and mobile emulation 390×844 (`isMobile`, `hasTouch`, DPR 3, iPhone user agent). Language checks used `en-US` and `it-IT`.
- **Screen reader stand-in:** no screen reader is installed, so I used Playwright's `locator.ariaSnapshot()` accessibility tree instead.
- **Artifacts:** `qa-artifacts/20261120-r11-judge-3/` (41 PNGs; agent token values are masked in the page before each screenshot).
- **Scripts, passwords, tokens, id lists:** kept outside the repository in `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j3r11/`.
- **Permissions note:** `curl` was denied by the tool permissions, as was a direct run of the Chrome binary. For HTTP API and MCP calls I used Playwright's `APIRequestContext` (`pw.request.newContext`) with a signed-in session plus CSRF header, or a bearer token for MCP. The Chrome version came from `browser.version()`.

## Commands and scripts

All scripts are in the scratch folder. Each ran with `cd apps/web && node <scratch>/<script>.cjs` and loads `@playwright/test` through `createRequire(apps/web/package.json)`.

| Script | What it does |
| --- | --- |
| `lib.cjs`, `mcp.cjs`, `dc.sh` | Helpers: browser/contexts, API session client, a minimal Streamable-HTTP MCP client, and the Compose wrapper `docker compose -p ripiano-j3 --env-file …/jstacks/j3/stack.env "$@"` |
| `02-setup.cjs` | First-time owner setup in the browser, including the weak-password check |
| `03-add.cjs`, `05-mobile-add.cjs` | Desktop: Take a photo, then Browse files with a batch. Mobile: Choose from photos, then Browse files |
| `07-file-ui.cjs` ×5 | File five documents by hand in the document dialog: sender, type, tag, with inline creation |
| `08-tagbarcode.cjs` + `dc.sh cp …/tag-barcode-desktop.pdf maintenance_worker:/consume/` | Barcode-mapped tag, then the watched (consume) folder |
| `09-suggest.cjs`, `10-correct.cjs`, `42-mobile-correct.cjs` | Upload a similar scan, inspect the suggestions, then accept / reject / correct in one screen (desktop and mobile) |
| `12-search.cjs` | 19 Library queries in the UI |
| `13/14/15/16/17/18-*.cjs` | Locations, sticker, printed label, lookup, deep link, move, history, reprint. Camera scan uses a fake camera: `ffmpeg … label.y4m` and `--use-file-for-fake-video-capture` |
| `19-killworker.cjs`, `20-backup-ui.cjs`, `21-stall.cjs`, `22/23-*.cjs` | `dc.sh kill worker` during an ASN split; Back up now with the worker dead; stalled detection; `dc.sh start worker`; recovery |
| `24/25/26/27-*.cjs` | Two agents created in the UI, `tools/list` and tool calls over MCP, activity log, revoke |
| `28-people.cjs`, `29-security.cjs` | Family account; isolation, CSRF, upload validation, unauthenticated access, headers |
| `30-api-down-upload.cjs`, `31-outages.cjs` | `dc.sh stop api` during a UI upload, plus a page reload while it is down; `dc.sh stop broker` during an upload |
| `32-state.cjs`, `33-prebackup.cjs`, `34-verify.cjs` | Restore drill (below) |
| `35-keyboard.cjs`, `36-focus.cjs`, `37-italian-mobile.cjs` | Keyboard-only use, focus visibility, Italian on mobile, touch-target sizes, horizontal overflow |
| `38-holdback.cjs`, `39-workflows-ui.cjs`, `40-edges.cjs`, `41-conflict-ui.cjs` | Workflow started by an agent (D12), edit conflict over the API and in the UI with two tabs, scan-ID retry, share link, Trash |
| `43-cleanup.cjs` | Revokes every agent grant I created; both tokens then answer 401 |

Restore drill on my stack, following docs/BACKUP_RESTORE.md:

```
33-prebackup.cjs   → upload barcode-batch-desktop.pdf, kill worker while "processing", POST /api/backups → complete 20261120T085230271726Z-240f8c1d
dc.sh down -v
dc.sh up -d --wait db broker api        → users 0 docs 0
dc.sh stop web worker maintenance_worker scheduler mcp api
dc.sh run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261120T085230271726Z-240f8c1d --yes → "Snapshot restored."
dc.sh up -d --wait
32-state.cjs post-restore.json; 34-verify.cjs
```

API suite, re-run by me: `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` gave `438 passed, 17 skipped in 71.60s`. I did not run `npm run build` or the e2e suite, as the brief instructs.

## Fixture IDs used

`judge.png` (camera, gallery, duplicate, scan-ID retry), `three-pages.pdf`, `office-letter.docx`, `office-sheet.xlsx`, `office-legacy.doc`, `office-open.odt`, `office-slides.pptx`, `email-notice.eml`, `outlook-notice.msg`, `asn-batch-mobile.pdf`, `asn-batch-desktop.pdf` (killed-worker split), `barcode-batch-mobile.pdf`, `barcode-batch-desktop.pdf` (similar scan for suggestions; backup with the worker killed), `tag-barcode-mobile.pdf`, `tag-barcode-desktop.pdf` (consume folder + TAG mapping). All 15 corpus files were used.

## Scores

| Dimension | Weight | Score | Evidence (what I exercised) | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.2** | **Desktop:** Take a photo (`capture=environment` input) and Browse files with 5 mixed files. All 6 documents were ready in 11 s. **Mobile:** Choose from photos and 6 Office/barcode files, all ready. Splits were correct (PATCHT, ASN 900021/900022, `(1/2)`/`(2/2)`). Exact copies were flagged and sent to Inbox only. Office, .eml, and .msg converted, and email dates were detected. Consume folder: the file imported within about 1 minute, marked "from NAS folder", with tag `Bills` added from its `ARCHIVE-BILLS-DESKTOP` code. No mandatory TODO screen. **Suggestions:** after I filed 5 documents, the similar scan showed tag, sender, and type suggestions, each with the example document and the shared words (20-suggestions-2-2.png). In one screen I accepted the sender, rejected the tag (✕ "Not right"), picked another tag, and accepted the type; this took about 7 s on desktop and 6 s on mobile, the unsaved title draft survived the one-tap accept, and the result persisted. | Telegram, Android scanner, and real camera hardware are out of scope (D7). Learned-model probability suggestions were not reached: the model needs more filed data than the corpus allows. Example suggestions show no confidence level. |
| Retrieval and physical filing | 20% | **9.2** | All of these found the right documents: OCR phrase (`second heron`), Italian stem (`tassa rifiuto` → *rifiuti*), sender (`sender:"Comune di Esempio"`), tag and its Italian alias (`tag:Home`, `etichetta:Home`), month (`date:2026-11`), exclusion (`type:Notice -tag:Taxes`), `OR`, `asn:900022`, `is:untagged`, and digits (`9473`). A typo got "Did you mean mirtillo". `/` focuses search. **Physical:** nested location Study shelf / Tax box; a sticker created from the document dialog; label printed with a QR that encodes `http://localhost:18103/?sticker=R-JWSABLZN`, decoded with pyzbar in the worker. The mobile deep link from that URL found the copy. Moving the copy to Garage box showed "If its sticker shows the old location, print it again", and the history records both placements. The reprinted label scanned with **Scan with camera** (real `BarcodeDetector`, fake camera feed) found "Place: Garage box". | Printing on paper. Missing/found status and location-contents views were only seen, not exercised in depth. |
| UX and accessibility | 20% | **9.0** | **Keyboard only:** sign in with Tab and Enter; `?` lists the shortcuts; `/`, `n`, `g t`, `g p`, `j`, `k`, and Enter work. The dialog traps focus (60 Tabs never left it), Escape returns focus to the row, and the focus ring is visible on every stop (3 px outline plus shadow). The only exception is Chrome's own date-picker button. ARIA snapshot: labelled dialog, regions, headings in order h1 → h2 → h3, labelled comboboxes, `status` live regions announcing result counts and saves. **Italian on mobile:** Library, document, Paper archive, Overview, Agents, Backups, and Inbox showed no English leftovers in my heuristic scan. No horizontal overflow at 390 px. No touch target under 44 px on Library or the document dialog, except the skip link. Copy is clear and friendly throughout. | Installed iOS/Android PWA, Android client, and VoiceOver/TalkBack are out of scope (D7). axe-core is not installed. |
| Reliability and recovery | 20% | **9.4** | **Worker killed mid-split:** flagged `stalled` at 2 min with Retry/Cancel on Overview. Back up now succeeded in 5 s with the worker dead. After `start worker`, the parts were ready within about 20 s and the source within about 80 s, with exactly 2 parts and the `.work` folder emptied. **API stopped during a UI upload:** "1 file is waiting to upload. Ripiano couldn't be reached; trying again…". The pending file survived a page reload and arrived 16 s after the API came back, with no action from me. While the API was down the UI showed "Ripiano can't be reached… will reconnect by itself" and recovered on its own 16 s after restart. **Broker stopped:** the upload was accepted, `/healthz` answered 503 `{"status":"unavailable"}`, and the document was ready 9 s after the broker returned. **Restore:** clean-stack restore from a snapshot taken with the worker killed mid-processing. For all 22 pre-backup documents, title, tags, sender, type, ASN, physical copy plus location, and the original's SHA-256 were identical (0 diffs). Tags with barcode, 3 locations, the member account, the revoked grant (still 401), and the active grant (200, same filter results) all survived. The interrupted document finished about 50 s after start-up with no duplicate parts. Retries: the same scan ID with the same file returned the same document (200); with a different file it was refused (409). | NAS restore and performance are out of scope (D7). DB restart was not exercised. |
| Privacy and agent control | 15% | **9.4** | Two agents created in the UI, each confirmed with my password: (a) titles-only, filtered to `Taxes`; (b) all four permissions, filtered to `Home`. `tools/list` matched exactly (`[search_documents]` and all 6 tools). (a) found its document by title, found nothing for an OCR word (`tassa`), and got "Tool is not permitted" for `get_document_text`. Both agents were blind outside their filter tag ("Document not found within this grant"). (b) was refused adding another agent's filter tag. Every call, including refusals, appears under Recent activity with the document title and no text. Revoke needs an inline "Yes, revoke"; the token then answers HTTP 401 and the other agent keeps working. **D12:** an agent adding `Family` started a "share with member" workflow; the note was added but sharing was held back ("skipped sharing (an agent made the change…)"), and member still gets 404. **Member account:** 404 on my document, original, archive, pages, history, and sticker; 403 on backups; 0 search hits. A PATCH without CSRF from a foreign origin got 403. HTML renamed `.pdf` got 400 and an empty file got 400. Anonymous `/api` calls got 401. CSP `default-src 'self'`, `X-Frame-Options: DENY`, and `nosniff` with `no-store` on originals. Share link: anonymous 200, then 404 after revoke. | Cloud-model provider behaviour (no content leaves Ripiano by design). 2FA and API tokens were not exercised this round. |

**Weighted mean:** 0.25×9.2 + 0.20×9.2 + 0.20×9.0 + 0.20×9.4 + 0.15×9.4 = **9.23**

## Hard gates

| Gate | Result |
| --- | --- |
| 1. Every parity capability has a working scenario or accepted deviation | **Partly demonstrated.** I exercised: web/API/consume-folder upload; Office, email, and .msg processing; OCR and search syntax; barcode/ASN/TAG splitting; tags, senders, and types with inline creation; example suggestions; duplicates; history (Changes); edit conflict; workflows (D12); people and sharing isolation; share links; Trash and restore; Overview and jobs; backup and restore; Italian; keyboard. Not exercised: IMAP mail rules, S3/WebDAV/folder Sources UI, PDF page editing and versions, custom fields, storage paths, bundles and document email, 2FA, API tokens, learned-model auto-filing, semantic search (not configured; not a defect). I found no evidence of a missing capability. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **PASS on my own stack.** Originals (checksums), tags, locations, sticker, member account, and revoked/active grants all verified. The document interrupted mid-processing finished after the restore. |
| 3. Installed iOS PWA, Android PWA, native Android, real-device capture | **Out of scope by owner decision (D7).** |
| 4. Security review (isolation, revocation, CSRF, upload validation, external input, no content to providers) | **PASS within what I tested.** Real Telegram, cloud-drive, and mail endpoints are out of scope (D7). |
| 5. Unit/API tests, builds, browser journeys, migrations, deployment checks | **Credible.** My API re-run matches the record (`438 passed, 17 skipped`). `round11-verification.md` records type check, build, `makemigrations --check`, Compose config, and 355/45/0 e2e with commands. Its note on an earlier flaky mobile run is candid. I did not re-run build/e2e (brief). The stack I was given came up healthy from the candidate. |

## Findings

No severe or high findings.

### Medium

**M1 — On a phone, the filing suggestions are about 1.5 screens below the top of the document.**
- Repro: mobile 390×844, open `barcode-batch-desktop (1/2)` after filing a similar document.
- The order is: preview, "Show larger" / "Open full size", exact-copy notice, split notice, Title, ASN, Document date, and only then "Suggested from your documents" (58-mobile-suggestions.png).
- The rubric's "correct an uncertain suggestion in one screen" works, but on a phone the user must scroll past the preview first. The suggestions are the main reason to open a freshly captured document.
- Cause: the `DocumentPanel.tsx` layout puts suggestions after the date field (`apps/web/src/DocumentPanel.tsx`, suggestions loaded at :297).

**M2 — Scanning a sticker gives no way to move or mark the copy from the result.**
- Repro: Paper archive, then Find (or the deep link `/?sticker=R-…`, or Scan with camera).
- The result card shows only title, place, and "Open document". To record a move, you must open the document dialog and scroll to Paper copies near the bottom, then choose and press Move (about 5 s scripted on mobile; more for a person).
- "Scan the sticker → put it in another box" is the core paper-filing gesture.
- Cause: `apps/web/src/PhysicalPanel.tsx:318-332`, where the `sticker-result` card renders only `onOpenDocument`.

### Low

- **L1 — Broken English in workflow summaries.** Repro: create a workflow with a tag, sender, or type condition. It reads "When I change a document, if it tagged Family: …". The same pattern gives "if it sender X" and "if it type X". Cause: `apps/web/src/locales/WorkflowsPanel.ts:29-31` with `:64` (`if it ${conditions}`). The Italian strings are correct.
- **L2 — The server-down screen is titled "You're offline" although the device is online.** Repro: `dc.sh stop api`, then load the app. The body text is correct ("Ripiano can't be reached"). Cause: `apps/web/src/locales/App.ts:35` `offlineTitle`.
- **L3 — Overview counts disagree, and nothing says no OCR worker is running.**
  - Repro: `dc.sh kill worker` during an ASN split.
  - Overview shows "2 being processed", Background jobs shows "Waiting for text recognition 3" (it includes the hidden split source), and Needs a look shows "Background queues: 6 OCR" (37-overview-stalled.png).
  - The row says "will be tried again by itself", which only happens once a worker exists. There is no "no worker is consuming the queue" signal.
- **L4 — On mobile, the auto-focused Close button's focus ring overlaps the end of the dialog title.** Repro: tap a document on a 390 px viewport (54-it-mobile-document.png, 58-mobile-suggestions.png). It is cosmetic; `:focus-visible` from a touch open.
- **L5 — Inbox lists a hidden split source as an exact copy.** Repro: upload the same barcode batch twice. The Inbox lists "barcode-batch-desktop — Exact copy of barcode-batch-desktop", although the Library hides split sources (60-mobile-inbox.png). It is mildly confusing, though the "Keep both" path is harmless.
- **L6 — The printed label page has no print control.** Repro: Print sticker opens a bare 264×150 label page (29-printed-label.png). It also prints the current location, which goes stale after a move; the app does warn to reprint.
- **L7 — Pending documents show as "Processing" while the queue server is down.** Repro: `dc.sh stop broker`, then upload. Status is `pending`, but the Library badge says "Processing" (48-upload-broker-down.png).

## Most serious finding

**M2.** Scanning a paper copy's sticker (with the camera, a deep link, or typed) lands on a result card whose only action is "Open document". Moving or marking the copy needs the full document dialog and a scroll to its bottom section (`apps/web/src/PhysicalPanel.tsx:318-332`). Everything works, but it adds steps to the most frequent physical-filing gesture.

## Cleanup

Both agent grants I created are revoked, and both tokens answer 401. The stack `ripiano-j3` is left running and healthy after my restore drill. It contains the family account `member` (password in the scratch folder) and the workflow "Share Family docs". I did not modify, commit, or rebuild any source.
