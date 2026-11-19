# Judge 1, round 2: independent quality review

- Candidate SHA: `f2b94168ff7af0bb914bb3f644eef7ee7490394a` (branch `codex/initial-implementation`)
- Date: 2026-11-18
- Reviewer account: `judge1` (Admin). The password is not recorded here.
- Stack: http://localhost:18080. The web, api, mcp, worker, maintenance_worker, and scheduler containers were already running. I did not restart or rebuild anything.
- Browser: Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (`channel: "chrome"`, headless).
- Viewports: desktop 1440x900 (`locale en-US`), mobile emulation 390x844 (`isMobile`, `hasTouch`, DPR 2), and Italian (`locale it-IT`) on desktop and mobile.
- Artifacts: `qa-artifacts/20261118-r2-judge-1/` (41 PNGs; `d*` desktop, `m*` mobile; the agent token is masked in `d20`).
- Emphasis: first-time owner on desktop, then the key journeys repeated on mobile emulation.

**Working-tree note.** While I was reviewing, someone else edited files in the working tree, including uncommitted `App.tsx` changes such as `narrowLayout` and drawer focus handling. The bundle served at :18080 (`/assets/index-rciIubZm.js`) does not contain those changes, so it matches the committed candidate. All `file:line` references below are to `git show HEAD:<path>`.

## Commands and scripts

All scripts are in the session scratchpad (`.../scratchpad/j1/`). Each one ran from `apps/web` as `node <script>.mjs` and imported `@playwright/test` by absolute path. `lib.mjs` reads the password from `judges.env` at runtime and never prints it.

| Script | Purpose |
| --- | --- |
| `s1/s4` | Desktop first look and the Add dialog inventory |
| `gen.mjs`, `gen2.mjs`, `gen3.mjs`, `gen4.mjs` | Generate unique test inputs: a camera-style PNG bill, a PDF report, mobile PNGs, and PDFs for the watched folder |
| `s5` | Desktop upload: camera input, then four files in one multi-select; polls until processing finishes |
| `s6/s7` | Document dialog; correcting sender, type, title, and tag in one screen |
| `s8/s9` | Search by OCR phrase, sender, date, tag, combined query, and a typo, through the API and the UI |
| `s10/s11` | Sticker: create, print, move, history, lookup by `/?sticker=` |
| `s12/s13` | Desktop keyboard-only navigation: skip link, `/`, Esc, j/k, Enter, focus trap, focus return, `?`, `n` |
| `s14–s16`, `s27` | Inbox and Agents; create two grants, inspect the audit log, revoke |
| `mcp.mjs`, `mcplib.mjs`, `mcpschema.mjs`, `mcpwrite.mjs` | MCP Streamable HTTP client: `initialize`, `tools/list`, `tools/call` for each grant |
| `s17/s18` | Backups screen and **Back up now** |
| `s19/s20` | Learned suggestions on a second bill; accept by tapping |
| `s21–s23` | Folder source (watched NAS folder) from the UI |
| `s24` | Overview, Needs action, landmarks, title |
| `s25` | CSRF probe, upload content validation, random-ID access |
| `s26`, `m3` | Italian sweep of every screen, desktop and mobile |
| `m1/m2` | Mobile: offline capture plus offline reload plus reconnect; dropped connection mid-upload plus **Try now**; drawer; sticker lookup; document dialog |
| `m4/m5/m6` | Mobile drawer: Esc, tap outside, focus, Tab order; checks the deployed bundle |
| `m7` | Mobile location contents and location label |

For the watched-folder test I put files into the shared `/sources` volume with `docker cp <dir> ripiano-maintenance_worker-1:/sources/`. I then ran `docker exec -u root ... chown -R ripiano:ripiano /sources/r2-judge1`, which touched only my own subfolder.

## Fixture IDs used

- Corpus fixtures: `judge.png`, `three-pages.pdf`, `office-letter.docx`, `email-notice.eml`, and `office-open.odt` (read only). Searches also covered round-1 copies of `outlook-notice.msg`, `office-*`, `asn-batch-desktop.pdf`, and `barcode-batch-desktop.pdf` already in this account.
- Generated inputs, needed for unique OCR text: `r2j1-bolletta-camera.png`, `r2j1-bolletta-nov.png`, `r2j1-referto.pdf`, `r2j1-mobile-offline.png`, `r2j1-mobile-abort.png`, `r2j1-watched-polizza.pdf`, `r2j1-perm-probe.pdf`.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable or not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **7.5** | Camera input (`capture=environment`), gallery, and a 4-file multi-select (PDF, DOCX, EML, image PDF) all reached Ready in about 15 s. No mandatory TODO screen. Date 14/10/2026 was detected from Italian OCR text and recorded in the history as "Date and sender detection". Exact duplicates were flagged and both originals kept. A sender and a type were created inline, and a title and tag were corrected in one dialog (d06–d08). Learned suggestions appeared on the second bill with an explanation of the shared words, and one tap saved each (d24, d25). A watched NAS folder source imported a PDF in about 66 s with `source=folder` and did not import it again. | Real phone camera, Telegram (needs a bot token), Android native scanner. Every document still has to be filed without seeing it: there is no preview or thumbnail in the Library or the document dialog. A tag cannot be created from the document dialog. The title stays the file name (on a phone that is `IMG_xxxx`). A wrong suggestion cannot be dismissed and stays on every reopen. |
| Retrieval and physical filing | 20% | **8.0** | Found by OCR phrase (`pervinca`, `58213`, `87,40`), `sender:"Acquedotto Mirto"`, `date:2026-10`, `tag:Condominio`, and all three combined, with snippets (d09). Office and email text was searchable. Sticker created into a location, label printed with QR and code (d12), moved with history (d13), and looked up via the `/?sticker=` URL the QR encodes (d14, m08). Location label and nested contents worked on mobile (m13, m14). | A physical QR scan with a phone camera; I did not decode the QR in the browser, only checked `physical_views.py:415`. The PWA has no in-app scanner. There is no typo tolerance (`pervincx` finds nothing). The printed sticker includes the location at print time, which becomes wrong after a move. On mobile the first document row is below the first screen (m01). |
| UX and accessibility | 20% | **6.5** | Desktop keyboard works well: skip link, `/`, j/k move real focus, Enter opens, the dialog traps focus (0 of 120 Tabs escaped), Esc returns focus to the row, `?` lists shortcuts, focus ring is 3 px. Landmarks: aside, nav "Main navigation", main, header; the title follows the screen. Italian covers every screen except the Backups items noted below. No horizontal overflow at 390 px. | Installed iOS/Android PWA, Android client, a real screen reader (VoiceOver/TalkBack). **Mobile drawer defect (High)**: see the findings. While offline, the Library shows "0 Documents". |
| Reliability and recovery | 20% | **6.5** | Offline capture on mobile was kept in IndexedDB, survived an offline reload, and was sent after reconnecting (m03, m04). A connection reset mid-upload kept the file and **Try now** sent it (m06). **Back up now** completed and verified in 4.6 s (d23). The folder source did not import twice after two more polls. A `Permission denied` move error was reported clearly on the source card (d28). | Killing or restarting the worker or other services, and restoring to an empty stack: forbidden on this shared stack, so **not demonstrated**. A folder source that cannot write leaves one new copy in `processed/` on every poll (finding H2). An old failed backup shows a raw `[Errno 13] Permission denied: '/backup/staging'`. |
| Privacy and agent control | 15% | **8.5** | Two grants: "R2b Local full" (all 4 scopes, all documents) and "R2b Cloud titles" (search only, Condominio only). `tools/list` returned 6 tools and 1 tool respectively. The cloud grant found nothing by OCR phrase, by `text:`, or by `note:`; it saw no Tasse-only document; `get_document_text` and `list_tags` returned "not permitted" and were audited as denied. The local grant read text, added and removed a tag (shown as `Agent "R2b Local full"` in the document history), and was refused when it tried to replace a sender a human had chosen. Revoking in the UI made the next request return HTTP 401. A POST without CSRF returned 403. A fake PDF (shell text) was refused with 400. A random document ID returned 404. | Real cloud MCP clients, other accounts' document IDs for cross-account probes, OIDC. The audit list does not show which document was touched. An agent filter can be only one tag. `pervinca OR Bolletta` returned nothing for the titles-only grant even though "Bolletta" is in a title (low). |

**Weighted mean**: 0.25×7.5 + 0.20×8.0 + 0.20×6.5 + 0.20×6.5 + 0.15×8.5 = **7.35 / 10**

## Hard gates

| Gate | Status |
| --- | --- |
| 1. Every parity row has a working scenario or accepted deviation | **Partially demonstrated.** I covered upload, OCR, search syntax, duplicates, suggestions, physical copies, the folder source, MCP grants, backup, and Italian. I did not verify the parity matrix row by row; the parity audit belongs to another reviewer. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **Partially demonstrated.** Upload, OCR, search, and a manual verified backup passed. Fresh install and clean-stack restore were not run (shared stack; restarting is forbidden). |
| 3. Installed iOS PWA, installed Android PWA, native Android, real-device capture and interrupted upload | **Not demonstrated** (needs owner hardware). Only emulation: offline and connection-reset upload recovery worked in Chrome mobile emulation. |
| 4. Security review (isolation, revocation, CSRF, upload validation, external input, no default content transfer) | **Partially demonstrated.** Agent scope and filter isolation, immediate revocation, CSRF 403, content-sniffed upload validation, 404 on a foreign ID, and no provider calls (semantic search is off and nothing is configured). Cross-account isolation with real IDs, OAuth, and Telegram input boundaries were not covered. |
| 5. Unit/API tests, builds, browser journeys, migrations, deployment checks on the candidate | **Not demonstrated by me.** I did not run the test suites (out of scope; I made no source changes). Note: the working tree differs from the candidate (uncommitted edits by someone else), so suites run now would not test the candidate. |

## Findings

### Severe

None found in what I exercised.

### High

**H1. Mobile navigation drawer is not keyboard or screen-reader safe, and it cannot be dismissed except with its own X button.** (This is the most serious finding.)

At 390 px (and any width ≤ 800 px) the closed drawer stays in the accessibility tree and in the Tab order. After the skip link, Tab moves through "Dismiss navigation" at x=-69, then Inbox, All documents, Needs action, and the rest at x=-228: about 20 invisible controls before any content. Focus is invisible the whole time (m12).

When the drawer is open, focus stays on the menu button underneath it. Esc does not close it, and tapping the uncovered page area does not close it either (m4: class stays `sidebar sidebar-open`). A VoiceOver or TalkBack user swipes through hidden navigation on every screen, and a keyboard user on a tablet or narrow window loses track of focus.

- Repro: emulate a mobile device at 390x844, sign in, press Tab 8 times and log `document.activeElement.getBoundingClientRect().x`. Then tap "Toggle menu", press Escape, and tap at (370, 400). The drawer stays open.
- Cause: `HEAD:apps/web/src/App.tsx:1201`. `<aside className={\`sidebar ${menuOpen ? "sidebar-open" : ""}\`}>` has no `inert` or `aria-hidden` when closed, there is no Esc handler, no scrim or click-outside handler, and no focus move on open (line 1268 only toggles state). An uncommitted fix appears to be in progress in the working tree, but it is not in the candidate or the deployed bundle.

**H2. A folder source that cannot write to its folder makes a new full copy in `processed/` on every poll, with no limit.** (Upgraded from medium after a clean repro.)

`FolderBackend.move` uses `shutil.move`. When the source folder is not writable, the rename fails, `shutil.move` falls back to copy-then-unlink, and the unlink fails. The copy stays in `processed/`, the original stays in place, and the next poll copies it again under a `-<timestamp>` name. The document itself is imported only once (`biancospino` returns one document), so the problem is invisible in the Library. Only the source card shows "cannot move".

Wrong folder ownership is the common Synology setup mistake (UID 10001), so this can fill the NAS. With the default 1–15 minute polls and 30-day retention, that is up to about 43,000 copies of each file. Also, `processed/` sits at the root of the mount and is shared by every folder source, not inside each source's folder.

- Clean repro: at 11:41 I placed `r2j1-perm-probe.pdf` in `/sources/r2-judge1/sub/`, owned by uid 501 with mode 755, under an existing Folder source set to "Move it to a processed folder". At 11:45 `find /sources -name '*perm-probe*'` showed the original still in place plus three identical 29,387-byte copies: `processed/2026-11-18/sub/r2j1-perm-probe.pdf`, `…-1794998669.pdf`, and `…-1794998729.pdf`. That is one copy per poll. An earlier run left the same stray copy for `r2j1-watched-polizza.pdf`.
- Cause: `HEAD:services/api/archive/folder_source.py:110-118`. The fix is to use `os.rename`/`os.replace` only (same filesystem), or to delete the copy when the unlink fails, and to stop retrying the after-import action once it has failed.
- After the repro I gave my test folder the right owner (`chown`) to stop the loop.

### Medium

**M1. No document preview anywhere in the filing flow.**

The Library rows use a generic icon, and the document dialog has no thumbnail, page image, or embedded PDF. To check that a sender or date is right, the owner must open "Open searchable PDF" in another tab. On a phone, that means leaving the dialog for every document. Paperless shows thumbnails and a preview. A page-image endpoint already exists (`PagesPanel.tsx:256`, `/api/documents/<id>/pages/<n>.png`) but is used only in Pages & versions.

- Repro: open any document; there is no image of it (d06, m09).

**M2. Mobile Library puts capture and results below the first screen.**

On a 390x844 phone the hero, the three counters, the saved-searches card, the search box, sort, and Filters fill the first viewport. The first document row starts at about y=810 (m01). **Add** is a secondary button under Filters, and the desktop's primary "Add document" button is hidden. The `/` keyboard hint is shown on touch devices.

- Repro: sign in with mobile emulation and take a screenshot.

**M3. While offline, the Library shows "0 Documents / 0 Ready to find / 0 Being processed" with an empty list**, next to the "can't be reached" banner (m03). That reads like data loss. The last known list and counts should stay, marked as stale.

- Repro: on mobile, sign in, set the context offline, and add a photo.

### Low

- **L1.** Italian Backups screen shows the raw triggers "schedule" and "manual" for scheduled runs. The locale map uses the key `scheduled` but the API sends `schedule`: `HEAD:apps/web/src/locales/AppBackups.ts:13`. The raw Python error `[Errno 13] Permission denied: '/backup/staging'` is shown verbatim (`App.tsx:492`).
- **L2.** Hard-coded English after a cloud source OAuth connects: `“…” is connected. Use Preview to check the folder.` (`HEAD:apps/web/src/App.tsx:605`). The `?source_error=` and `?mail_error=` URL parameters are displayed as given. React escapes them, but anyone can craft a link that shows arbitrary text inside the app.
- **L3.** A tag cannot be created from the document dialog (sender and type can). A wrong learned suggestion cannot be dismissed.
- **L4.** In the search box, Esc does not blur, so j/k typed after Esc go into the query instead of moving through the Library.
- **L5.** No typo or fuzzy tolerance in search (`pervincx` gives 0 results).
- **L6.** The printed paper-copy sticker includes the location at print time (`d12`). After a move, the paper says the wrong shelf.
- **L7.** The Agents activity list does not name the document, although the docs say the document ID is recorded. Agent filters allow only one tag. For a titles-only grant, `X OR Y` returns nothing even when Y matches a title.
- **L8.** The Sources form's "Storage" `<select>` is wrapped in a label that includes every option's text, so its accessible name is "Storage S3-compatible storage WebDAV …". The same happens for the document dialog's "From" select (Playwright `getByLabel("Condominio")` matched the sender select).
- **L9.** Desktop sidebar at 900 px height: the Appearance select is cut off behind the user block, and Language needs an inner scroll (d01).
- **L11.** A new source defaults to "Move it to a processed folder" and deletes processed files after 30 days (`HEAD:apps/web/src/SourcesPanel.tsx:28`). For a NAS folder the owner already organises, the default removes their files from that folder; Ripiano does keep the original. "Leave the file and remember it" is listed first but is not the default.
- **L10.** Mixed date formats: "Nov 18, 2026" in lists, "11/18/2026, 10:48:27 AM" on the Overview and Sources cards.

## Most serious finding

**H1.** On mobile, the closed navigation drawer stays focusable and readable off-screen, about 20 invisible Tab stops before content. The open drawer does not take focus and cannot be closed with Esc or by tapping outside. This undermines the UX and accessibility dimension on exactly the platform (phone PWA) the product puts first.

## Cleanup

- All four round-2 agent grants I created were revoked.
- Created and left in judge1's own account: 9 new documents, 1 folder source ("R2 judge1 NAS folder"), sender "Acquedotto Mirto", type "Bolletta", 1 sticker, and 1 manual backup snapshot.
- Shared volume: `/sources/r2-judge1/` and my stray copies under `/sources/processed/2026-11-18/` (`r2j1-watched-polizza*` and `sub/r2j1-perm-probe*`), left in place as evidence for H2.
