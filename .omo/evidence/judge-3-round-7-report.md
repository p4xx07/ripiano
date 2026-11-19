# Judge 3 — round 7 report

- Candidate SHA: `2e97ca193004cae30da90c067357f89478e135f9` (branch `codex/initial-implementation`); running stack at http://localhost:18080
- Date: 2026-11-19
- Reviewer focus: security and reliability (agent grants, scopes, revocation through MCP, agent-to-agent isolation including through workflows, password change and deactivation, workflows started by single, bulk, and agent edits, upload validation and retries, whether the parity document matches the build). All five dimensions are scored.
- Browser: Playwright 1.64.1, Google Chrome 157.0.8103.79 (channel `chrome`). Desktop 1440x900; mobile emulation 390x844 (`isMobile`, `hasTouch`, DPR 3); locale `en-US` and the in-app Italian setting.
- Account: `judge3` (archive owner/admin). I created one temporary person, `j3r7-tmp-58458`, for the deactivation and cross-account tests. It is deactivated again. I did not touch other judges' data.
- Run tag: `58458`. Every object I created is named `j3r7-…-58458`.

## Commands and scripts

The scripts are in the scratch folder `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/judge3-r7/` (outside the repository):

| Script | What it does |
| --- | --- |
| `api.py` | Python standard library helper: session plus CSRF, multipart upload, and an MCP Streamable HTTP client (`initialize` → `notifications/initialized` → `tools/list`/`tools/call`) |
| `sec1.py` | Tags, uploads, three agents A/B/C, tool lists, scope and filter enforcement, guarded filter tags |
| `sec2.py` | "Updated" workflows started by agent tag change, agent sender change, unfiltered-agent change, owner single edit, and owner bulk edit |
| `sec3.py` | Owner password change: agent, other session, CSRF; the password was restored afterwards |
| `sec4.py` | Temporary person: deactivation, reactivation, own password change, admin reset; agent and API token behavior; what an API token may do |
| `sec5.py` | Upload validation (empty, fake PDF, .exe, random .jpg, PDF named .png, truncated PDF), scan-ID retry semantics |
| `sec6.py` | Retrying a failed document, the jobs endpoint, an upload interrupted half-way at the socket level |
| `phys.py` | Shelf and nested box, paper copy, move, sticker lookup, box lookup, label, movement history, `sticker:` search |
| `xacct.py`, `xacct2.py` | Cross-account access: another person's document, a document shared *with* judge3 versus judge3's agents, the owner deactivated |
| `tok.py` | Personal API token limits and revocation; MCP without a bearer token or with a session cookie |
| `ui1.mjs`, `ui2.mjs`, `ui3.mjs` | Playwright, desktop and mobile: search, document dialog and history, Agents create/revoke, Workflows, keyboard (`/`, `j`, Enter, focus trap, Esc), Italian, touch targets, overflow, sticker search |

Run with `python3 -I <script> <scratch>` and `cd apps/web && node <scratch>/uiN.mjs <scratch>`. The logs are `sec*.log` in the scratch folder.

**Fixture IDs used:** `three-pages.pdf`, `office-letter.docx`, `judge.png`, `office-open.odt`, `email-notice.eml`, `office-sheet.xlsx`, `outlook-notice.msg`, `office-legacy.doc`. Derived negative inputs, made in the scratch folder: an empty `.pdf`; text named `.pdf`; a 30 KB truncation of `three-pages.pdf`; an MZ-header `.exe`; random bytes named `.jpg`; `three-pages.pdf` renamed `.png`.

**Screenshots** (15) are in `qa-artifacts/20261119-r7-judge-3/`, with agent tokens masked: desktop/mobile 01 search, 02 document, 03 history, 04 agent created, 06 workflows, 10 sticker search; desktop 05/07 keyboard dialog, 08 Agents in Italian, 09 Workflows in Italian.

## What I observed

### Privacy and agent control

- **Tool lists follow scopes exactly.** A (search+text+tag+filing, filter tag fA) got 6 tools; B (search, filter fB) got `search_documents` only; C (search+tag, no filter) got 3 tools.
- **Scopes and document filters held on every call:**
  - A reading text outside its filter got "Document not found within this grant".
  - B calling `get_document_text` got "Tool is not permitted".
  - After A removed its own filter tag from a document, A could no longer re-add it ("not found within this grant").
- **Guarded filter tags held.** These were all refused: A adding fB; C adding fB (by ID and by case-changed name); C removing fB; C removing fA; C adding fA.
- **Workflows started by agents cannot widen another agent's view.** Each run detail says "skipped tag … (it limits another agent's access and an agent made the change)". This held for:
  - workflow "if tagged trig → add fB" after A added `trig`;
  - workflow "if sender S → add fB, remove fA" after A set the sender;
  - the same tag workflow after the unfiltered agent C changed tags.
- **Owner edits run the same workflows unguarded, as intended.** A single-document PATCH and `bulk-tags` both added fB. B's view afterwards was exactly the two owner-tagged documents.
- **Document history** records the agent, then the workflow, with old → new tag lists.
- **Agent activity** logs refused calls with the document title. A cross-account attempt logs no title, so nothing about the other account leaks.
- **Password change revokes everything:** all agent grants and API tokens, and the other session. The current session stays signed in. This was checked for the owner and for the temporary person.
- **Admin password reset and account deactivation** revoke agents and tokens and end the session (MCP 401, token 401). Reactivating does not bring old grants back.
- **Agent creation requires the password.** A wrong password returns 400 and counts toward the sign-in throttle.
- **A personal API token** reads documents (200) but gets 403 on people, agents, workflows, mail, backups, share links, tokens, and sources. Once revoked, it gets 401.
- **MCP without a bearer token, or with only a session cookie:** 401.
- **CSRF:** a session POST without the CSRF token gets 403.
- **Cross-account isolation:** judge3 gets 404 on the other person's document. Judge3's unfiltered agent cannot search, read, or tag a document that person shared with judge3 *as edit*. This matches AGENT_ACCESS.md: an agent only sees its creator's own documents.

### Capture and reliability

- **Uploads:** PDF, DOCX, PNG, ODT, EML, XLSX, and MSG were all `ready` within about 8–12 s.
- **Rejected uploads have clear, specific messages:**
  - empty file: "File is empty";
  - fake PDF: "could not be read as a PDF…";
  - .exe: the list of allowed types;
  - random .jpg: "could not be read as a JPEG or PNG image…".
- **A PDF named `.png`** was accepted and downloads as `…pdf` with `application/pdf`, as the parity row claims.
- **Truncated PDF:** status `failed` with the "damaged… compare it with the paper" message. Page 1 is still searchable ("first otter"). Retry is accepted (202) and correctly stays failed. The document appears in `/api/jobs` under failed.
- **Scan-ID retries:**
  - same ID, same bytes: 200 with the same document;
  - same ID, different file: 409 with a clear message;
  - malformed ID: 400;
  - the same ID on the android channel is a separate namespace (202).
- **Interrupted upload** (half the multipart body, then the socket closed): no ghost document.
- **Restore drill:** `.omo/evidence/restore-drill-round7.md`, run on this exact commit, is detailed and credible. Fresh install, upload/OCR/search, backup, clean restore, originals verified by SHA-256, tag, nested location and sticker, and revoked grant still 401 with the active one still 200. I count it for hard gate 2.

### Retrieval and physical filing

- **Search:**
  - OCR phrase search with snippets works: `text:otter`, "three-pages otter", "first otter".
  - `sticker:R-…` finds the document; typing the sticker into the Library search shows the shelf/box path on desktop and mobile.
- **Paper copies:**
  - Nested shelf and box, placing a copy, and moving it with a note all work. The movement history shows from → to, the note, and the person.
  - Box label lookup works, and the printable label HTML is served.

### UX and accessibility

- **Keyboard:**
  - `/` focuses the search; `j` highlights a row; Enter opens the dialog.
  - Focus stays inside the dialog after 8 Tab presses. Esc returns focus to the row title.
  - A skip link is the first Tab stop.
- **Mobile (390 px):** no horizontal overflow. No control in the Library main area is shorter than 44 px. The revoke button is 62x44 on mobile (62x27 on desktop).
- **Italian:** no English left on the Agents screen.
- **No console errors** on either viewport.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 8.8 | Seven formats ready in about 10 s; precise rejection messages; scan-ID semantics; damaged-PDF handling; workflows filing on single, bulk, and agent edits | Camera, Telegram, and watched folder (out of scope, or not exercised by me); this round I uploaded through the API, not the PWA Add dialog; I did not exercise correcting a suggestion in one screen |
| Retrieval and physical filing | 20% | 8.9 | OCR, tag, and sticker search with snippets; move with history; box label lookup and label HTML | Physical sticker scan with a camera; printing. A query combining a title number fragment with a body word returns nothing (L2) |
| UX and accessibility | 20% | 8.6 | Keyboard flow, focus trap and return, skip link, mobile targets and no overflow, Italian Agents screen | Screen reader; real devices (out of scope). Workflows "Recent runs" is unstyled (M1); run details are English in Italian (M2); agent activity is an unbounded wall of 100 rows (L1) |
| Reliability and recovery | 20% | 9.0 | Retry, interrupted upload, damaged PDF, idempotent scan retry, credible restore drill on this commit | Restarting workers or services myself (forbidden on the shared stack); NAS restore (out of scope) |
| Privacy and agent control | 15% | 9.3 | Every isolation, revocation, and workflow-guard probe held; password change, admin reset, and deactivation revoke grants and tokens; tokens limited; CSRF enforced; cross-account and shared-document isolation for agents | Real cloud MCP client (I used my own MCP HTTP client); expiry by time |

**Weighted mean:** 0.25·8.8 + 0.20·8.9 + 0.20·8.6 + 0.20·9.0 + 0.15·9.3 = **8.90**

## Hard gates

| Gate | Demonstrated? | Notes |
| --- | --- | --- |
| 1. Every parity row has a working scenario or accepted deviation | Partially | The rows I probed match the build: upload/scan-ID/extension, damaged PDF, workflows on single/bulk/agent edits with guarded tags, users and permissions, API token limits, tags with agent filter guard. I did not verify all rows; FEATURE_PARITY.md itself says the Italian native-speaker review and the R4 row-by-row verification are still open. |
| 2. Fresh install, upload/OCR/search, backup, clean restore | Yes (by evidence) | `.omo/evidence/restore-drill-round7.md` on `2e97ca1`, credible; upload, OCR, and search re-verified live by me |
| 3. Installed iOS/Android PWA, native Android | Out of scope by owner decision (D7) | — |
| 4. Security review (isolation, revocation, CSRF, upload validation, input boundaries, no default content transfer) | Yes, within scope | All probes passed. Telegram and cloud inputs are out of scope by owner decision. |
| 5. Unit/API tests, builds, journeys, migrations, deployment checks | Not run by me | I judged the running build only |
| NAS performance, ACLs, restore on the DS923+; real Telegram and cloud accounts | Out of scope by owner decision (D7) | — |

## Findings

No severe or high findings.

### Medium

**M1 — Workflows "Recent runs" list is unstyled.** It is the screen where the agent-guard explanation appears.

- **What happens:** the run name, status, document link, detail, and time run together with no spacing (e.g. "Applied**j3r7-58458-office-sheet**added tag …"). The first glyph of each row is clipped at the card edge, and rows are not separated (`desktop-06-workflows.png`).
- **Repro:** open Workflows with at least one run.
- **Cause:** `apps/web/src/WorkflowsPanel.tsx:300-302` renders `<div className="agent-events">` with `<div>` children. The CSS only styles `.agent-events > li` (`apps/web/src/style.css:2978-2995`), as used by the `<ul>` in `AgentPanel.tsx:339`. It also loses list semantics for screen readers.

**M2 — Workflow run details stay English in the Italian interface,** including the guard explanation "skipped tag … (it limits another agent's access and an agent made the change)", "added tag", "removed tag", and "marked as needing action".

- **Repro:** set Language to Italiano and open Workflows (`desktop-09-workflows-it.png`).
- **Cause:** the detail is composed server-side as English text and stored in `WorkflowRun.detail` (`services/api/archive/workflows.py:252-296`). This conflicts with the parity row's "no hard-coded text" localization claim.

### Low

**L1 — Agent activity is a flat list of the latest 100 events across all agents.** It has no grouping, no per-agent filter, and no paging. On a used account the Agents screen is about 5,000 px tall, with the "Search by meaning" card at the bottom (`desktop-04-agent-created.png`). Refused and failed outcomes are only small grey text. Cause: `agent_views.py` `events` returns `[:100]` unfiltered.

**L2 — A free-text search that combines a number from a hyphenated title with another word returns nothing.**

- **Repro:** title `j3r7-58458-three-pages`. Each query below returns:
  - `58458`: 11 results (it matches the file name);
  - `otter j3r7`: 3 results;
  - `otter 58458`: 0;
  - `58458 three`: 0.
- **Cause:** every word must match the tsvector (`archive/fulltext.py:71-85`, `views.py:512-516`), and the file-name/title `icontains` fallback applies only to the whole query string. Realistic titles such as "Fattura-2026-031" would behave the same way.

**L3 — A workflow's "remove tag" action is silently skipped for tags the owner added by hand.** The run detail says nothing about it: workflow "if sender S → … remove fA" left the manually added fA in place, and the detail only mentioned the skipped fB. Cause: `workflows.py:257-258` `.exclude(origin=MANUAL)` with no message. This is arguably intended ("manual choices win"), but the run should say so, as it does for guarded tags.

**L4 — A document shared by a person who is then deactivated stays visible to the recipient.** Judge3 still got 200 on the document after `j3r7-tmp` was turned off. Defensible (sharing outlives the sharer), but the parity row says "Turned-off accounts… end access" without saying whose access ends. Worth one sentence in USER_GUIDE/FEATURE_PARITY.

**L5 — Owner-triggered workflow runs and agent-triggered runs share the once-per-document rule.** After an agent's change makes a run skip a guarded tag, a later human edit will not re-apply that tag automatically. The owner has to add it by hand, and the run detail does not mention that.

### Most serious finding

**M1:** the Workflows "Recent runs" list renders without layout. It is the one place where an owner can see that the agent guard skipped a tag, and it is hard to read and loses list semantics.

No security or isolation defect was found in this round: every agent-isolation, revocation, and upload-validation probe held on the running build.

## Cleanup

- All agent grants on judge3 are revoked (0 active). The password change in `sec3.py` revoked the leftover round-6 grants; the original password was restored and verified by signing in.
- Both `j3r7` workflows are paused. The temporary person `j3r7-tmp-58458` is deactivated. The API tokens were revoked.
- No token values were written to the repository. The scratch token state (`state.json`) is outside the repository, and its tokens are all revoked.
