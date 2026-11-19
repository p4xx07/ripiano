# Judge 3 — round 5 report

- **Candidate SHA:** `95e6f6d4d0893157ae63cb33541e6b5d53636dd7` (branch `codex/initial-implementation`); file:line references verified with `git show HEAD:<path>`.
- **Date:** 2026-11-18
- **Reviewer:** Judge 3 (account `judge3`, an admin on the shared stack). Emphasis: security and reliability.
- **Stack:** http://localhost:18080 (nginx 1.27.5 → gunicorn API, MCP at `/mcp`, OCR worker, maintenance worker, scheduler). The local stack runs with `RIPIANO_DEBUG=1` (needed for plain HTTP; Django's debug CSRF page is visible). Production settings turn this off (`settings.py:8,91-92`), so I did not count it against the product.
- **Browser:** Playwright `Version 1.64.1`, Google Chrome `157.0.8103.79` (channel `chrome`). Desktop 1440×900; mobile emulation 390×844 (`iPhone 13` descriptor, `isMobile`, `hasTouch`), `it-IT` and `en-US` locales; keyboard-only run on desktop.
- **Artifacts:** `qa-artifacts/20261118-r5-judge-3/` (12 PNGs; agent token field masked in `05-…`). The scripts are in my scratch folder outside the repo (`…/scratchpad/j3r5/`). The token files were deleted after the run.

## Commands and scripts run

All scripts were run with `node <script>` from the scratch folder. HTTP calls use Node `fetch` (session cookie + CSRF header, or a `Token`/`Bearer` header). Playwright is imported by absolute path from `apps/web/node_modules`.

| Script | What it does |
| --- | --- |
| `lib.mjs` | Session helper (GET then POST `/api/session`, CSRF header, Origin), plus MCP JSON-RPC helpers (`initialize`, `tools/list`, `tools/call` on `POST /mcp`). |
| `agents.mjs` | Creates tags `j3r5-filterA-*` and `j3r5-ord-*` and puts the filter tag on one document. Creates grants A (search+text, filter tag), B (search+tag, no filter) and C (search only), and tries a wrong password. Runs `tools/list` for each grant. Then: A reads a document inside and outside its filter; A calls a tool it lacks; B tries to add/remove A's filter tag and adds an ordinary tag; B reads text without the scope; C runs a title-only search. Tries to delete and rename the filter tag. Sends no token, a bogus token, and a foreign Origin. Revokes B, checks the next call, and reads the activity log. |
| `iso.mjs`, `iso2.mjs`, `iso3.mjs`, `iso4.mjs` | Creates one disposable user via `POST /api/people`. Runs 16 GET and 10 mutation probes against another account's document. Shares one document view-only and probes it. The new user's agent reaches for the shared document; the user tries another account's tag as a filter. Tests API-token scopes, CSRF without a token and with a foreign Origin, a self password change (second device, token, agent), an admin password reset, and account off/on. Tests the workflow `share_with` action with run-now, its validation (self, missing person), history, and cleanup. |
| `up.mjs`, `poll.mjs` | Upload validation with 12 generated cases (see below), then polls processing status and `/api/jobs`. |
| `idem.mjs` | Three concurrent uploads with the same `X-Ripiano-Scan-ID`, a retry, a re-upload without a scan ID (duplicate detection), and an invalid scan ID. |
| `cr.mjs` | Queues 4 Office/email fixtures, then cancel-processing, a second cancel, retry, and a second retry. Tries credential confusion (agent token on the REST API, API token on MCP, revoked API token), a 5 MB MCP body, malformed JSON, and agent expiry/scope bounds. |
| `sh.mjs` | Public share link: anonymous fetch, tampered token, link after Trash and after restore. Agent visibility after Trash/restore, after untagging, and with only a child of the filter tag. |
| `bk.mjs` | Backup as non-admin, two concurrent manual backups, backup completion, and API/original response headers. |
| `find.mjs` | Retrieval checks: OCR/email phrase, `tag:`, `date:`, title. |
| `ui1.mjs` | Desktop: offline upload and reconnect; lost response (`route.fetch()` reaches the server, then the response is aborted to the client); over-cap image in the UI; Agents screen. |
| `ui2.mjs` | Desktop keyboard only: sign in, Tab to Agents, create an agent with Space/typing/Enter, revoke with Enter. Mobile Italian: Agents, People, and Security screens, plus a horizontal-scroll check. |
| `ui3.mjs` | Mobile Italian: mixed batch (damaged PNG, random bytes named `.pdf`, a valid `.odt`); offline upload, reload while offline, reconnect; Backups screen. |
| `clean.mjs` | Revokes every `j3r5-*` agent and turns off the disposable user. |

## Fixture IDs used

`three-pages.pdf`, `judge.png`, `office-letter.docx`, `office-open.odt`, `office-sheet.xlsx`, `office-slides.pptx`, `email-notice.eml`, `outlook-notice.msg`.

I also used derivatives generated from them:
- `truncated-three-pages.pdf`: the first half of `three-pages.pdf`.
- `corrupt-png-body.png`: the first 200 bytes of `judge.png` plus random bytes.
- `three-pages.pdf` with a unique trailing comment, for the scan-ID, lost-response, path-traversal-name and 24 MB cases.

Fully synthetic inputs: PNG headers of 100000×100000, and real 8000×8000 and 7000×7000 grayscale PNGs; 4 KB of random bytes named `.pdf`; HTML named `.pdf`; an SVG with a script; an empty file; and a 27 MB file.

## Results by area (what I actually observed)

**Agent grants, scopes, isolation, revocation (MCP):**
- `tools/list` matched each grant exactly: A got `search_documents` and `get_document_text`; B got `search_documents`, `list_tags` and `change_document_tags`; C got `search_documents`.
- A sees only documents carrying its filter tag. A document outside the filter returns "Document not found within this grant". A tool outside the scope returns "Tool is not permitted for this agent".
- Agent B **cannot add or remove A's filter tag** ("This tag limits another agent's access; only a person can add or remove it"). B can still add ordinary tags.
- A document carrying only a child of A's filter tag stays invisible to A. A trashed document disappears from A's view and comes back on restore. Removing the tag by hand removes access immediately.
- Agent tag changes do not fire "updated" workflows (`views.py:1058` is the only caller), so one agent cannot use a workflow to widen another's view.
- The filter tag cannot be deleted while a grant uses it (409 "Revoke agents using this tag before deleting it"; FK is `PROTECT`).
- Creating a grant requires the password (wrong password → 400). Expiry outside 1–365, a boolean, or a string is rejected. Duplicate or unknown scopes are rejected.
- No token, a bogus token, an API token (`rip_`) on MCP, and a revoked grant all get 401. A foreign Origin gets 403. A 5 MB body gets 413, and malformed JSON gets 400.
- The activity log records each call with its outcome. One gap: scope-denied calls lose the document ID (L1).
- Another user's agent cannot read a document shared with that user (owner-only `_documents`). That user cannot use another account's tag as a filter.

**Password change and account state:**
- A self password change revoked that user's API token and agent (both 401). It signed out the second device and kept the current one.
- An admin reset revoked the token and agent created after it.
- Turning the account off blocked session, token and agent (401). **Turning it back on revived the token and agent** (M2).
- Neither password-change message tells the person that every agent was disconnected (M1).

**API tokens:**
- With a token: `/api/documents` 200. Agents, account tokens, people, workflows, backups and share-link creation all 403. Another account's document 404; a document shared with the token's user 200.
- An agent token used as `Token`/`Bearer` on the REST API gets 401. Revoking a token gives 401 immediately.

**Sharing isolation:**
- An unshared document from another account returns 404 on all 16 GET sub-resources: detail, original, archive, pages, page PNG, export, history, notes, shares, copies, versions, similar, access, suggestions, custom fields, links.
- All 10 mutations return 404 (one export method returns 405). Search returns 0 hits.
- With view-only sharing: GET and original 200, PATCH 403. Trash, share link, access, purge and email all 404.
- Workflow `share_with` + run now granted view access and recorded an `access` history entry. It rejects sharing with yourself and with a missing person. Another user cannot edit or run the workflow (404). Removing the grant removes access.

**CSRF and headers:**
- A cookie POST without a CSRF token gets 403; a foreign Origin with a token gets 403.
- PWA: strict CSP (`script-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`), XFO DENY, nosniff, `Referrer-Policy: same-origin`, a Permissions-Policy, and COOP on the API. Session cookie HttpOnly and SameSite=Lax.
- Originals use `Content-Disposition: attachment`. Share links send `no-store`. Authenticated API JSON and originals send no Cache-Control (L2).
- HSTS and Secure cookies are not testable on plain HTTP; production sets them.

**Upload validation:**
- 100000×100000 header-only PNG: 400 in 13 ms, with a clear 50 MP message (English and Italian in the UI).
- Real 8000×8000 PNG: 400. Real 7000×7000 PNG: 202, then ready.
- Truncated PDF: 202, repaired, ready.
- Damaged PNG and random bytes or HTML named `.pdf`: 400 with plain-language reasons. SVG: 400. Empty file: 400.
- `../../../etc/…pdf` is stored as a basename.
- 27 MB: JSON 413 "File exceeds the upload limit". 24 MB: 202, then ready.
- A mixed batch on Italian mobile reported "2 file su 3 non sono stati aggiunti" with a reason for each file and added the valid one (screenshot 09).

**Interrupted, retried and lost uploads:**
- Desktop and mobile offline uploads show "1 file is waiting to upload". Reloading while offline shows "Sei offline". On reconnect the file is sent (202) and nothing is left behind.
- Lost response: the server stored the file and the client saw a connection reset. The app kept the file as waiting and resent it with the same scan ID, so exactly **one** document exists (screenshot 02).
- Three concurrent POSTs with one scan ID gave 202/200/200 for the same document. A retry gave 200 for the same document. Without a scan ID, the re-upload is flagged `duplicate_of`.
- Cancel-processing on a queued document → failed. A second cancel → 409. Retry → pending, then ready. A second retry → 409.
- I could not restart workers or containers (forbidden by the brief).

**Backup:**
- Non-admin: 403.
- Two concurrent manual requests gave 202 + 409 (single flight). The snapshot `20261118T173852640653Z-9d73d68d` completed in about 10 s.
- I did not perform a restore. `.omo/evidence/restore-drill-round5.md` did not exist when I finished, so I count no restore evidence.

**UX and accessibility (security screens):**
- Keyboard only: the skip link comes first. Agents is reachable by Tab. After navigation, focus lands at the screen so the next Tab reaches **Name**. Every control has a label. Space toggles scopes. Enter creates the token, and focus moves to the token notice. Revoke uses a two-step confirmation by Enter. Focus is visible (3 px outline plus ring).
- Italian is complete on Agents, People, Security, Backups and upload errors.
- No horizontal scroll at 390 px.

**Retrieval (light check):**
- `lampone` and `mirtillo` (email body/subject), `tag:j3r5-child-…` and `condominio date:2026-11` returned the right documents with snippets in 30–115 ms.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | Desktop and mobile web upload of PDF, PNG, DOCX, ODT, XLSX, PPTX, EML and MSG. Offline queue, lost-response dedupe, mixed batch with clear per-file reasons, scan-ID idempotency, duplicate flagging (screenshots 01–03, 09–11). | Camera capture, Telegram and watched folder were not run by me; the Telegram account and real devices are out of scope by owner decision. I did not exercise correcting an uncertain suggestion. |
| Retrieval and physical filing | 20% | 9.0 | Phrase, tag, date and title searches correct and fast; snippets shown. | Sticker scan, moving a paper copy, and label print/re-scan were not exercised by me (outside my emphasis). Mobile list titles truncate early (L5). |
| UX and accessibility | 20% | 8.9 | Keyboard-only agent create and revoke works with visible focus and sensible focus moves. Italian is complete; no horizontal scroll on mobile (05–08, 12). | No screen-reader run. Installed iOS/Android PWA and the native client are out of scope by owner decision. Deductions: M1 messaging, clutter of revoked agents (L3), early title truncation (L5). |
| Reliability and recovery | 20% | 9.2 | Offline and lost-response uploads, concurrent scan-ID races, cancel/retry state machine, damaged/oversized files, single-flight backup that completed. | Worker or service restart and the clean-stack restore were not exercisable by me (no container restarts allowed; round-5 drill file absent). Small open concern: L4. |
| Privacy and agent control | 15% | 9.0 | Every agent isolation, scope, filter, revocation and credential-confusion probe passed. Agent B cannot change A's view. Password change revokes agents. Sharing isolation holds across accounts. | No real cloud agent; tested by direct MCP calls. Deductions: M2 (reactivation revives credentials), M1, and L1 (audit). |

**Weighted mean:** 0.25×9.0 + 0.20×9.0 + 0.20×8.9 + 0.20×9.2 + 0.15×9.0 = 2.25 + 1.80 + 1.78 + 1.84 + 1.35 = **9.02**

## Hard gates

| Gate | Demonstrated? | Notes |
| --- | --- | --- |
| 1. Parity: every capability has a scenario or an accepted deviation | Partially | I checked only the security-related rows (agents, tokens, sharing, workflows share action, upload validation). I did not audit the matrix row by row. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Partially | Upload/OCR/search and backup creation passed live. Restore was not demonstrated: `.omo/evidence/restore-drill-round5.md` was absent at report time, and I cannot restart the stack. |
| 3. Installed iOS/Android PWA and native Android on real devices | Out of scope by owner decision | Not exercised; no score lowered for it. Synology DS923+ checks and real Telegram/Google/Microsoft/Dropbox accounts are likewise out of scope by owner decision. |
| 4. Security review: isolation, token revocation, CSRF, upload validation, external input boundaries, no default model transfer | Yes, with findings M2 and L1 | Account and agent isolation, revocation, CSRF, upload validation, MCP Origin and size limits, and API-token boundaries all passed. Ripiano makes no outbound model call in anything I exercised. |
| 5. Unit/API tests, builds, browser journeys, migrations, deployment checks on the candidate | Not demonstrated by me | I did not run the test suites; my own Playwright journeys passed against the running build. |

## Findings

### Severe
None.

### High
None.

### Medium

**M1. Changing a password silently disconnects every agent; the UI neither warns nor reports it.**
- Repro:
  1. Create an agent under Agents and connect it to MCP.
  2. Security → Password → change the password.
  3. The success message reads "Password changed. Your other devices and API tokens were signed out." (Italian: "…Gli altri dispositivi e i token API sono stati disconnessi.").
  4. The agent's next MCP call returns 401, and Agents shows it as Revoked.
  5. An admin reset says the same ("Their other sessions and API tokens ended").
- Cause:
  - The behavior is intended (`services/api/archive/api_tokens.py:56-59`, documented in `docs/AGENT_ACCESS.md`).
  - The message omits agents: `apps/web/src/locales/PasswordPanel.ts:5,16` and `apps/web/src/locales/PeoplePanel.ts:21,74`.
  - The form shows no warning before submitting (`apps/web/src/PasswordPanel.tsx:40-46`).
- Impact: a non-technical owner's Claude or local classifier stops working with no explanation at the moment of the change.

**M2. Turning an account back on revives all of its API tokens and agent grants.**
- Repro (`iso2.mjs`):
  1. As a disposable user, create an agent and an API token; both work (200).
  2. An admin turns the account off: agent, token and session all return 401.
  3. The admin turns it back on: **the same agent token and API token return 200 again**.
- Cause:
  - Turning an account off only flips `is_active` (`services/api/archive/people_views.py:164`).
  - Grants and tokens are only gated on `owner.is_active` (`services/api/archive/mcp_server.py:91`, `services/api/archive/api_tokens.py:81`).
  - Nothing revokes them when the account is turned off.
- Impact: an admin who turns off a suspected-compromised account and later re-enables it, without also resetting its password, brings back every leaked long-lived credential (up to 365 days). Suggest revoking tokens and grants when `is_active` goes false, or at least warning on reactivation.

### Low

**L1. Scope-denied MCP calls drop the document from the activity log, contrary to the docs.**
- Repro: grant A (no tag scope) calls `change_document_tags` with a `document_id`. `/api/agents/events` shows `change_document_tags - denied` with `document_id: null`.
- Cause: `services/api/archive/mcp_server.py:300` creates the audit row without the document.
- `docs/AGENT_ACCESS.md:28` says "Requests an agent was refused still name the document". That holds only for in-scope refusals (lines 303-309).

**L2. Authenticated API JSON and `/original` downloads carry no `Cache-Control: private, no-store`.**
- Only share links do (`bk.mjs` output).
- Low risk because of same-origin and cookie auth, but on a shared family device document metadata and originals can sit in the HTTP cache after sign-out.

**L3. Revoked agents accumulate forever in "Connected agents" with no way to hide or delete them.**
- Screenshot `04-agents-desktop.png`: active and revoked cards are interleaved.
- This makes it harder to see at a glance which agents can still read the archive.

**L4. The offline resend loop keeps a file forever on any 5xx.**
- `apps/web/src/App.tsx:1427-1429` with `uploadQueue.isRefusal` (`apps/web/src/uploadQueue.ts:82`).
- A file that always triggers a 500 is retried every 60 s (`App.tsx:1447`) with no attempt limit or per-file message.
- Found by reading the code; I did not reproduce it.

**L5. Mobile Library titles ellipsize early.**
- "Avviso condominio …" and "Avviso TARI 2026 la…" are cut even though the row has room for the full title.
- Screenshot `09-mobile-it-damaged-batch.png`.

**L6. (Environment, not scored) The judging stack runs with `RIPIANO_DEBUG=1`, so Django's debug CSRF page is served.**
- Production settings turn this off (`services/api/ripiano/settings.py:8`).

## Most serious finding

**M2:** reactivating a turned-off account silently revives every API token and agent grant it had. The kill switch an admin would reach for during a suspected compromise is reversible in a way that brings leaked credentials back.

## Independence note

One `git grep` over the repository for `MAX_IMAGE_PIXELS` incidentally printed matching lines from earlier-round evidence files (`judge-3-round-4-report.md`, `round-4-fixes-review.md`, `round-4-judge2-fixes.md`). They describe the round-4 decompression-bomb fix. I did not open those files. All results above come from my own runs against the live stack.

## Cleanup

- Revoked every `j3r5-*` agent grant and the temporary API token.
- Turned off the disposable user `j3r5u72614`.
- Removed the share grants and the test workflow.
- Test documents remain in the `judge3` account only.
