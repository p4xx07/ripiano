# Judge 3, round 12 report

- Candidate: `71315f4531f0ef02d0205aa77bfdce0019c9c127` (branch `codex/initial-implementation`; HEAD `57c76a3` adds evidence files only). The stack was built from the candidate by the caller. I did not rebuild it.
- Date: 2026-11-20, 11:15–12:40 CET
- Stack: own Compose project `ripiano-j3`, http://localhost:18103. It started empty, and I did the first-time setup myself with the setup key.
- Browser: Playwright `Version 1.64.1`, Chrome channel `157.0.8103.79`. Desktop was 1440x900. Mobile emulation was 390x844 with `isMobile`, `hasTouch` and DPR 3. I used `en-US` and `it-IT` locales.
- Screen reader: none is installed. I used Playwright `ariaSnapshot()` on the accessibility tree instead.
- Artifacts: `qa-artifacts/20261120-r12-judge-3/` (40 PNGs; agent token values are masked in `25-*.png`).
- Scripts, passwords and id lists are in my scratch folder (`…/scratchpad/j3r12/`: `s1.mjs`–`s38.mjs`, `lib.mjs`, `api.mjs`, `facts.mjs`, `csrf.mjs`, `mask.mjs`, `dc` wrapper). I deleted the token files. All 4 agent grants I created are revoked.

## Commands run (summary)

- `docker compose -p ripiano-j3 --env-file …/jstacks/j3/stack.env {ps, stop worker, start worker, kill worker, stop api, start api, cp <fixture> maintenance_worker:/consume/, exec api manage.py shell, down -v, up -d db broker api, stop …, run --rm --no-deps api manage.py restore_snapshot 20261120T103206427736Z-dd799819 --yes, up -d}`
- Browser journeys: `node s2.mjs` … `node s38.mjs`, run from the scratch folder with `apps/web/node_modules` symlinked. The scripts cover setup, upload, filing, suggestions, locations, stickers, search, worker and API interruption, agents, people and sharing, backup, the restored-stack checks, keyboard use, and Italian on mobile.
- API checks with the owner and member sessions (`api.mjs`): documents, jobs, filing suggestions, member isolation, and CSRF without the header.
- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` → `457 passed, 17 skipped in 75.43s`.

## Fixture IDs used

- `judge.png`, used as a gallery image, then again as a camera capture on mobile (flagged as an exact copy).
- `three-pages.pdf`, `office-letter.docx`, `office-sheet.xlsx`, `office-slides.pptx`, `office-open.odt`, `office-legacy.doc`, `email-notice.eml`, `outlook-notice.msg`.
- `tag-barcode-mobile.pdf`, `asn-batch-mobile.pdf` and `barcode-batch-mobile.pdf`, uploaded in the browser during the worker-down and worker-kill tests.
- `asn-batch-desktop.pdf`, `tag-barcode-desktop.pdf` and `barcode-batch-desktop.pdf`, imported through the watched consume folder.
- Two derived inputs:
  - `condominio-seconda-riunione.eml`, a plain-text email modelled on `outlook-notice.msg` and `email-notice.eml`. I needed it because the fixture corpus has no two documents that share 3 or more distinctive words, so the corpus alone cannot trigger a suggestion.
  - `fake.pdf`, a text file renamed to `.pdf`, for upload validation.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | **Capture without a TODO screen:** gallery (05), camera button with `capture=environment` on mobile (19), batch of PDF/Office/eml/msg (06–07, all Ready within ~10 s), and the watched consume folder: three PDFs imported in under 1 min, barcode split into parts, ASNs set (`900001`, `900011/12`). Every file landed in the Library. Inbox lists only exceptions: exact copies, with "Keep both" or "Move this copy to Trash" (36). A mixed batch rejects the fake PDF with a clear per-file reason and adds the valid file (35). **Filing:** sender, type and tag can be created inline (09). On a similar new document, suggestions show the example and the shared words (11). In one screen I accepted the sender, rejected the type, created a new type, accepted the tag and saved (12); the API shows all of it as `manual`. **Defect:** wrong suggestions made from email-header boilerplate (M1). | Telegram and native Android capture are out of scope by owner decision. The real camera is emulated by a file input. |
| Retrieval and physical filing | 20% | 9.4 | **Search:** an OCR phrase (`second heron`), sender (free text and `sender:"…"`), `tag:casa`, `date:2026-11`, exclusion (`heron -tag:casa`) and `sticker:` all returned the correct documents with snippets (20). **Paper copy:** nested locations (13), a sticker created in "Armadio studio / Scatola 2026" (14), and a 70x40 mm label with QR, title, code and path (15/15b). Moving the copy to "Scaffale cucina" gives a reprint hint. Lookup by lowercase code works (16). Opening the QR URL (`/?sticker=…`) signed out on mobile leads to sign-in and then lands on the found sticker (17–18). The re-scanned label resolves to the new place. | Live camera QR decoding was not exercised: headless Chrome has no camera. |
| UX and accessibility | 20% | 9.2 | **Keyboard:** skip link, `?` shortcut list, `/` search, `n` Add, `g p` navigation, `j`/`Enter` opens a document, a focus trap in the document dialog (80 Tabs, 0 escaped), and focus returns to the row after Esc or Close (s33–s35). The focus ring is visible (3px outline + 6px ring). **Italian:** the setup screen is localized, including the native validation message (02). An `it-IT` mobile sweep of 11 screens and the document dialog found no English UI strings. **Mobile:** layouts are clean (18, 19, 26, 34), and the only targets under 44px are tag checkboxes inside larger labels. **Friction:** worker-down is explained only on Overview, not where the person waits (L1). The label language does not follow the UI language (L2). | Installed iOS/Android PWAs and the Android client are out of scope. No real screen reader. |
| Reliability and recovery | 20% | 9.4 | **Worker stopped, upload:** documents show "Waiting". After the 2-minute grace, Overview says text recognition is not running and how to fix it (24). Starting the worker processes them on its own. **Worker killed right after a barcode split:** both parts finished after the restart, with no duplicates. **API stopped during a mobile upload:** an offline banner and "1 file is waiting to upload… trying again" (26). The file was added once the API was back. **Backup now:** verified (29). Then `down -v`, an empty stack, `restore_snapshot`, `up -d`. After restore, all of these matched before/after: 22 documents, metadata, tags, locations, the sticker location, and SHA-256 of all 22 originals (`facts-before.json` vs `facts-after.json`, all `True`; the `three-pages.pdf` original matches the fixture hash). Owner and member sign-in work, and the member still sees the shared document. 3 revoked grants stayed revoked and 1 active stayed active (30–31). | Broker stop was not exercised. I did not confirm a kill strictly during OCR: the documents were queued when I killed the worker. NAS performance is out of scope. |
| Privacy and agent control | 15% | 9.0 | **Grants:** created in the UI with different scopes and filters: "Cloud helper (casa)" (titles/tags only, `casa` documents only) and "Local classifier (all)" (titles, OCR text, tags). The password is required, and the token is shown once with the MCP URL. Revoke has an inline confirmation, and revoked grants move to "Revoked or expired". The UI states that a cloud agent may send the text it reads to its provider. **Isolation:** the member gets 404 on the owner's unshared document, its original and its sticker. A view-only share gives PATCH 403 and trash 404. **CSRF:** a POST without the header gets 403 with a clear message. Revoked grant states survive restore. | **The MCP endpoint calls (initialize/tools/list, scoped tool calls, 401 after revoke, audit entries from real calls) were denied by the session's permission classifier and NOT exercised.** "Recent activity" therefore stayed empty. The API suite (457 passed), which contains the MCP scope tests, is the only evidence for that part. |

**Weighted mean: 0.25×9.0 + 0.20×9.4 + 0.20×9.2 + 0.20×9.4 + 0.15×9.0 = 9.20**

## Hard gates

| Gate | Status in this review |
| --- | --- |
| 1. Parity scenarios | Partially demonstrated: upload channels, consume folder, OCR, barcode/ASN, tags, senders, types, search syntax, duplicates, notes, history, physical copies, sharing, backup/restore. I did not walk every parity row. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **Demonstrated** on my own stack: originals (SHA-256), tags, locations, revoked grants and member shares were all preserved. |
| 3. Installed iOS/Android PWA, native Android | Out of scope by owner decision (D7). |
| 4. Security review | Partially: account isolation, CSRF, upload validation and grant scoping/revocation in the UI were demonstrated. MCP calls were not exercised (permission denied). |
| 5. Tests and builds | API suite re-run: `457 passed, 17 skipped` (matches `.omo/evidence/round12-verification.md`). That file is credible: commands and result lines are listed, the commit is 71315f4, and e2e shows `402 passed, 48 skipped`. I did not re-run the build or e2e, as the brief instructs. |
| NAS / real devices / real Telegram, Google, Microsoft, Dropbox | Out of scope by owner decision. |

## Findings

### Severe
None.

### High
None.

### Medium

**M1 — Filing suggestions are built from email-header boilerplate and propose a wrong sender, type and tag.**

Reproduction:
1. On an empty archive, upload `outlook-notice.msg` and `office-legacy.doc` and file both as sender "Condominio Via Roma", type "Avviso", tag "casa".
2. Upload a similar condominio email (`condominio-seconda-riunione.eml`, `To: famiglia@example.test`) and file it as sender "Condominio Via Roma", type "Verbale", tag "casa".
3. Open `email-notice.eml`, a municipal TARI tax bill from "Comune di Esempio".
4. It offers "3 filing suggestions" (34): tag casa, sender Condominio Via Roma, type Verbale.
5. `GET /api/documents/<id>/filing-suggestions` shows `shared_terms ['famiglia', 'example', 'subject', 'avviso']`, similarity 0.32.

Three of the four words are the recipient address and the header label "Subject". These appear in every email a household receives, so most of its emails would get confident-looking but wrong sender suggestions until the archive is large. Suggestions are never applied automatically, and the shared words are displayed, so the user can spot it. But this is the "uncertain suggestion" path the rubric scores.

Cause: in `services/api/archive/classification.py`, `_evidence` (line 53) counts email header labels and the owner's own address. Common words are only discounted when `count > max(4, len(rows) // 4)` (line 113), which never happens in a small archive. Header labels and the archive owner's address are not in `STOPWORDS` (line 20). The gates `len(shared) < 3` (line 119) and `similarity < 0.3` (line 122) are both just met.

### Low

**L1 — A family member waiting on an upload is not told that OCR is down.**

Reproduction:
1. `docker compose … stop worker`.
2. Upload `tag-barcode-mobile.pdf` and `asn-batch-mobile.pdf`.
3. After more than 2 minutes, the Library rows still say only "Waiting" and the Library page has no notice (23).

The explanation ("text recognition is not running… start the worker") appears only on Overview, in the Background jobs panel (24; `apps/web/src/JobsPanel.tsx:40`).

**L2 — The printed sticker label ignores the UI language.**

With the UI in English (browser `en-US`), `GET /api/copies/<id>/label` returns `<html lang="it">` and `<title>Ripiano adesivo R-…`. The owner account was created from an Italian browser, so the label seems to follow the stored or setup language rather than the current UI. The visible label text is language-neutral, so the impact is minimal. The label is built in `services/api/archive/physical_views.py` (`printable_label`, around line 424).

**L3 — Thin-corpus note, not a defect of the build.**

None of the fixtures share 3 or more words of 4+ letters (`classification.py:119`), so on the identical fixture corpus no suggestion ever appears. "Suggestions appear here after you have filed a few similar documents" is shown instead (10-*). Judging the suggestion UI needed the derived input listed above.

## Most serious finding
M1: wrong sender, type and tag suggestions built from email-header boilerplate (`famiglia`, `example`, `subject`). They appear on most household emails in a small archive.

## Not exercised
- MCP endpoint calls: tool lists per grant, scoped calls, 401 after revoke, and audit entries. The permission classifier denied the curl call; I did not work around it.
- Broker outage.
- A worker killed strictly during OCR of a single document.
- Live camera QR scan.
- Dark/AMOLED themes.
- Workflows, IMAP, external sources.
