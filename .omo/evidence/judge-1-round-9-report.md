# Judge 1 — quality round 9 report

- **Candidate SHA:** 1a365f35c12509f79da9cd9c459b426dca1f4ec4 (branch `codex/initial-implementation`). The running images in Compose project `ripiano-j1` were built at 2026-11-19T14:04Z from this commit. Two newer commits (4fc2458, c06ffba) arrived on the branch during the review. I did not judge them, but I note below where they already fix a finding.
- **Date:** 2026-11-19
- **Emphasis:** a first-time owner: install, capture and filing, retrieval, paper copies and stickers, damaged PDFs, recovery.
- **Browser:** Playwright 1.64.1 (`@playwright/test` from apps/web), Chrome channel 157.0.8103.79. Desktop is 1440x900. Mobile emulation is 390x844 with isMobile, hasTouch, and DPR 2. Locales were en-US and it-IT.
- **Stack:** http://localhost:18101, Compose project `ripiano-j1`. No image rebuild and no env edits. The stack was left running with all 9 services up.
- **Screen reader:** none is installed. I used Playwright `locator.ariaSnapshot()` as a stand-in.
- **Environment note:** the host wall clock jumped about 4 hours during the session (`date` went from 16:37 to 20:44 CET within minutes). This affected one timing observation (see finding H1). It is not an app defect.

## Commands and scripts

The scripts are in `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j1r9/`. I ran them with `node <script>` from inside apps/web. They import Playwright by absolute path.

| Script | What it does |
| --- | --- |
| `01-setup.mjs` | First-time setup: wrong setup key, then a too-short password, then the real setup. |
| `02-explore.mjs` | Empty library and the Add dialog. |
| `03-upload.mjs` | Desktop upload through "Browse files". |
| `06-file.mjs` | Manual filing through the UI: sender, type, and tag. |
| `07-upload-kill.mjs` + `dc.sh kill worker` | Kills the worker in the middle of OCR. |
| `09-correct.mjs` | Accepts suggestions, then rejects and corrects an uncertain one. |
| `10-search.mjs`, `11-paper.mjs` | Search, filters, and the "did you mean" message. |
| `12-sticker.mjs`, `13-print.mjs`, `14-qr.mjs` | Locations, a sticker, the printed label, and a fake-camera Y4M video made from the printed QR code. |
| `15-camera.mjs` | Scan with camera: desktop and mobile with permission granted, permission denied, and no BarcodeDetector. |
| `16-mobile-move.mjs` | Italian on mobile: scan, open the document, move the copy, scan again. |
| `17-mobile-upload.mjs` | Damaged and broken PDFs uploaded on mobile. |
| `18-restart.mjs` + `dc.sh restart api` | Restarts the api during a throttled 2 MB upload. |
| `19-apidown.mjs` + `dc.sh stop api` (25 s) / `start api` | Upload while the api is down. |
| `20-kbd.mjs` | Keyboard-only path, shortcut help, and the Agents page. |
| `21-agents.mjs`, `22-mcp.mjs`, `23-mcp2.mjs`, `24-revoke.mjs`, `25-check401.mjs` | Two scoped agent grants, MCP `tools/list` and calls, a text-oracle probe, revocation, then 401 checks. |
| `26-backup-mobile.mjs` | Tapping a suggestion on mobile, then "Back up now". |

State was checked with `docker compose -p ripiano-j1 --env-file …/jstacks/j1/stack.env exec -T api /app/.venv/bin/python manage.py shell < dumpN.py`. These scripts read only.

I re-ran the API suite with `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q`. Result: `372 passed, 15 skipped in 61.78s`. This matches round9-verification.md.

## Fixture IDs used

- **From the fixture folder:** judge.png, three-pages.pdf, asn-batch-desktop.pdf, asn-batch-mobile.pdf, barcode-batch-desktop.pdf, barcode-batch-mobile.pdf, tag-barcode-desktop.pdf, tag-barcode-mobile.pdf, email-notice.eml, outlook-notice.msg, office-letter.docx, office-open.odt, office-legacy.doc, office-sheet.xlsx, office-slides.pptx.
- **Derived inputs, kept in scratch only:**
  - `damaged-three-pages.pdf`: three-pages.pdf cut to its first 50,000 bytes.
  - `broken-asn.pdf`: asn-batch-mobile.pdf cut to its first 3,000 bytes.
  - `restart-big.pdf`: three-pages.pdf plus 2 MB of padding.
  - `restart-small.png` and `apidown.png`: judge.png plus a few trailing bytes.
  - `qr.y4m`: a fake camera feed of the printed sticker R-3ECRVP2F.

## Dimension scores

| Dimension | Weight | Score | Evidence | Not exercisable or not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **9.1** | See "Capture and filing" below. | Telegram bot and watched folder (no accounts or mounts used). Real camera capture and the native Android scanner are out of scope (D7). The "Take a photo" button was only seen in the dialog. |
| Retrieval and physical filing | 20% | **9.3** | See "Retrieval and physical filing" below. | Printing on a physical printer. A real phone camera-app deep link (out of scope). The date-range filter was seen but not used. |
| UX and accessibility | 20% | **9.0** | See "UX and accessibility" below. | Real assistive technology. Installed PWA and Android client (out of scope, D7). |
| Reliability and recovery | 20% | **8.7** | See "Reliability and recovery" below. | I did not run my own `down -v` restore drill. I read restore-drill-round9.md instead: credible, PASS on 1a365f3, with checksums, a revoked grant still at 401, and the sticker location restored. Broker outage was not tested. |
| Privacy and agent control | 15% | **9.4** | See "Privacy and agent control" below. | Real cloud agent clients (out of scope). Tag-changing tool calls were not exercised. |

**Weighted mean:** 0.25·9.1 + 0.20·9.3 + 0.20·9.0 + 0.20·8.7 + 0.15·9.4 = **9.09**

### Capture and filing

- **Uploads.** I uploaded 8 mixed files on desktop (01–06): PDF, PNG, EML, DOCX, and ODT. The barcode batch was split into 2+2 documents, and ASN 900002 was detected. I uploaded more on mobile (29–31), including MSG, DOC, XLSX, and PPTX. Everything reached Ready in the Library without a TODO screen. The Inbox shows exceptions only (32).
- **Manual filing (09).** "Add a sender", "Add a type", and "Create a tag" work inline in one dialog.
- **Suggestions (15).** After I filed barcode-batch-desktop (1/2), the similar mobile page got sender, type, and tag suggestions. Each one shows a "Like X · shared: …" reason, and accepting takes one tap (16). Mobile tap targets are 274x70 and 44x70 (41).
- **Correcting a wrong suggestion (17–18).** barcode-batch-mobile (2/2) is an invoice, but it was suggested as Letter from Quokka. I rejected the sender with an inline ✕ and added a new sender and type. All of this happened in one screen.

### Retrieval and physical filing

- **Search (19, 20).**
  - OCR phrases found the right documents: "wombat harbour", "otter", "heron", and "lampone 120".
  - A sender name, a tag name, and a text inside an email all worked.
  - A typo gave "Did you mean wombat".
  - The filters cover tag, sender, type, paper copy, custom detail, and date from/to.
- **Paper copies.** I created nested locations (22) and sticker R-3ECRVP2F (23), and printed its label (24).
- **Camera scanning (25).** "Scan with camera" read the printed QR through a fake camera on desktop and on mobile, and showed the copy and its location.
  - When permission is denied, the dialog says "Ripiano may not use the camera… or type the code" and offers "Type the code instead".
  - When BarcodeDetector is missing, the button is hidden and the intro switches to "Type the code… Or open its QR code with your phone's camera app".
- **Moving a copy (27–28).** On mobile in Italian I moved the copy to "Study cabinet / Tax box 2026". The status line reminded me to reprint the sticker. Scanning again showed the new location.

### UX and accessibility

- **Keyboard (37).** Tab order is logical. "/" focuses search, and the first result was reached in 6 Tabs. Enter opens the document dialog with focus on Close, and Esc returns focus to the row. "?" shows the shortcut list.
- **Italian on mobile (26–28).** Fully translated and clean. Tap targets are large.
- **Feedback.** Status messages are clear throughout, for example "Sender … saved. Other edits still need Save changes."
- **Friction found:** see M2, L1, and L2.

### Reliability and recovery

- **api restarts.** I restarted the api during a throttled 2 MB upload (33), and separately stopped it for 25 s during an upload (35). In both cases the upload completed (POST 202), and the originals were byte-identical (SHA-256 eb4b1066…, 6420b00c…, 0611b412…).
- **Damaged PDFs (30–32).**
  - The truncated PDF was kept with 2 of 3 pages searchable. Its warning reads: "This PDF is damaged, so some of its pages may be missing… Compare it with the paper…".
  - The unreadable PDF was marked Failed, with a readable message and Retry OCR in the Inbox.
- **Backup (42).** "Back up now" on mobile produced a complete, verified snapshot.
- **Killed worker.** The document under OCR stayed stuck. See H1.

### Privacy and agent control

- **Two grants (38–39).**
  - "Local classifier B": find, OCR text, and tags, on all documents.
  - "Cloud helper B": find only, limited to documents tagged Taxes.
- **Tool lists.** The local grant gets 4 tools. The cloud grant gets only `search_documents`.
- **Scope and permission checks.**
  - The cloud grant's search for "girasole" (a Home-tagged document) returned nothing.
  - Its `get_document_text` call was refused with "Tool is not permitted for this agent", and the refusal appears in Recent activity as "refused".
  - No text oracle: searching for text-only words ("rifiuti", "contribuente") returned nothing for the no-text grant.
- **Revocation (40).** Revoke asks for an inline "Yes, revoke". Afterwards the tokens get MCP 401. All 4 grants I created are revoked.

## Hard gates

| Gate | Status | Evidence |
| --- | --- | --- |
| 1. Parity scenarios | Partly demonstrated (in scope) | Capture, OCR, search, filing, suggestions, stickers, camera, backup, agents, and damaged PDFs work. Not exercised by me: Telegram, watched folder, mail rules, Drive/S3 import. No missing parity found in what I tested. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Demonstrated | I did fresh setup, upload, OCR, search, and backup on my own stack. The restore comes from restore-drill-round9.md on 1a365f3 (PASS, checksums, grants, stickers). I did not repeat it. |
| 3. Real-device iOS/Android PWA and native Android | Out of scope by owner decision (D7) | Not scored down. |
| 4. Security review (isolation, revocation, CSRF, upload validation, no default model transfer) | Partly demonstrated | Agent scope and permission isolation, revocation 401, no text oracle, and semantic search off by default. CSRF and multi-account isolation were not probed this round. |
| 5. Tests, builds, journeys, migrations | Credible | round9-verification.md: 372 passed / 15 skipped, migrations check, tsc, build, and 257/1 flaky/42 skipped e2e with a plausible isolation explanation. My API re-run matched (372 passed, 15 skipped). |
| Synology DS923+ performance, ACLs, and NAS restore | Out of scope by owner decision (D7) | — |

## Findings

### Severe

None.

### High

**H1. A document whose OCR worker is killed stays "Processing" for up to an hour, with Retry OCR disabled and no Inbox entry.**

Reproduction:
1. Upload tag-barcode-mobile.pdf, office-sheet.xlsx, and office-slides.pptx.
2. About 3 s later, run `docker compose -p ripiano-j1 … kill worker`.
3. Run `start worker`.

What happens:
- The two documents that were only queued (pending) finished within 40 s.
- The document under OCR (tag-barcode-mobile) stayed `processing`.
- In the document dialog, Retry OCR is disabled with "OCR is being prepared. The original is available above." (13). The Library shows "Processing" (12).
- The Inbox does not list it, although its intro says it shows processing failures (32).

It recovered only through the 1-hour stale reclaim. In my run that came early because the host clock jumped about 4 h. The document did eventually reach Ready, and nothing was lost.

Cause:
- `services/api/archive/tasks.py:74` (at 1a365f3) skips any document that is not PENDING. So when the late-acked task is redelivered (`settings.py:106` `CELERY_TASK_ACKS_LATE = True`; Valkey's visibility timeout is 1 h by default), it does nothing.
- `reconcile_pending_documents` (`tasks.py:219-225`) only resets PROCESSING rows older than 1 hour.
- The UI disables retry for `processing` (`apps/web/src/DocumentPanel.tsx:358,1051`).

For a family member, a scan that stays "Processing" for an hour with no way to retry looks lost. Suggestion: reclaim PROCESSING rows whose worker is gone after a few minutes (for example via a heartbeat or worker-start hook), or allow "Retry OCR" once processing is older than N minutes.

### Medium

**M1. No feedback while the api is unreachable during upload.**

Reproduction:
1. Run `stop api`.
2. Add a file through Browse files.
3. Wait 25 s, then run `start api`.

For about 35 s the banner says only "Adding 1 of 1…" (35), with no "server not reachable, retrying" hint. It did complete, and the bytes were intact, so this is about feedback only: a user may close the tab thinking it is stuck.

**M2. The "Search by meaning" card shows a red error banner while the feature is Off (38, 40).**

Reproduction: open Agents on a default install. A pink alert reads "The database image has no pgvector extension. Switch it to `pgvector/pgvector:pg17` before turning this on". The banner is also laid out in three broken columns: the code element splits the sentence. For an optional, off-by-default feature, a first-time owner reads this as something being broken. It should be neutral information, shown only when an option other than Off is selected.

### Low

- **L1. The setup screen names a specific deploy tool.** On 1a365f3 it says "Your setup key is in your Portainer configuration." (01; `apps/web/src/locales/App.ts:18,99`), while the README install uses `.env`. Already fixed in 4fc2458 after the candidate.
- **L2. Suggestion reasons echo filename words.** They read, for example, "shared: separator, barcode, mobile, batch" (17). "mobile" and "batch" come from the file names, not the document. It is slightly technical and can make a wrong suggestion look well-founded.
- **L3. The printed label shows the location at print time.** After a move, the old label shows the old shelf. The app tells you to reprint, which mitigates this; it is noted only for completeness.
- **L4. The browser's own validation message appears when the setup password is too short.** It follows the OS language: it appeared in Italian while the UI was in English (`minLength` without a custom message). Cosmetic.

## Most serious finding

H1: a worker killed during OCR leaves that document in "Processing" for up to an hour, with Retry OCR disabled and the document absent from the Inbox. Nothing is lost, but the owner cannot recover it themselves.

## Housekeeping

- Screenshots (40 files) are in `qa-artifacts/20261119-r9-judge-1/`. Agent tokens are masked.
- Tokens, password, and scripts stay in the scratch folder only.
- All 4 agent grants I created are revoked.
- The stack is running, and all services are up.
