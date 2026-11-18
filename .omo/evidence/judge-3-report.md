# Judge 3 report — Ripiano quality review

- **Candidate SHA:** `901d491828b1eb9df5d674a23e6115c0dd7bc3be` (branch `codex/initial-implementation`)
- **Date:** 2026-11-18 (run 09:15–09:35 Europe/Rome)
- **Reviewer:** Judge 3 (account `judge3`, an archive admin with an empty archive at start). Focus: security and reliability; all five dimensions scored.
- **Stack:** `http://localhost:18080` (PWA + `/api` + `/mcp`), running as provided. No containers restarted or rebuilt.
- **Browser:** Playwright `Version 1.64.1` (`npx playwright --version` in `apps/web`), Google Chrome `157.0.8103.79` (channel `chrome`, from `browser.version()`).
- **Viewports:** desktop 1440x900; mobile emulation 390x844 (`isMobile`, `hasTouch`, DPR 2, `it-IT` locale).
- **Artifacts:** `qa-artifacts/20261118-judge-3/` (24 screenshots plus `judge3-scripts.txt`, which holds every script verbatim). Token values are masked. No password appears in any artifact.

> Note on source references: the working tree had uncommitted changes from other work during this review (for example the untracked `search_syntax.py` and a modified `views.py`). Every file:line below was checked against `git show 901d491:<path>`, not against the working tree.

## Exact commands

All scripts live in `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j3/`. They import `@playwright/test` by absolute path from `apps/web/node_modules`, and each was run as `node <script>`. Their full text is in `qa-artifacts/20261118-judge-3/judge3-scripts.txt`. HTTP and MCP calls used the Playwright `APIRequestContext`, because direct `curl` was not permitted in this environment.

| Script | Purpose |
| --- | --- |
| `lib.mjs` | Helpers: session login with CSRF, UI login, token masking. Reads the password from `judges.env` at runtime. |
| `s1-explore.mjs`, `s2-capture.mjs` | Session/role probe; Add-document dialog inputs |
| `s3-upload.mjs` | UI capture: camera input, then a 13-file mixed-validity batch |
| `s5-agents-tokens.mjs` | CSRF; two MCP grants with different scopes and filters; tools/list, tool calls, audit, revoke; API token create/use/blocked routes/revoke |
| `s6-people.mjs`, `s7-iso.mjs`, `s8-iso2.mjs` | People screen; creates the disposable member `judge3-iso` through the UI; isolation (view, then edit, then revoke); password reset ends tokens and sessions |
| `s9-upload-sec.mjs` | Upload validation (polyglot, SVG-as-PNG, HTML, XSS/traversal filenames, 26 MB, broken DOCX), idempotent scan retry, raw-socket interrupted upload |
| `s10-reliab.mjs` | Security headers; retry of a failed document; cancel of queued and processing jobs; retry of a cancelled job |
| `s11-backup.mjs`, `s12-runs.mjs` | "Back up now" through the UI plus a concurrent API request; run outcomes |
| `s13-ui.mjs`, `s14-agent-ui.mjs` | Agents screen; grant created and revoked through the UI; failed-document panel; oversized upload through the UI |
| `s15-mobile.mjs`, `s15b-offline.mjs` | Mobile, Italian, OCR search, detail view, horizontal-overflow check; offline interrupted upload |
| `s16-keyboard.mjs` | Skip link, `/`, `j`, Enter/Esc, `?`, `g a`, focus indicators |
| `s17-retrieval.mjs`, `s18-final.mjs` | Sender/date/tag/OCR/sticker search; paper copy, label, move, history; member sticker isolation; `semantic_search` while the feature is off; XSS-title rendering; Sources; member mobile "Shared with me" |

## Fixtures used

From `apps/web/e2e/fixtures/` (SHA-256 values match `corpus.sha256`): `judge.png`, `three-pages.pdf`, `office-letter.docx`, `email-notice.eml`, `outlook-notice.msg`, `office-sheet.xlsx`, `office-legacy.doc`, `office-open.odt`, `office-slides.pptx`, `tag-barcode-desktop.pdf`, `asn-batch-desktop.pdf`, `barcode-batch-desktop.pdf`, `asn-batch-mobile.pdf` (as four cancel probes with a unique byte suffix each).

Synthetic negatives, kept in scratchpad `j3/bad/`:
- `fake-invoice.pdf` (an MZ header)
- `empty.pdf` (0 bytes)
- `polyglot.pdf` (`%PDF-` followed by HTML/JS)
- `x.png` (SVG with a script)
- `big-27mb.pdf`
- a random 26 MB `%PDF-` buffer, a broken DOCX, and HTML

## Scores

| Dimension | Weight | Score | Evidence (what I exercised) | Not exercisable or not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **7.5** | Camera-input upload (`judge.png`). A 13-file batch through the Browse input: 11 valid files across 9 formats imported and reached Ready within about 60 s. Clear per-file reasons for the 2 invalid files (`04-desktop-batch-mixed.png`). ASN/barcode batch PDFs split automatically. Exact-copy flag on identical bytes. No mandatory TODO screen; documents are retrievable at once. | Real camera, installed PWA, Android client; Telegram and watched-folder capture (the built-in consume source belongs to the first archive owner, and Telegram needs a real bot); "correct an uncertain suggestion in one screen" (not exercised). Defects: oversized-file error is a raw JSON parse message (M2); offline/interrupted browser upload loses the file with "Failed to fetch" and no queue (M3); raw `InputFileError` shown (L1). |
| Retrieval and physical filing | 20% | **8.0** | OCR phrases (`second heron`, `third badger`); text from .eml and .msg; `sender:"…"`, `tag:…`, exact `date:2026-03-15`, `sticker:R-…`; sticker lookup; nested location, paper copy, move, movement history; printable label (HTML). Another account cannot look up my sticker (404). | Printing and physically re-scanning a label; QR scan through a camera. Month and range date queries are rejected (L4). |
| UX and accessibility | 20% | **7.5** | Desktop and mobile emulation without horizontal scroll; full Italian screens with no English leftovers found in the mobile detail; skip link is the first Tab stop; `/`, `j`, Enter, Esc, `?`, `g a` work; focus indicator on 24 of 25 Tab stops (Agents). Shared-with-me works on mobile for a member. | Installed iOS/Android PWA, Android client, real screen reader, touch on hardware. Friction: focus goes to `<main>` instead of the opening row after closing the detail panel (L5); raw technical errors (M2, L1, L3); mobile detail opens on the form with no page preview, and a shared viewer gets no preview at all (L6). |
| Reliability and recovery | 20% | **7.0** | Raw-socket upload cut at 50%: no partial document, API healthy. `X-Ripiano-Scan-ID` retry returns the same document (202, then 200). Cancel of 3 queued documents worked; cancelling a document already processing is refused with 409. Retry of a cancelled document reached Ready; retry of a failed polyglot failed again cleanly. "Back up now" completed a checksum-verified snapshot in about 15 s. | Interrupting or restarting the OCR worker or other services (not allowed on the shared stack); restore to an empty stack; NAS performance. Defects: two backups started in the same second both ran (M4); no client-side retry queue in the PWA (M3); raw errno in a backup error (L3). |
| Privacy and agent control | 15% | **8.0** | Two grants: A has search+text with a tag filter, B has search only. `tools/list` was exact per grant. B is denied `get_document_text`. A is denied documents outside its tag and tools outside its scopes. Audit lists ok, denied, and error entries. Revoking B gives 401 on the next call while A keeps working. A UI-created grant also returned 401 after UI revoke. Foreign Origin gives 403, foreign Host 421; agent tokens are rejected on `/api` and API tokens on `/mcp`. CSRF is enforced (403 without a token or with a bogus one). API tokens are blocked from account, agents, people, share links and access grants; a revoked token gives 401; a password reset ends the member's tokens and sessions. Member isolation is clean on documents, originals, archive PDF, pages, export, notes, trash, shares, bulk actions, stickers and locations, with immediate loss of access on unshare. Semantic search is off, so no content left the stack. | A real cloud agent (Claude/ChatGPT); OAuth-based clients. Defects: an API token can email documents to any address and set up exfiltrating sources and workflows (M1); `semantic_search` is advertised while the feature is off (L2); only admins can create agents (L7); out-of-filter probes are logged with a null document ID (L8). |

**Weighted mean (Judge 3): 0.25×7.5 + 0.20×8.0 + 0.20×7.5 + 0.20×7.0 + 0.15×8.0 = 7.58 / 10**

The quality gate needs 9.5 on average and 9.0 per dimension. This candidate does not meet it on my evidence, and the hard gates below are not satisfied either.

## Hard gates

| Gate | Status |
| --- | --- |
| 1. Every FEATURE_PARITY row has a working scenario or an accepted deviation | **Not demonstrated.** I exercised a subset (upload channels, OCR/search, Office/email, barcode/ASN splitting, physical archive, sharing, agents, backups); I did not verify the matrix row by row. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **Partially demonstrated:** upload, OCR, search and a manual checksum-verified backup passed. Fresh install and clean-stack restore with grant checks were not run (they need an empty stack; I was not allowed to touch containers). |
| 3. Installed iOS/Android PWA and native Android capture and interrupted upload on real devices | **Not demonstrated** (needs owner hardware). Browser emulation of an interrupted upload was run and failed in the UI (M3). |
| 4. Security review: account/agent isolation, token revocation, CSRF, upload validation, external inputs, no default transfer to model providers | **Partially demonstrated:** account isolation, agent isolation, token revocation, CSRF and upload validation passed live. External input boundaries (Telegram, cloud OAuth, IMAP) were not exercised. "No default transfer" holds for what I saw (semantic search off, no provider keys). M1 and M5 are open. |
| 5. Unit/API tests, builds, browser journeys, migrations, deploy checks on the candidate | **Not demonstrated** by me. I did not run the suites: they create data under fixed accounts on the shared stack, and the working tree is not at the candidate commit. |

## Findings

### Severe
None found.

### High
None found.

### Medium

**M1 — API tokens can send document content out of the archive, despite the "no public links" boundary.**
- Cause: `services/api/archive/api_tokens.py:18-24` (`BLOCKED_PREFIXES` and `_blocked`) blocks share links and access grants, but not:
  - `POST /api/documents/<id>/email` (`bundle_views.py:230`), which emails the original or PDF to up to 10 arbitrary addresses;
  - `/api/workflows` (webhook/email actions);
  - `/api/sources` and `/api/mail/accounts` (credential-bearing inputs).
- Repro (`s5-agents-tokens.mjs`):
  1. Create a token under Security → API tokens.
  2. `POST /api/documents/<id>/email` with `Authorization: Token rip_…` and body `{"to":""}` returns **400 validation**, not 403. The route is reachable, and a valid `to` would send the document.
  3. For contrast, `POST /api/documents/<id>/shares` with the same token returns 403.
  4. `GET /api/sources`, `/api/workflows` and `/api/backups` with the token all return 200.
- Impact: a leaked script token reads everything (expected), but it can also push originals to external mailboxes and webhooks, which the README's token boundary implies it cannot.

**M2 — Upload over about 26 MB shows a raw JavaScript error.**
- Cause: nginx rejects the body first (`apps/web/nginx.conf:6`, `client_max_body_size 26m`; Django's limit is 25 MB at `settings.py:139`) with an HTML 413. `apps/web/src/api.ts:236` calls `response.json()` unconditionally, and `App.tsx:989` shows the exception text.
- Repro: Add document → Browse files → pick a 27 MB PDF. The page shows "1 of 1 files could not be added. big-27mb.pdf: Unexpected token '<', "<html> <h"... is not valid JSON" (`11-desktop-too-large.png`).
- There is no client-side size check before sending.

**M3 — The PWA does not keep or retry an interrupted upload.**
- Cause: `App.tsx:967-997` has no pending queue; the file inputs are cleared in `finally`.
- Repro (`s15b-offline.mjs`, `18-mobile-offline-upload.png`):
  1. Mobile emulation, open Add.
  2. Go offline, then choose a photo with the camera input.
  3. The page shows "judge.png: Failed to fetch". The "Retry" button reloads the list, not the upload. After going back online nothing is retried.
- The user must find and pick the photo again. The native Android client may cover this, but it was not validated on a device.

**M4 — Concurrent manual backups are not de-duplicated.**
- Cause: `services/api/archive/views.py:1255` (at 901d491) creates a `BackupRun` without checking for a pending or running one.
- Repro (`s11-backup.mjs`): click "Back up now" and send `POST /api/backups` about 0.5 s later. Both return 202 and both run to completion: snapshots `…082230…` and `…082240…`, 0.5 s apart.
- On a 4 GB DS923+ this doubles I/O and disk use. Any of the many admin accounts can trigger it.

**M5 — Sign-in throttle per address becomes a global lockout behind a reverse proxy.** This is from code review only and was not exercised, because it would lock out the other judges.
- Cause: `services/api/archive/throttle.py:13` keys on `X-Real-IP`, which nginx sets to `$remote_addr` (`nginx.conf:13`). Behind the Synology proxy or the planned Traefik gateway, that is always the proxy's IP. The limit is 30 failures in 15 minutes (`throttle.py:9`), stored in a shared Redis cache (`settings.py:100`).
- Effect: anyone on the internet can fail 30 sign-ins and lock out every user, including the owner, for 15 minutes, again and again.

### Low

- **L1 — Raw exception names are shown to users.** The failed polyglot PDF shows "Processing failed: InputFileError" (`10-desktop-failed-doc.png`). Cause: `tasks.py:113` stores the last diagnostic line as is.
- **L2 — `semantic_search` is advertised while semantic search is off.** It appears in `tools/list` for text-scoped grants and returns `{"error":"Semantic search is off"}` when called (`mcp_server.py:272-276`). AGENT_ACCESS.md says the tool exists "only while the optional semantic search is on".
- **L3 — Backup errors show raw OS errors.** "[Errno 13] Permission denied: '/backup/staging'" is visible in Backups for an old run (`tasks.py:184`).
- **L4 — Date search accepts exact days only.** At the candidate, `date:2026-03` and `date:2026-03-01..2026-03-31` return "Use YYYY-MM-DD after date:". Only exact days work through the search box.
- **L5 — Focus is not returned after closing the detail panel.** Repro: Library, press `j`, Enter, then Esc. `document.activeElement` is `<main>`, not the row that opened the panel.
- **L6 — No page preview for a shared viewer, and a form-first detail on mobile.** For a member with view access, `GET /api/documents/<id>/pages/1.png` returns 404. The member detail offers only download links (`24-mobile-member-shared-doc.png`). On mobile, the owner's detail panel opens on edit fields with no preview (`17-mobile-it-detail.png`).
- **L7 — Only admins can create MCP agents.** `agent_views.py:21` requires `is_superuser`. A family member cannot connect an agent to their own archive (member gets 403 on `/api/agents`).
- **L8 — Out-of-filter agent probes lose the document ID in the audit log.** When agent A asked for text of a document outside its tag, the audit entry recorded `document_id: null` with outcome "error", so the owner cannot see which document was probed.
- **L9 — Members can list every username.** `GET /api/people` returns all 39 usernames to a non-admin, probably to support sharing. The SPA document itself is served without CSP or `X-Frame-Options` (only the API responses carry `X-Frame-Options: DENY`). The `SameSite=Lax` session cookie mitigates framing attacks.
- **L10 — Agent revocation has no confirmation.** Revoke acts on the first click. This is acceptable because it fails safe, but the opposite of how other destructive actions behave.

### Verified as working well (for balance)

- Uploads are content-sniffed: HTML, SVG renamed to `.png`, executables renamed to `.pdf`, empty files and broken Office ZIPs are all rejected with readable reasons.
- The `%PDF` polyglot is stored but served with `Content-Disposition: attachment` and `nosniff`, and its processing fails safely.
- A title of `<img src=x onerror=alert(1)>` renders as text with no script execution. A `../../../../etc/passwd.pdf` filename is stored as `passwd.pdf`.
- MCP checks DNS rebinding and Origin. Agent and API tokens are hashed and do not work on each other's endpoints.
- A password reset revokes API tokens and sessions.

## Single most serious finding

**M1: an API token can push document content out of the archive** through document email, workflows and sources, even though tokens are presented as unable to create outbound sharing. A leaked or misused script token therefore becomes a quiet way to exfiltrate originals. M5, the proxy-wide sign-in lockout, is the most serious availability risk for the planned gateway deployment.

## Data created by Judge 3 (for cleanup)

- **In account `judge3`:** about 30 documents (fixtures, negatives, cancel probes), tags `j3-agent-ok` and `j3-token-tag`, sender "J3 Comune di Lampone", locations "J3 Shelf A" and "J3 Box 2", one paper copy, and 4 agent grants (all revoked at the end of the run). API tokens: `j3-script` is revoked, and the `iso` token belongs to the member account.
- **Disposable member `judge3-iso`:** created through People; its password was reset, which ended its token. No document is shared with it now.
- **Backups:** 2 manual backup snapshots, 08:22 UTC.
