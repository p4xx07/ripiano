# Judge 3 — round 4 report

- Candidate SHA: `b57e14e6c529d7fdeb5b9b7ff6b023d28fe88a7b` (branch `codex/initial-implementation`); line references checked with `git show HEAD:<path>`.
- Date: 2026-11-18
- Reviewer focus: security and reliability (agent grants, scopes and revocation over MCP; API tokens; isolation between accounts; upload validation; interrupted and retried uploads; security headers; backups). All five dimensions are scored.
- Stack: http://localhost:18080 (shared). Account `judge3`, plus one disposable account `j3r4x83329` that I created for isolation tests. I deactivated it afterwards.
- Browser: Playwright `Version 1.64.1` (`npx playwright --version`), Chrome channel `157.0.8103.79`. Desktop 1440x900 (en-US). Mobile emulation 390x844 with `isMobile`, `hasTouch` and DPR 2, in en-US and it-IT.
- Artifacts: `qa-artifacts/20261118-r4-judge-3/` (17 screenshots plus `scripts/`). Agent tokens are masked in the screenshots. Scripts read the password from judges.env at run time and do not contain it.

## Commands and scripts run

Each script was run from the scratch folder as `node <script>.mjs`. Playwright was imported by absolute path from `apps/web/node_modules/@playwright/test/index.mjs`. Copies are in `qa-artifacts/20261118-r4-judge-3/scripts/`.

| Script | What it does |
| --- | --- |
| `t2.mjs` | Upload validation: empty file, HTML named .pdf, SVG named .png, truncated PDF, path-traversal file name, and a bad ZIP named .docx. Uploads all 15 fixtures with web scan IDs. Re-sends one scan ID (a lost response), then sends 4 uploads at once with one scan ID. |
| `t4.mjs` | Three MCP grants: A (search+text+tag, filter tag A), B (search only, filter tag B), C (search+tag+filing, no filter). Checks `tools/list` for each, the scope and filter results, and cross-agent tag changes. Also tests no token, an API token sent to MCP, a foreign Origin, revoking A, and the audit log. |
| `t5.mjs`, `t6.mjs` | Creates the disposable user and shares one document with view access and one with edit access. Tests that user's access to shared and unshared documents, re-sharing, share links, trash and purge, bulk actions, a foreign filter tag, and their own agent and API token (blocked routes, revocation). Tests CSRF without the header and with a foreign Origin, then removes the share. |
| `t7.mjs` | Manual backup, a second click while it is pending, polling, and a retry of the failed (truncated) PDF. |
| `t8.mjs` | Cookie flags. Headers on original, archive, page preview and export downloads. Share link create, fetch and revoke. Password change: what happens to API tokens and agent grants. Deactivating a person: their session and agent. Sign-in throttling. |
| `t10.mjs` | Cancel, retry and reprocess, then a SHA-256 check that the original is unchanged. Search for an OCR phrase, a tag, and email/msg subjects. |
| `t11.mjs` | Decompression-bomb PNG headers (100000² and 15000²) and a 26 MB upload. |
| `t12.mjs` | Shelf and nested box, a paper copy, sticker lookup, moving the copy, history, the printable label, and search by sticker. |
| `offline.mjs` | Browser: upload while `context.setOffline(true)`, then back online. Lost response: the route lets the server store the file, then aborts the answer to the browser. Then counts the copies on the server and the entries left in IndexedDB. |
| `ui.mjs`, `ui2.mjs`, `ui3.mjs` | Desktop: create an agent, view the audit log, revoke with confirmation. Screens for Security, Backups and People. `/` search and Tab order. Agent form reachable by keyboard. Mobile it-IT: Library and Agents, horizontal overflow, English text left over, target sizes. Desktop and mobile: sticker search, open the document, focus on open and after Escape. |

Fixture IDs used (from `apps/web/e2e/fixtures/`): all 15 — asn-batch-desktop.pdf, asn-batch-mobile.pdf, barcode-batch-desktop.pdf, barcode-batch-mobile.pdf, email-notice.eml, judge.png, office-legacy.doc, office-letter.docx, office-open.odt, office-sheet.xlsx, office-slides.pptx, outlook-notice.msg, tag-barcode-desktop.pdf, tag-barcode-mobile.pdf, three-pages.pdf. I also used generated inputs: an empty file, HTML, SVG, a truncated PDF, a bad ZIP, PNG bomb headers, and 26 MB of random bytes.

## Observed results (summary)

- **Uploads:** all 15 fixtures reached `ready`. Empty, HTML, SVG and bad-ZIP files were refused with 400 and a clear message. A file over 25 MB got 413. The path-traversal name was reduced to the title `j3r4-trav`. The truncated PDF went to `failed` with a readable message, and Retry fails it again cleanly.
- **Lost responses and retries:**
  - Re-sending a scan ID returned 200 with the same document.
  - Four uploads sent at once with one scan ID gave one 202 and three 200s, all for the same document ID.
  - In the browser, an upload made offline was queued with the banner "1 file is waiting to upload… Try now". It was sent when the connection came back.
  - When the server stored a file and the answer was dropped, the file was kept and retried, and the server recognised it. Exactly one copy of each exists on the server, and IndexedDB was empty at the end.
- **Agents (MCP):**
  - `tools/list` follows the scopes exactly: B gets only `search_documents`.
  - Filters hold: A sees only the documents tagged A, B only those tagged B, and A gets "Document not found within this grant" for B's document.
  - B is denied `get_document_text`, and searching OCR text returns nothing for it.
  - Cross-agent tag changes are refused: C cannot add A's tag or remove B's, and A cannot add B's tag.
  - Revocation takes effect immediately (401 on list and call) and does not affect other agents.
  - No token, an `rip_` API token, and a foreign Origin get 401, 401 and 403.
  - Audit entries show agent, action, outcome and document.
- **Isolation between accounts:**
  - A view-level user can read and download the shared document only. They get 403 on edit and notes. Unshared documents, share links, re-sharing, trash and bulk actions return 404 or "not found".
  - That user's own agent cannot see documents shared with them.
  - They cannot create an agent with my tag as its filter, or revoke my agent (404).
  - Removing the share ends their access at once.
- **API tokens:** blocked from `/api/agents` (with or without a trailing slash), `/api/agents/events`, creating tokens, share links and backups (403). A revoked token gets 401, and a password change revokes all tokens.
- **CSRF, cookies and headers:**
  - A session POST without the CSRF header, or with a foreign Origin, gets 403.
  - The session cookie is HttpOnly and SameSite=Lax. It has no Secure flag only because this stack runs `RIPIANO_DEBUG=1`; Compose defaults to 0.
  - The PWA sends CSP, X-Frame-Options DENY, nosniff, Referrer-Policy and Permissions-Policy. API responses send nosniff, DENY and COOP.
  - Originals download as an attachment. Share links are `no-store` and `no-referrer`, and a revoked link gets 404.
  - Sign-in is throttled after 10 failures (429).
- **Backups:** a manual backup completed in about 9 s (snapshot `20261118T164038255685Z-2ad6fd34`). A second click while it was pending got 409 with the existing run. Reprocessing kept the original byte-identical (SHA-256 match).
- **Physical filing:** shelf with a nested box, paper copy with sticker `R-…`, lookup and search by sticker, move with history (2 entries), and an HTML label all work. The document dialog shows the shelf and sticker on desktop and mobile.
- **UX checks:**
  - `/` focuses search. Opening a document moves focus to Close, and Escape returns focus to the row.
  - The agent form can be reached in order with Tab, and every control has a label.
  - Italian Agents screen: no English text left over. Mobile: no horizontal overflow.
  - No page errors or console errors in any browser run.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 8.8 | All 15 formats reach `ready` with no TODO step. Offline queue and lost-response retries work without duplicates. Validation messages are clear. Docked: a very large image gives a 500 error page instead of a message (finding M1). | Camera scan on real phones, Telegram, real cloud drives (owner decision D7). I did not run the watched folder myself. |
| Retrieval and physical filing | 20% | 9.0 | OCR phrase ("otter"), tag, email/msg subjects and sticker searches all hit. Nested location, moving a copy, history and the printable label work. | Printing and re-scanning a sticker with a camera; I used the lookup endpoint and the search box instead. |
| UX and accessibility | 20% | 8.8 | Keyboard paths and focus handling work, controls are labelled, Italian coverage is complete, nothing overflows on mobile, and there were no console errors. Small friction: mobile text inputs are about 37 px high; during a lost-response retry the document is listed and also counted as "waiting" (L1). | Installed iOS/Android PWA and native Android (D7). I ran no screen reader; checks used accessibility names only. |
| Reliability and recovery | 20% | 8.9 | Offline, lost-response and concurrent upload paths each keep exactly one copy. The backup completes and a second backup cannot start while one is pending. Retry and reprocess keep the original intact. The restore drill (`.omo/evidence/restore-drill-round4.md`, same SHA) is credible. Docked: the 500 in M1. | Killing or restarting the worker and services myself (shared stack). I read the code: `acks_late`, prefetch 1 and the stale-job reconcilers. |
| Privacy and agent control | 15% | 8.8 | Scopes, document filters and cross-agent tag protection held. Revocation is immediate, other accounts are isolated, and the audit log works. Docked: agent grants can be created without re-entering the password and survive a password change (M2). | A real cloud MCP client; the protocol was exercised directly instead. |

**Weighted mean: 0.25·8.8 + 0.20·9.0 + 0.20·8.8 + 0.20·8.9 + 0.15·8.8 = 8.86**

## Hard gates

| Gate | Status in this review |
| --- | --- |
| 1. Parity: every row has a scenario or accepted deviation | Not demonstrated row by row by me. The rows I exercised (upload, Office, email, search, tags, physical copies, sharing, share links, tokens, agents, backups) work. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Demonstrated. Backup creation and upload/OCR/search in my own run; install and restore from the credible same-SHA drill in `.omo/evidence/restore-drill-round4.md`, which covers originals, tags, locations and revoked grants. |
| 3. Installed iOS/Android PWA, native Android capture, interrupted uploads on real devices | Out of scope by owner decision (D7). Interrupted uploads passed in browser emulation. |
| 4. Security review | Largely demonstrated. Passed: isolation between accounts and between agents, token revocation, CSRF, upload validation, and no default transfer of content to model providers (B without text scope sees no text). Two medium findings remain open (M1, M2). |
| 5. Unit/API tests, builds, journeys, migrations, deploy checks on the candidate | Not run by me. |
| Owner NAS checks (performance, ACLs, restore on the DS923+), real Telegram/Google/Microsoft/Dropbox | Out of scope by owner decision (D7). |

## Findings

### Severe
None.

### High
None.

### Medium

**M1 — Oversized-image upload gives a 500 error page instead of a validation message.**
- **Repro:** upload a PNG whose header says 15000×15000 or 100000×100000; any real image above about 179 MP does the same. Script: `t11.mjs`. `POST /api/documents` → 500 `DecompressionBombError`, a traceback page while DEBUG is on.
- **Cause:** `services/api/archive/storage.py:55-59`. `Image.open()` raises `PIL.Image.DecompressionBombError`, which is not caught by the `except (UnidentifiedImageError, OSError, ValueError)` clause.
- **Effect:** the temp file is removed (`finally` in `storage.py`), so nothing leaks. But the web uploader reports a generic failure with no explanation, because a 500 is neither queued nor shown with a reason. A real large-format scan, such as a 600 dpi A1/A0 poster, would hit this.
- **Gap:** images between about 89 and 179 MP are accepted with only a warning and go on to OCR. There is no pixel limit for the NAS's RAM.
- **Fix:** catch `Image.DecompressionBombError` (and its warning) and return a 400 with the pixel limit.

**M2 — Agent grants need no password confirmation and survive a password change.**
- **Repro:** with a session, call `POST /api/agents` with `{"name":"x","scopes":["documents:search","documents:text"]}`. You get 201 and an `rpa_` token without entering the password. Then change the password (`POST /api/account/password`): API tokens get 401, but the agent token still gets 200 on `tools/list` (script: `t8.mjs`, `agentAfterPwChange: 200`).
- **Cause:** `services/api/archive/agent_views.py:41-84` has no `check_password`, unlike `api_tokens.py:107`. `revoke_tokens_on_password_change` (`api_tokens.py:44`) revokes only `ApiToken` rows.
- **Effect:** someone who has a stolen session or password can mint a read-all-text agent token valid for up to 365 days. Changing the password, the usual recovery step, does not cut it off. The owner has to notice it on the Agents screen. API tokens are protected against exactly this.
- **Fix:** require the current password when creating a grant, and offer (or default to) revoking agent grants on a password change.

### Low

- **L1 — Lost-response retry shows the document twice in the UI for a while.** During a lost-response retry the document is already listed, and the banner also says "1 file is waiting to upload" (screenshot `04-lost-response-waiting.png`). It settles on the next retry with no duplicate, but a non-technical user may tap "Try now" or upload again.
- **L2 — Denied calls are not linked to the document in the audit log.** An agent's call to a tool outside its scope is logged as `denied` without the `document_id` it probed (`mcp_server.py:300`). Probes that pass the scope check do link the document.
- **L3 — `list_tags` ignores the grant's filter tag.** An agent limited to one tag still lists every tag name, including other agents' filter tags (`mcp_server.py:185`). This is metadata only.
- **L4 — Filter tags can be offered as suggestions.** Learned suggestions can propose a tag that is another agent's filter tag (screenshot `14-mobile-document.png`, "Add tag: j3-agent-ok"). Accepting it quietly widens that agent's view. Marking such tags in the suggestion would help.
- **L5 — Every account can list every username.** Any non-admin account can list all 41 usernames and display names through `GET /api/people`, for the sharing picker. This matches Paperless, but is worth knowing for a family deployment.
- **L6 — Pixel-limit gap.** Already covered under M1: images between about 89 and 179 MP pass validation and go to OCR with no RAM-aware limit.
- **L7 — Upload error handling.** On the first upload, a 500 or 429 is shown as a failure and the file is not kept (`apps/web/src/uploadQueue.ts:77`, `App.tsx:1337`). The retry loop, by contrast, keeps the file. This is acceptable but inconsistent.
- **L8 — Quickstart DEBUG default.** `.env.example` uses `RIPIANO_DEBUG=1` for quickstart. A LAN install copied from it would expose traceback pages; I saw one for M1. Compose defaults are safe.

## Single most serious finding

**M2:** an agent token that can read all text can be created from a session without the password, and it survives a password change. A stolen session or password therefore gives up to 365 days of access that the usual recovery step does not end.
