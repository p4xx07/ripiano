# Judge 3 — round 6 report

- Candidate SHA: `635be8edb4768499d627eae922c1ab5a463cfeb3` (branch `codex/initial-implementation`); running stack at http://localhost:18080 (judged as running).
- Date: 2026-11-19 (CET), run between 00:10 and 00:30 local time.
- Reviewer focus: security and reliability (agent grants/scopes/revocation through MCP, API tokens, account isolation, workflow sharing, upload validation, interrupted/retried uploads, headers, backup). All five dimensions are scored.
- Browser: Playwright `Version 1.64.1`, Chrome channel `Google Chrome 157.0.8103.79`. Desktop 1440x900 (`locale en-US`); mobile emulation 390x844, `isMobile`, `hasTouch`, DPR 2, `locale it-IT` (the UI followed the device language and rendered in Italian).
- HTTP client: Node 26 `fetch` (curl was not permitted in this session).
- Account: `judge3` (admin). One disposable member account, `j3r6-tmp-31126`, was created through `POST /api/people` (what the People screen calls) for the isolation tests. It was turned off at the end through the People screen and is still off.
- Environment note: a second process was also using the `judge3` account during my run. Documents and agents with suffix `-26763` and the files in `scratchpad/judge3/` are not mine; mine use suffixes `-31126`, `-68583`, `-43311`, `-57457`. I used my own scratch folder, `scratchpad/judge3-r6b/`, so the two runs would not interfere.

## Commands and scripts

All scripts are in `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/judge3-r6b/`. Token values are masked in logs, and the password is read from `judges.env` at runtime.

| Script | Run as | What it does |
| --- | --- | --- |
| `lib.mjs` | — | Cookie and CSRF session client, multipart upload, MCP Streamable-HTTP client (`initialize` → `tools/list` / `tools/call` on `/mcp`) |
| `a1.mjs` | `node a1.mjs` | Security and cache headers, sign-in, CSRF-less POST |
| `a2.mjs` | `node a2.mjs` (log `a2.log`) | Two MCP agents with different scopes and a tag filter: tool lists, filter enforcement, cross-agent guard, revocation, audit |
| `a3.mjs` | `node a3.mjs` (log `a3.log`) | Disposable user: cross-account isolation, API token limits, sharing, workflow `share_with`, password change, turning the account off and on |
| `a5.mjs` | `node a5.mjs` | Workflow sharing with a corrected file-name pattern; behaviour while the recipient is off |
| `a6.mjs`, `a7.mjs` (log `a6.log`) | `node a6.mjs` | Upload validation (empty, fake PDF, HTML/SVG/EXE, traversal and RTL names, wrong extension, truncated PDF), scan-ID idempotency, parallel retries, Trash interaction, retry of a failed document |
| `a8.mjs` | `node a8.mjs` | Manual backup creation and completion |
| `a9.mjs`, `a10.mjs` | `node …` | Cookie flags, deleting an agent's filter tag, share-link lifecycle, invalid grants, sign-in throttle |
| `a11.mjs` | `node a11.mjs` | Whether "updated" workflows fire on bulk, MCP, and single-document changes |
| `b1.mjs` | `cd apps/web && node …/b1.mjs desktop` and `… mobile` | Browser: offline upload queue, lost response (`route.fetch()` then `abort`), Agents create/revoke, API cache headers |
| `b2.mjs` | `cd apps/web && node …/b2.mjs` | Browser, keyboard only: sign-in, skip link, `/`, `J`, `Enter`, `Esc` focus return, `?`, `G A`, People turn-off with confirmation |

Fixture IDs used: `office-letter.docx`, `three-pages.pdf`, `judge.png` (from `apps/web/e2e/fixtures/`), plus synthetic invalid payloads built in `a6.mjs`: an empty file, text named `.pdf`, HTML named `.png`, `.html`, `.svg` with a script, a fake `.exe`, the first 600 bytes of `three-pages.pdf`, and `three-pages.pdf` named `.png`.

Artifacts (13 files) are in `qa-artifacts/20261118-r6-judge-3/`: `desktop-01…05`, `mobile-01…05`, and `kbd-01…03`. The agent token field is masked in the creation screenshots.

## Scores

| Dimension | Weight | Score | Evidence (what I exercised) | Not exercisable or not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 8.8 | Web upload of the fixtures on desktop and mobile, which reached `ready` in about 4 s. Bad files are refused at upload with clear EN/IT messages: empty, fake PDF, HTML-as-PNG, HTML, SVG, EXE. Traversal and RTL-override names are sanitized. Batch and parallel uploads work. Workflow assignment and sharing work on "added". Friction: "updated" workflows do not run after bulk or agent changes (H1). A truncated PDF is accepted and fails only later at OCR (L2). A PDF uploaded with a `.png` name downloads as `.png` (L3). | Camera scan, Telegram, watched folder, Android; I did not repeat the uncertain-suggestion correction |
| Retrieval and physical filing | 20% | 8.8 | Keyboard search (`/`, query, `J`, `Enter`) opened the right document. Agent search matches titles only without the text scope, and OCR text with it. The share link served the original with `no-store` and `no-referrer`, and returned 404 after revocation. | I did not exercise sticker scanning, moving a paper copy, or printing and re-scanning a label in this run (left to the other judges). The score reflects limited evidence, not observed defects. |
| UX and accessibility | 20% | 9.1 | Desktop EN and mobile IT both rendered cleanly. Keyboard only: the first Tab lands on "Skip to content"; `/` focuses search; `J` and `Enter` open the dialog with focus on Close; `Esc` returns focus to the row; `?` opens the shortcut list; `G A` goes to Needs action. People turn-off is a two-step confirmation reachable by keyboard, with a clear consequence message. The offline banner is clear in both languages. Friction: the agent activity list shows guarded-tag refusals as "failed" rather than refused, and the rows do not name the document (L1). | Real phones, screen reader (no VoiceOver/TalkBack run) |
| Reliability and recovery | 20% | 9.2 | Offline upload was kept in IndexedDB and sent once when the connection returned (desktop and mobile). A simulated lost response (request reached the server, response dropped) was retried with the same scan ID, producing 1 copy on the server. Three parallel posts with one scan ID gave statuses 202/200/200 and 1 document. Retrying a scan that is in Trash returns 409. A damaged PDF goes to failed with an actionable message, and Retry OCR re-queues it. A manual backup completed in about 8 s. The clean-stack restore drill (`restore-drill-round6.md`, same SHA) checks originals by SHA-256, tags, nested locations and stickers, and revoked grants; I find it credible. Friction: reusing a scan ID with a different file silently returns the old document (L4). A workflow share to a turned-off person is skipped while the run reads "nothing needed changing" (L5). | Killing or restarting workers and containers (forbidden on the shared stack); my own restore |
| Privacy and agent control | 15% | 9.4 | See the security matrix below. Every isolation, scope, filter, revocation, password-change and turn-off check passed. Agent creation needs the password; a deleted filter tag is refused (409) while an active agent uses it. Deductions: refusals logged as "error" (L1); the parity claim about agents triggering workflows is wrong (H1, scored under capture). | Real cloud MCP clients; semantic search (off on this stack) |

**Weighted mean: 0.25·8.8 + 0.20·8.8 + 0.20·9.1 + 0.20·9.2 + 0.15·9.4 = 9.03**

### Security matrix (all observed live)

| Check | Result |
| --- | --- |
| Agent A (`search`+`text`, filter tag) `tools/list` | only `search_documents`, `get_document_text` |
| Agent B (`search`+`tag`) `tools/list` | only `search_documents`, `list_tags`, `change_document_tags` |
| A reads text outside its filter | refused: "Document not found within this grant" |
| B calls `get_document_text` | "Tool is not permitted for this agent"; logged as `denied` |
| B adds or removes A's filter tag (by ID, by name in a different case, remove) | all refused: "This tag limits another agent's access" |
| B adds an ordinary tag | allowed |
| After A is revoked | A gets 401 on MCP; the filter tag is no longer guarded, so B can add it (as designed) |
| Bad, random, or API-style token on MCP; agent token on REST; API token on MCP | 401 in every case |
| Disposable user U opening judge3's document, original, pages, history, notes, export; PATCH, trash, bulk-tags, share, public link | 404 in every case; backups 403 |
| U's agent searches or reads a document judge3 shared with U | not visible ("an agent only sees its creator's documents") |
| U with view access edits the shared document | 403; original download 200 |
| U's API token creating agents, tokens, a password, workflows, people, a share link, or a session | 403 with a clear reason; `Bearer` scheme 401; reading and ZIP export allowed |
| U changes password | same session continues; the other session, API token, and agent all get 401 |
| Admin turns U off (password required; without it 400) | session, token, and agent 401; sign-in 401. After turning U on again, the old token, agent, and session stay dead and the UI lists the agents as revoked |
| Workflow `share_with` U on "added" | shared on upload (run detail "shared with … (view)"); while U is off, no grant is created |
| CSRF-less POST with a session | 403 |
| Sign-in throttle | 429 after 10 failures |
| Cookies | `sessionid` HttpOnly, SameSite=Lax; `csrftoken` SameSite=Lax (no `Secure` on the local http origin, as expected) |
| Headers | PWA: strict CSP (`script-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`), XFO DENY, nosniff, `Referrer-Policy: same-origin`, Permissions-Policy. API document data is `private, no-store`; originals are `attachment` + `nosniff` + `private, no-store` |

## Hard gates

| Gate | Status in this review |
| --- | --- |
| 1. Every parity row has a working scenario or an accepted deviation | **Not demonstrated, and one contradiction found.** The Workflows row says MCP agents' changes can trigger "updated" workflows; live they do not (H1). I did not verify the other rows one by one. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore (originals, tags, locations, revoked grants) | **Pass**, partly my own evidence: upload, OCR, search, and manual backup were observed live. The clean-stack restore is from `.omo/evidence/restore-drill-round6.md` on the same SHA, which I judge credible. |
| 3. Installed iOS/Android PWA and native Android on real devices | **Out of scope by owner decision (D7).** Browser emulation only. |
| 4. Security review: account and agent isolation, token revocation, CSRF, upload validation, external input boundaries, no default transfer to model providers | **Pass for what I exercised** (matrix above). No provider calls are configured; semantic search is off. |
| 5. Unit/API tests, production builds, browser journeys, migrations, deployment checks on the candidate | **Not run by me** (no rebuilds or restarts allowed). My browser journeys against the running build passed. |

## Findings

### Severe
None.

### High
**H1 — "Updated" workflows do not run on MCP-agent or bulk changes, although the parity contract says agents can trigger them.**
- `docs/FEATURE_PARITY.md` (Workflows row, D1 rationale) states: "MCP agents … apply filing through their grants, and workflows can react to those changes with 'updated' triggers."
- Repro (`a11.mjs`):
  1. Create a workflow: `trigger: "updated"`, `filter_tag_id: T`, `set_needs_action: true`.
  2. `POST /api/documents/bulk-tags {add T}` on document D2. Result: `action_status` stays `none`.
  3. Agent B calls MCP `change_document_tags add T` on D1. Result: stays `none`.
  4. Single-document `PATCH /api/documents/D2 {title}`. Result: `open` (the workflow ran).
- Cause: the only "updated" call site is `services/api/archive/views.py:1089` (single-document PATCH, owner only). `bulk_document_tags` (`views.py:671`), `bulk_document_filing` (`views.py:714`), and MCP `_execute` `change_document_tags` / `set_document_filing` (`services/api/archive/mcp_server.py:219`, `:263`) never call `run_for_document`.
- Impact: the D1 substitute for Paperless "AI actions + workflows" does not work as documented, and Paperless runs "Document Updated" on bulk edits too. The UI label ("When I change a document") hints at the narrower behaviour, but the parity contract does not.
- Fix: either run "updated" workflows after bulk and agent changes, or correct the parity row and record it as an accepted deviation. If the guard is kept, note that an agent-triggered workflow could add another agent's filter tag.

### Medium
None found in this run.

### Low
- **L1 — Agent activity misclassifies refusals and omits the document in the UI.** A guarded-tag refusal is stored as `outcome="error"` (`mcp_server.py:331`) and shown as "failed", unlike scope refusals, which are `denied` (`mcp_server.py:321`). The activity rows (screenshot `desktop-05-agent-revoked.png`) do not show which document was involved, although the API returns `document_id`. Repro: `a2.mjs` "B add TF to D2", then open Agents → Recent activity.
- **L2 — A truncated PDF passes upload validation.** The first 600 bytes of `three-pages.pdf` return 202, then fail at OCR. Text bytes named `.pdf` are refused at upload. Repro: `a6.mjs` "truncated pdf". The failure message is actionable, so the impact is low.
- **L3 — A wrong extension is kept on the original.** `three-pages.pdf` uploaded as `x.png` is detected as a PDF (3 pages, `application/pdf`) but downloads as `attachment; filename="…png"`, so the OS opens it with the wrong app. Repro: `a6.mjs` "pdf-as-png", then `GET /original`.
- **L4 — Reusing a scan ID with different bytes silently returns the earlier document** (200, same ID), with no checksum comparison. `views.py` upload path (`documents()` POST, scan-ID branch around lines 640–652). The web client generates one UUID per file, so this matters only for buggy or third-party clients. A 409 on checksum mismatch would be safer.
- **L5 — A workflow share skipped because the recipient is turned off is not reported.** The run detail reads "conditions matched; nothing needed changing" (`workflows.py` `_share`, `continue` when `lookup is None`). The owner cannot tell that the intended share did not happen. Repro: `a5.mjs`.
- **L6 — Any member can list every username** (`GET /api/people` as non-admin U returns 200 with id, username, name). This is presumably needed for the sharing picker, but it also enumerates accounts, including other judges and admins.
- **L7 — Minor header nits.** A CSRF failure returns Django's HTML 403 page instead of JSON. The unauthenticated `/api/session` and the HTML shell and `sw.js` have no `Cache-Control` (document data endpoints correctly send `private, no-store`).

## Most serious finding
**H1:** "Updated" workflows never run after MCP-agent or bulk edits (only `views.py:1089`), which contradicts the parity contract's D1 claim that agents' filing changes can trigger workflows.
