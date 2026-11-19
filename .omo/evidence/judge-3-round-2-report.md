# Judge 3, round 2 report (security and reliability focus)

- Candidate SHA: `f2b94168ff7af0bb914bb3f644eef7ee7490394a` (branch `codex/initial-implementation`, clean tree)
- Date: 2026-11-18
- Reviewer account: `judge3` (instance admin). Disposable account created through the People screen: `j3r2-iso` (member). It was turned off at the end of the run.
- Stack: running local stack at `http://localhost:18080` (PWA + `/api` + `/mcp`), with the OCR worker, maintenance worker, and scheduler. I did not restart any container.
- Browser: Playwright `Version 1.64.1` (`npx playwright --version` in `apps/web`), Google Chrome channel `157.0.8103.79` (headless). Desktop viewport 1440x900. Mobile emulation 390x844 with `isMobile` and `hasTouch`. Locales `en-US` and `it-IT`.
- HTTP and MCP calls: Node 26 `fetch` and a raw `net` socket, with my own session cookie, a personal API token I created, and agent grant tokens. `curl` was not permitted in this environment.
- Artifacts: `qa-artifacts/20261118-r2-judge-3/`, with 24 screenshots plus one label HTML. Token values are masked in every image. The exact scripts are copied to `qa-artifacts/20261118-r2-judge-3/scripts/`. They read the password from `judges.env` at runtime and never print it.

## Commands and scripts run

All scripts are in `qa-artifacts/20261118-r2-judge-3/scripts/`. Each one was run with `node <script>` from a scratch folder that links to `apps/web/node_modules`.

| Script | What it exercised |
| --- | --- |
| `api.mjs`, `pw.mjs` | Cookie-jar API client with CSRF, and the Playwright launcher (desktop or mobile, locale) |
| `t1-upload.mjs` | Upload validation (fake PDF, renamed EXE, empty, HTML-as-PNG, SVG, GIF, `%PDF-` + HTML polyglot, 26.5 MB, `../` names, HTML in the file name), the fixture uploads, and CSRF (missing token, foreign Origin) |
| `t3-mcp.mjs` | Three MCP grants with different scopes and tag filters: `tools/list`, in-scope and out-of-scope calls, filter enforcement, cross-grant tag change, foreign Origin, revocation, audit log, document history |
| `t4-iso.mjs`, `t4b.mjs` | Isolation between accounts: 30 document, tag, and admin routes probed by the member; view-only share; unshare |
| `t5-tokens.mjs`, `t5b.mjs` | Personal API tokens: password needed to create, blocked routes, upload without CSRF, revocation, admin password reset ending tokens and sessions. `t5b` removed the tag share the test created |
| `t6-interrupt.mjs` | Upload cut off midway (raw socket), truncated PDF, cancel of 5 queued jobs then retry, reprocess keeping the original SHA-256, retry of a failed document |
| `t7-retr.mjs`, `t9-phys.mjs` | Search syntax (phrase, `tag:`, `date:`, `OR`, `-`, `text:`), locations, paper copy, sticker lookup, move with history, label |
| `t12.mjs` | Response headers and cookie flags |
| `e3-people.mjs` | People screen: added `j3r2-iso` |
| `e5-agents-ui.mjs` | Agents screen: create a grant with a tag filter, revoke through the inline confirmation, MCP returns 401 afterwards |
| `e6-tokens-backup.mjs` | Security screen API token (wrong password, create, use, revoke), Backups screen "Back up now", double POST |
| `e7-upload.mjs` | Mixed valid and invalid batch report, offline upload queue, lost-response retry (route fetches then resets) |
| `e8-member.mjs` | Member navigation, then the account turned off while its page is open |
| `e9-kbd.mjs` | `?` shortcut list, Tab order, keyboard-only agent create and revoke, focus after actions, signing out in another tab |
| `e10-mobile-it.mjs`, `e11-tokvis.mjs` | Mobile Italian: Library, Agents, Security, People, Backups; offline upload; app closed and reopened, then online; position of the one-time token |
| `e12-label.mjs`, `e13-find.mjs`, `e14-hist.mjs` | Label rendering, typed sticker lookup, OCR phrase search, agent history on a document |

## Fixture IDs used

`three-pages.pdf`, `judge.png`, `office-letter.docx`, `email-notice.eml`, `outlook-notice.msg`, `office-sheet.xlsx`, `tag-barcode-desktop.pdf`, `asn-batch-desktop.pdf`, `barcode-batch-desktop.pdf`, `office-slides.pptx`, `office-open.odt`, `office-legacy.doc`.

I also made synthetic invalid files of my own. These are not fixtures: `fake.pdf`, `evil.pdf.exe`, `empty.pdf`, `page.png` (HTML), `img.svg`, `anim.gif`, `polyglot.pdf`, `big.pdf` (26.5 MB random), and a truncated copy of `three-pages.pdf`.

## Scores

| Dimension | Weight | Score | Evidence (what I exercised) | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 7.5 | Web upload on desktop and mobile of PDF, PNG, DOCX, XLSX, PPTX, ODT, DOC, EML, and MSG. All processed in seconds with the original kept. Invalid files are refused per file with clear reasons (07). The offline queue survives closing and reopening the app (08, 18). Email subject and date were filled automatically. Friction: a lost upload response stores a second copy that needs review in Inbox (H2). Saved document errors stay in English in the Italian Library (L3). | Real camera scan, installed PWA gallery picker, Telegram, watched/consume folder, Android client, correcting an uncertain suggestion (not reached in my time box) |
| Retrieval and physical filing | 20% | 8.0 | OCR phrase (`heron`, `9473`), exact phrase, `tag:`, `date:2026-11`, `date:2026-11-10`, `OR`, `-exclusion`, `text:` all correct with snippets. Nested location, paper copy, typed sticker lookup (case-insensitive), move with movement history, sticker search, printable label (20–23). `sender:"Comune di Esempio"` found nothing because the email's sender was not filed as a correspondent. | Re-scanning a printed QR with a camera (headless Chrome on macOS has no `BarcodeDetector`, so I could not decode the label), printing |
| UX and accessibility | 20% | 7.0 | Skip link, `?` shortcut list, logical Tab order on the Agents form, revoke confirmation that takes focus ("Yes, revoke"), no horizontal overflow at 390 px, Italian coverage of the screens I checked. Defects: focus drops to `<body>` after creating or revoking a grant (M3). On mobile the one-time agent token is drawn about 3,900 px above the viewport (M2, 19). An ended session leaves the app showing "0 documents" and three "Sign in required" banners instead of the sign-in screen (M1, 10). | Installed iOS/Android PWA, Android client, VoiceOver/TalkBack, real touch |
| Reliability and recovery | 20% | 7.5 | An upload cut off midway leaves no document. A truncated PDF fails safely or is processed. Five queued jobs cancelled and retried all reached ready. Reprocess keeps the original bytes (SHA-256 equals the fixture). A second reprocess while busy gets 409. A deterministic failure stays failed after retry. A manual backup completed and verified in 9 s (06). A concurrent second backup gets 409. The offline queue is re-sent after the page is reopened. Defect: the retry after a lost response is not idempotent (H2). | Killing or restarting the worker, API, or DB mid-job; clean-stack restore; the NAS; interrupted uploads on a real device |
| Privacy and agent control | 15% | 7.0 | `tools/list` matches the scopes exactly. Out-of-scope calls are denied and audited. The tag filter holds for reads and writes. Revocation gives 401 on the next request (from the UI and the API). Audit entries store no text. Tokens are shown once and stored hashed. API tokens cannot reach account, people, agents, links, mail, sources, or backups, and are ended by a password reset. No cross-account access on 30 routes, and view-only sharing is enforced. A turned-off account loses its session and tokens. Uploads are content-sniffed. CSRF is enforced. Defects: H1 (one agent can widen another agent's document filter), M4 (members cannot have agents), M5 (no security headers on the PWA shell), L1. | A real cloud MCP client (Claude Desktop and similar), grant expiry over time, restore of revoked grants |

**Weighted mean: 0.25×7.5 + 0.20×8.0 + 0.20×7.0 + 0.20×7.5 + 0.15×7.0 = 7.43 (7.4)**

No dimension reaches 9.0. I found meaningful defects in every dimension I tested.

## Hard gates

| Gate | Status |
| --- | --- |
| 1. Every FEATURE_PARITY row has a working scenario or accepted deviation | Partially demonstrated: upload/OCR, formats, search syntax, physical copies, agents, tokens, sharing, backups, and trash/retry were exercised. Most rows (workflows, mail, sources, versions, page editing, custom fields, and more) were not exercised by me. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore (originals, tags, locations, revoked grants) | Partially demonstrated: upload, OCR, search, and verified backup creation. Fresh install and restore were not demonstrated, because I may not restart or rebuild the stack. |
| 3. Installed iOS PWA, installed Android PWA, native Android capture and interrupted upload | Not demonstrated (needs the owner's hardware). Only browser emulation and the offline queue were exercised. |
| 4. Security review: account and agent isolation, token revocation, CSRF, upload validation, external input boundaries, no default content transfer | Partially demonstrated: all listed areas were exercised except external inputs (Telegram, cloud, IMAP). It does **not** pass as is, because of H1 (agent filter isolation) and M5. |
| 5. Unit/API tests, builds, browser journeys, migrations, deployment checks on the candidate | Not demonstrated by me. I ran no test suite and no build; my brief did not include it. |

## Findings

### Severe

None found.

### High

**H1. An agent with the tag permission can move documents into another agent's filter, so that agent can read text the owner never scoped to it.**

- Repro (`scripts/t3-mcp.mjs`):
  1. Tag `email-notice.eml` with `j3r2-agentA` and `outlook-notice.msg` with `j3r2-agentB`.
  2. Create grant A `{documents:search, documents:text}` filtered to `j3r2-agentA`.
  3. Create grant B `{documents:search, documents:tag}` filtered to `j3r2-agentB`.
  4. Grant B calls `change_document_tags {document_id: <outlook doc>, add: [<j3r2-agentA id>]}` and gets `ok`.
  5. Grant A's `search_documents` now returns "Avviso condominio mirtillo", and `get_document_text` works on it.
- Grant B has no text permission, yet it decides which documents the text-reading agent A may read. The owner's document filter for A is bypassed, and if A is a cloud client, content leaves the NAS beyond the owner's intent. Document history records the change (24), but nothing warns the owner.
- `list_tags` exposes every tag, including other grants' filter tags. B can also remove A's filter tag to hide documents from A.
- Cause: `services/api/archive/mcp_server.py:226`. `change_document_tags` accepts any owner tag, including tags that are another active grant's `filter_tag`.
- Fix direction: refuse adding or removing any tag that is the `filter_tag` of an active grant other than the caller's own (or of any grant), and hide such tags from `list_tags`. Add a test in which two grants try this.

**H2. Retrying after a lost response stores the document twice. The web upload queue has no idempotency key.**

- Repro (`scripts/e7-upload.mjs`): in the PWA, add `three-pages.pdf` while a route lets the POST reach the server and then resets the connection. The file shows "1 file is waiting to upload". After the `online` event it is re-sent, and the Library then holds **2** documents with the same name.
- The server already supports idempotent retries for Android (`X-Ripiano-Scan-ID`, `services/api/archive/views.py:594-604`, honored only as source `android`). The PWA retry loop (`apps/web/src/App.tsx:1190-1197`) does not send its stable queue id.
- This is documented as a limitation in `apps/web/src/uploadQueue.ts:1-5`. Still, on flaky mobile connections, the exact scenario the queue exists for, every lost answer becomes a duplicate that needs review in Inbox. That contradicts the "no mandatory TODO screen" capture goal.

### Medium

**M1. An ended session is not handled: the app shows an empty archive instead of the sign-in screen.**

- Repro (`e9-kbd.mjs`, `e8-member.mjs`, screenshot 10):
  1. Sign out in a second tab, or have an admin turn the account off.
  2. In the first tab, click "All documents".
- The page shows "0 Documents / 0 Ready to find" and three "Sign in required" banners, and stays in the app shell.
- Cause: `apps/web/src/api.ts:258-261`. A 401 is thrown like any other error, and `App.tsx` never resets `session`.
- Risks: a person may think their archive is empty. Offline uploads started in this state stay queued with no clear way forward.

**M2. On mobile, the one-time agent token appears far off-screen.**

- Repro (`e11-tokvis.mjs`, screenshot 19): at 390x844, Agents, create a token. The "Copy this token now" box is at `top: -3884px` while the view stays at the form, and focus drops to `<body>`.
- A person on a phone may not see the token, and it cannot be shown again.
- Cause: `apps/web/src/AgentPanel.tsx:117` sets the token without scrolling to it or focusing it.

**M3. Keyboard focus is lost after creating or revoking an agent grant.**

- Repro (`e9-kbd.mjs`): using only the keyboard, create a grant, then revoke it. `document.activeElement` is `BODY` both times, so a screen-reader user hears nothing about the one-time token or the revocation.
- The revoke confirmation itself focuses "Yes, revoke" correctly.

**M4. Only instance admins can use agents. Members cannot connect any MCP agent to their own private archive.**

- Repro: sign in as a member (`j3r2-iso`). There is no Agents item in the navigation, and `/api/agents` returns 403 "Owner access required".
- Cause: `services/api/archive/agent_views.py:21` (`is_superuser`) and `apps/web/src/App.tsx:544` (`OWNER_VIEWS`).
- FEATURE_PARITY promises "same access behavior across PWA, Android, REST, and MCP" for every user. Members can have personal API tokens but no MCP grant, and that limitation is not documented in AGENT_ACCESS.md.

**M5. The PWA shell is served without any security headers.**

- `GET /` has no `Content-Security-Policy`, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options`, or `Referrer-Policy`. `/api` responses do have `DENY`, `nosniff`, and `same-origin`.
- Cause: `apps/web/nginx.conf` has no `add_header`, and `deploy/gateway` does not add them either.
- With the planned gateway, sibling services on the same registrable domain are same-site, so `SameSite=Lax` cookies would be sent to a framed Ripiano. That allows clickjacking of actions such as creating agent tokens or People changes.

### Low

**L1.** A personal API token can share tags, senders, types, and saved views with another account: `POST /api/object-access/tag/<id>` returned 201. The document-level `/access` and `/shares` routes are blocked for tokens (`services/api/archive/api_tokens.py:16-36`), so `/api/object-access` should be blocked too. I removed the test grant afterwards.

**L2.** The agent activity list in the UI does not show which document an action touched, although the API returns `document_id`. It has no filter per agent and is capped at 100 entries. Revoked grants can never be removed from the list.

**L3.** The Italian UI shows document errors in English in the Library and in `/api/jobs`, for example "Elaborazione non riuscita: Text recognition failed…". Cause: `services/api/archive/api_language.py:82` translates only a top-level `error` key, not nested document errors.

**L4.** A CSRF failure returns Django's HTML 403 page rather than JSON. The UI copes, but API clients get HTML.

**L5.** Login throttling allows 10 failures per username per 15 minutes, so anyone who can reach the sign-in can lock the owner out for 15 minutes. Behind the planned gateway all requests share the Pi's address. This is a known trade-off; mention it in SECURITY.md.

**L6.** The member People list exposes every active username (40 here), which is by design for sharing. Admins cannot reset another admin's password, and the app has no promote or demote control.

### Verified as working (security)

- Upload validation. Refused: fake PDF, renamed EXE, empty file, HTML-as-PNG, SVG, GIF, and the 26.5 MB file (limit 25 MB). The `%PDF-` + HTML polyglot was accepted and failed OCR safely. File names with `../` are reduced to the base name. An HTML file name is escaped in the UI and only used in `Content-Disposition: attachment`. Originals are served `attachment` with `nosniff`.
- CSRF: a missing token, or a foreign `Origin` with a valid token, gets 403.
- MCP: unknown, API-type, or revoked bearer gets 401 with `WWW-Authenticate`. A foreign `Origin` gets 403. Unknown tool names are denied and audited.
- Isolation between accounts: 30 document, tag, admin, version, merge, and link routes return 404/403 for another account's document. After unsharing, access returns 404.
- Sessions and tokens: an admin password reset ends the member's API tokens and session. A turned-off account cannot sign in, and its open session gets 401.

## Most serious finding

**H1:** An agent holding only `documents:tag` can add another grant's filter tag to its documents. The other agent, which may be a cloud client allowed to read OCR text, then reads documents the owner never put in its filter. This breaks the "agent grants are additional restrictions" and per-agent document filter promise (`services/api/archive/mcp_server.py:226`).
