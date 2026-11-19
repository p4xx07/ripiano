# Judge 3 — round 3 report (security and reliability emphasis)

- Candidate: `d8724ff32baa77fb5f58c35a49fa0ee933b75576` (branch `codex/initial-implementation`); running build at http://localhost:18080.
- Date: 2026-11-18. Account: `judge3` (admin). One disposable account `j3r3-tmp` was created for isolation tests and left deactivated.
- Browser: Playwright 1.64.1 driving Google Chrome 157.0.8103.79 (headless, `channel: "chrome"`); desktop 1440x900 and mobile emulation 390x844 (`isMobile`, `hasTouch`), English and Italian. HTTP and MCP calls with Node 26 `fetch`.
- Artifacts: `qa-artifacts/20261118-r3-judge-3/` (43 screenshots, token values masked, plus `scripts.tar` with every script).

## Result

| Dimension | Weight | Score |
| --- | ---: | ---: |
| Capture and filing friction | 25% | 8.5 |
| Retrieval and physical filing | 20% | 9.0 |
| UX and accessibility | 20% | 8.3 |
| Reliability and recovery | 20% | 8.5 |
| Privacy and agent control | 15% | 9.2 |
| **Weighted mean** | | **8.67** |

No severe or high finding. Five medium findings keep three dimensions below 9.0.

**Most serious finding (M1):** a file or photo chosen in Add while the session has ended is discarded without a word. The sign-in screen says only "You were signed out"; after signing in again the file is neither uploaded nor waiting on the device.

## Commands and scripts

All scripts are in `scripts.tar`. API scripts were run as `node <script>`; browser scripts as `node <script>` from `apps/web` (Playwright resolved with `createRequire`).

| Script | What it does |
| --- | --- |
| `lib.mjs`, `blib.mjs` | Session/CSRF client, upload and MCP helpers; Playwright launch, sign-in, navigation |
| `s1.mjs` | Anonymous access, CSRF, cookies, upload validation, scan-ID retry and 4-way concurrent retry, 26 MB upload, download headers |
| `s2.mjs` | Four agent grants (A text + tag filter, B tagger, C search only, D tag/filing + filter): tool lists, scope and filter enforcement, cross-agent tag guard, Origin check, Trash, revocation, audit |
| `s3.mjs` | API token create/use/blocked routes/revoke; disposable user: 55 direct-ID requests against my objects, view-only share, unshare, public link and revoke, deactivation |
| `s4.mjs` | Backup creation and concurrent start, retry of failed OCR, cancel then retry, original byte comparison, reprocess |
| `s5.mjs`, `s6.mjs` | Italian API messages; search-only agent against OCR text; security headers; Django admin |
| `b2`–`b6.mjs` | Desktop: 7-file upload, OCR/sender/date/tag/sticker search, one-screen correction, paper copy, move, history, missing/found, label, agent create and revoke |
| `b7.mjs` (`m-it`, `d-it`, `m-en`) | Every screen: horizontal overflow, small controls, text dump for translation review |
| `b8.mjs` (`d`, `m`), `b9.mjs` | Offline upload, offline reload, lost response, 503, ended session, sign-out with waiting files |
| `b10`–`b13.mjs` | Keyboard-only use, focus return, shortcuts, API token and backup screens, tag deletion, mobile camera/gallery/document dialog in Italian |

Unit tests: `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q -p no:cacheprovider -x` on the candidate code: all passed, 13 skipped (318 collected).

Fixtures used: `three-pages.pdf`, `judge.png`, `office-letter.docx`, `office-sheet.xlsx`, `email-notice.eml`, `outlook-notice.msg`, `barcode-batch-desktop.pdf`, `tag-barcode-desktop.pdf`.

## Dimensions

| Dimension | Evidence | Not exercisable |
| --- | --- | --- |
| Capture and filing friction (8.5) | Seven files in one Add (PDF, PNG, DOCX, XLSX, EML, MSG, one invalid): six added, the invalid one named with a reason, list updates to Ready by itself, nothing forces a visit to Inbox. Camera and gallery inputs on mobile (`capture=environment`, `image/*`). Date, new sender, new tag, sticker set in the document dialog. Held back by M2 and M1. | Real camera, Telegram, watched/consume folder (no access to the mount), Android scanner |
| Retrieval and physical filing (9.0) | OCR phrase, sender (plain and `sender:"…"`), `date:2026-03`, `date:2026-03-14`, `tag:`, combined query, sticker code in Library and in Paper archive (case-insensitive), move with history, mark missing/found with last known location, location contents, 70x40 mm label with QR. Only friction: L6. | Scanning a printed QR with a camera |
| UX and accessibility (8.3) | No horizontal overflow on any of 15 screens at 390 px; skip link, `/`, `n`, `?`, `g`+letter, `j`/`k`/Enter work; dialogs trap focus (45 stops, 0 outside) and return focus to the opener; Italian wording is natural on every screen read. Held back by M3, M4, M5, L1, L2. | Screen reader, installed PWAs, Android client |
| Reliability and recovery (8.5) | Offline: files wait on the device and are sent once on reconnect (desktop and mobile). Lost response: resent with the same scan ID, one document. 503: file kept, sent on the next retry. Four concurrent posts of one scan ID: one document. Cancel then retry: ready, original byte-identical. Backup from UI and API: complete in about 8 s, second start refused with 409. Held back by M1 and by the restore drill's gaps (hard gate 2). | Stopping the worker or services, restore (shared stack) |
| Privacy and agent control (9.2) | See below. | Semantic search (off), expiry by time |

### Agent, token, and account isolation (all passed)

- Tool lists match scopes exactly. A search-only agent gets 0 hits for an OCR phrase, cannot call `get_document_text` or `semantic_search`, and its results carry only title, status, dates, tags, sender, type.
- A tag-filtered agent sees only its tagged documents; other document IDs, and its own document once in Trash, return "not found within this grant".
- One agent cannot change what another reads: adding or removing another active agent's filter tag is refused, including inside a mixed request. Agent changes do not trigger "updated" workflows, so there is no indirect route.
- Revocation returns HTTP 401 on the next call. Agent tokens are refused on `/api`, API tokens on `/mcp`. A foreign `Origin` on `/mcp` gets 403.
- API tokens: 403 on account, session, agents, people, groups, object access, share links, bundles, email, mail, sources, workflows, backups; path tricks (`..`, `%2F`, `//`) do not bypass; revoked token gets 401.
- Disposable user: 404 or 403 on all 55 direct-ID requests against my documents, files, pages, notes, history, tags, agents; cannot use my tag as an agent filter; their agent cannot read my documents, even one shared with them. View-only share allows read and download only; unshare takes effect immediately. Deactivation ends their session, sign-in, and agent token at once.
- Uploads: empty, text-as-PDF, HTML-as-PNG, SVG, EXE, GIF, fake DOCX, 26 MB refused with clear messages; `../` and `<img onerror>` in file names are stored as plain text and never executed in any screen (no dialog fired in any run). Originals are served as attachments with `nosniff`.
- Headers on the app shell: CSP (`script-src 'self'`, `frame-ancestors 'none'`), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`. Session cookie is HttpOnly, SameSite=Lax. Posts without a CSRF token or with a foreign Origin get 403.

## Hard gates

| Gate | Status |
| --- | --- |
| 1. Parity rows have scenarios | Not verified row by row in this review; the rows I exercised (upload, formats, OCR, search, tags, paper copies, sharing, API tokens, agents, backup, Italian, shortcuts) work |
| 2. Install, upload/OCR/search, backup, clean restore | Partly demonstrated. Backup creation shown live. `.omo/evidence/restore-drill-20261118.md` is credible for originals and tags, but it ran on `f2b9416`, not this candidate, and by its own statement did not check locations or revoked grants |
| 3. Real devices | Out of scope by owner decision (D7): installed iOS/Android PWA, native Android capture, real Telegram/Google/Microsoft/Dropbox accounts, DS923+ checks |
| 4. Security review | Demonstrated for account and agent isolation, token revocation, CSRF, upload validation, and no transfer of content to a model provider by Ripiano itself. Sign-in throttling was read in code only (the per-address limit is shared by all judges on this stack) |
| 5. Tests, builds, journeys, migrations | Unit/API tests pass on the candidate. Production builds, the e2e suite, and deployment checks were not rerun by me |

## Findings

### Medium

**M1 — A file added after the session ended is lost silently.**
Repro: sign in, open Add, remove the `sessionid` cookie (or let the session expire, or sign out in another tab), choose a file or take a photo. The app shows the sign-in screen with "You were signed out". Sign in again: the file is not on the server, not in the waiting queue (IndexedDB `pending` is empty), and no report mentions it. Same on desktop and mobile (`m-34-session-expired-upload.png`, `m-34b-after-resignin.png`).
Cause: `apps/web/src/App.tsx:1337` keeps a file only when `isRetryable(status)` (0, 502, 503, 504); a 401 goes to the failure list, which the sign-in screen replaces. `uploadQueue.ts` already says a signed-out answer should keep the file, but that applies only to files already queued.

**M2 — Enter in "New sender name" or "New type name" closes the document dialog without creating the sender.**
Repro: open a document, choose "Add a sender", type a name, press Enter. The whole form is saved, the dialog closes, the sender does not exist and the typed name is gone (`d-08-enter-in-new-sender.png`). The tag field next to it handles Enter correctly.
Cause: `apps/web/src/DocumentPanel.tsx:583` and `:595` have no `onKeyDown`; the tag input at `:664-667` does.

**M3 — A tag that was ever an agent's document filter cannot be deleted, and the message is wrong.**
Repro: create a tag, create an agent limited to it, revoke the agent, then Tags & filing → Delete the tag → confirm. Result: "Move or delete child tags first" (Italian: "Prima sposta o elimina le sottoetichette") although the tag has no children (`d-22-delete-filter-tag-en.png`, `-it.png`). Revoked grants cannot be removed, so the tag can never be deleted.
Cause: `services/api/archive/models.py:463` (`filter_tag … on_delete=PROTECT`) and `metadata_views.py:432-433`, which answers every `ProtectedError` with the child-tag message.

**M4 — Processing errors stay in English in the Italian interface.**
Repro: Italian interface with one failed document. Library, Inbox, and Overview show "L'OCR non è riuscito a terminare: Text recognition failed for this file. Check that it opens correctly, then choose Retry OCR. Details are in the worker log." (`m-it-scr-in-arrivo.png`, `d-it-scr-panoramica.png`). `GET /api/documents`, `/api/jobs` with `Accept-Language: it` return the English text.
Cause: the Italian text exists in `messages_it.py:6`, but `api_language.py` translates only the top-level `error` of a response, not a document's stored `error` field. "Details are in the worker log" is also no help to a non-technical person.

**M5 — Rename, share, and delete icons for senders and types are 28x21 px on a phone.**
Repro: mobile 390 px → Tags & filing → Senders and organizations. The three icon buttons measure 28x21 CSS px and sit side by side, delete next to share (`m-it-10-senders-small-buttons.png`). In the mobile document dialog the three download links are 17 px tall.

### Low

- **L1** After `j`/`k` + Enter opens a document, Esc returns focus to `<main>`, not the highlighted row (opening with Tab + Enter returns focus correctly).
- **L2** Tag, sender, and type deletion use the browser's native `confirm()`, unlike the inline confirmations elsewhere.
- **L3** A call refused for a missing scope is logged without the document ID (`mcp_server.py:299-301`), while `docs/AGENT_ACCESS.md` says refused requests still name the document.
- **L4** An API token can move a document to Trash and delete it permanently. This matches "acts with your access" but not the code comment's "can read and file".
- **L5** No `Strict-Transport-Security` setting in `settings.py`; `nginx.conf` forwards the client's own `X-Forwarded-Proto` to Django. Authenticated downloads carry no `Cache-Control`.
- **L6** `date:14/03/2026` is refused (with a clear hint to use `2026-03-14`); day-first dates are what an Italian user types.
- **L7** A failed CSRF check and unknown `/api/` routes answer with Django's HTML page instead of JSON; anonymous `/api/agents` and `/api/backups` answer 403 "Owner access required" where other routes answer 401.
- **L8** The user guide says API tokens last 7–365 days; the API accepts 1 day.
- **L9** Every admin can open Django's `/admin/` (users and groups), which bypasses the People screen's rule that another admin's password cannot be changed.
- **L10** The restore drill should be rerun on the candidate and extended to locations and revoked grants (hard gate 2).

## Data left on the stack

Under `judge3`: about 30 test documents (titles starting `j3r3-`, `j3b-`, `j3off-`, `j3lost-`, `j3bad-`, `j3so-`, `j3m-`), tags `j3r3-*` and `j3b-tag-*`, sender `J3B Sender …`, one paper copy, five manual backups. All my agent grants and API tokens are revoked. User `j3r3-tmp` is deactivated.
