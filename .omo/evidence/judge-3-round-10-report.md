# Judge 3 — round 10 report (security, privacy, reliability)

- **Candidate:** `5bc8c7de72619aac6ebea44b3cad7c69a610b31a` (branch `codex/initial-implementation`; HEAD `255f81d` adds only the two evidence files).
- **Date:** 2026-11-20 (stack clock 2026-11-19 23:29–23:52 UTC).
- **Stack:** my own Compose project `ripiano-j3`, `http://localhost:18103`, started empty. All 206 Python files under `/app` in the running `api` container have the same SHA-256 as `git show 5bc8c7d:services/api/...` (checked file by file), so the running API is the candidate.
- **Browser:** Playwright 1.64.1, Google Chrome 157.0.8103.79 (channel `chrome`), macOS 26.6. Desktop 1440x900; phone emulation 390x844 (`isMobile`, `hasTouch`); English and Italian.
- **Screenshots:** `qa-artifacts/20261119-r10-judge-3/` (23 files, no token values).
- **Weighted mean: 8.73.** Two dimensions are below 9.0.

## How the checks were run

`curl` was refused by my sandbox, so every HTTP and MCP call went through Playwright's request client (cookie jar, CSRF header taken from the cookie, as the browser does). The scripts are in my scratch folder `…/scratchpad/j3r10/`, each run with `node <script>` in the order below.

| Script | What it does |
| --- | --- |
| `lib.mjs` | Shared client: session + CSRF, anonymous fetch, a small MCP Streamable-HTTP client |
| `01-setup.mjs`, `02-owner.mjs` | Anonymous probes (`/healthz`, `/livez`, `/api/*`, `/mcp`); first-time setup in the browser; second setup refused |
| `03-seed.mjs` | CSRF checks, uploads and upload validation, tags, family account, share link, bundle, API token, three agents |
| `04-mcp.mjs`, `05-isolation.mjs` | Tool lists, scopes, filters, audit, agent-started workflow, revocation; family-account isolation (44 requests); API-token boundary (21 requests) |
| `06-access-end.mjs`, `07-fixpw.mjs` | Public links; account off/on; admin reset; owner password change; weak passwords; sign-in limit |
| `08-probe.mjs` | Stop/start `db`, then `broker`: probes during the outage, timing of recovery |
| `09-kill.mjs`, `10-watch.mjs`, `11-kill2.mjs` | `docker compose kill worker` during a barcode-split scan (twice); stalled state; owner retry raced against restart |
| `12-digest.mjs`, `13-backup.mjs` | Backup; digest of every original/archive SHA-256, tags, locations, grants, people, shares before and after restore |
| `14`–`17` | Desktop and phone screens (Agents, People, Security, search, document, Backups, Shared with me), keyboard sign-in, tidy-up |

Compose commands (from the repository root, `dc` = `docker compose -p ripiano-j3 --env-file …/jstacks/j3/stack.env`): `dc stop db` / `dc start db`; `dc stop broker` / `dc start broker`; `dc kill worker` / `dc start worker`; `dc down -v`; `dc up -d --no-build db broker api`; `dc stop web worker maintenance_worker scheduler mcp api`; `dc run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261119T234554756135Z-6c1bb29a --yes`; `dc up -d --no-build`. Gate 5: `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` and `manage.py makemigrations --check --dry-run`.

**Fixtures used:** `three-pages.pdf`, `office-letter.docx`, `judge.png` (also with trailing bytes appended to make distinct files), `email-notice.eml`, `office-open.odt`, `office-slides.pptx`, `office-sheet.xlsx`, `barcode-batch-desktop.pdf`, `barcode-batch-mobile.pdf`, `asn-batch-desktop.pdf`, `tag-barcode-desktop.pdf`.

## Scores

| Dimension | Weight | Score | Evidence | Not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | PDF, DOCX, ODT, PPTX, XLSX, PNG and EML uploads all reached `ready`; an exact copy was flagged and offered in the Inbox; a fake PDF, an HTML file and a path-traversal file name were handled safely; the document panel offered a one-tap learned tag suggestion with a reject button. Barcode and ASN batches split into the right parts. | Camera, gallery, Telegram, watched folder, mail; uploads through the browser dialog (I uploaded through the API). The score rests on a narrow sample. |
| Retrieval and physical filing | 20% | 9.0 | The OCR phrase "second heron" found both copies in the Library with a text snippet; a shelf location and a paper copy with sticker codes were created and survived the restore. | Sticker scanning, label printing and re-scanning, moving a copy, sender/date filters. |
| UX and accessibility | 20% | 8.8 | Italian sign-in, Library, Backups and Agents on a phone with no horizontal overflow; named controls in the accessibility tree (`ariaSnapshot`, a stand-in for a screen reader); keyboard sign-in lands on "Add document"; inline revoke confirmation; token shown once with focus on the "Copy this token now" card. Friction: the backup failure message is jargon (H1); a database outage shows only "The server sent an unexpected reply" (L5). | Installed PWAs and the Android client (out of scope); a real screen reader; most screens outside my emphasis. |
| Reliability and recovery | 20% | 8.0 | Database and broker stop/start: everything worked again on the first request, no restarts needed. Two worker kills during a split scan: no duplicates, no stuck documents. Backup → `down -v` → restore: 0 differences across 24 documents. Pulled down by H1: backups fail while anything is being processed and for up to 2 hours after a worker is killed. | Interrupted browser upload; power loss of the whole host; NAS (out of scope). |
| Privacy and agent control | 15% | 8.8 | Three agents with different scopes and filters showed the right tool lists; every out-of-scope or out-of-filter call was refused and logged; revocation, account off, admin reset and password change ended every credential I tested. Pulled down by M1 (an agent-started workflow shared a document with a person) and L1–L3. | Semantic search (not configured); two-step sign-in; a real cloud client. |

Weighted mean: 0.25×9.0 + 0.20×9.0 + 0.20×8.8 + 0.20×8.0 + 0.15×8.8 = **8.73**.

## Hard gates

| Gate | Demonstrated? | Notes |
| --- | --- | --- |
| 1. Parity | Not assessed by me | Outside my emphasis; I did not walk FEATURE_PARITY.md row by row. |
| 2. Install, upload/OCR/search, backup, clean-stack restore | Yes, with a caveat | Fresh setup, upload, OCR and search passed. Restore passed: all 24 originals and archive PDFs byte-identical, tags, location and paper copy, shares, people, workflow, audit entries kept; revoked agents, the revoked share link and the revoked API token stayed dead; a second restore was refused ("Restore requires an empty Ripiano database"). Caveat: three of my five backup attempts failed (H1). |
| 3. Real devices | Out of scope by owner decision | Installed iOS/Android PWA, native Android capture, real Telegram/Google/Microsoft/Dropbox accounts, and checks on the Synology DS923+. |
| 4. Security review | Yes, with findings | Account and agent isolation, token revocation, CSRF, upload validation and public-link boundaries all held. Findings M1, L1–L4. No document content left the server by default. |
| 5. Tests and builds | Credible | I re-ran the API suite: `400 passed, 17 skipped in 66.99s`, and `No changes detected` for migrations — both match `round10-verification.md`. Its two live claims also match what I measured (agents answer right after a database restart; a killed worker's document is requeued after about 3 minutes with one copy). I did not re-run the web build or e2e suite. Gap: no test or drill covers a backup that overlaps document processing, which is why H1 passed all 400 tests and the recorded restore drill. |

## What held up

- **CSRF:** a POST without the header, with a wrong token, or with a foreign `Origin` got 403, including upload and sign-out. Cookies: `sessionid` is HttpOnly, SameSite=Lax, 14 days.
- **Health endpoints:** through the web port `/healthz` returns only `{"status":"ok"}` or 503 `{"status":"unavailable"}` and never names the failing part; it went 503 with either the database or the broker down. `/livez` stayed 200 in both outages.
- **Database stopped:** API and MCP answered 500. After `start db`, sign-in, the existing session, the API token, an MCP session opened before the outage and a new one, and upload all worked on the first try (under 1 s) with no container restarted.
- **Broker stopped:** sign-in, browsing, MCP and the API token kept working. An upload during the outage was accepted (202) and processed by itself after the broker returned.
- **Worker killed during a barcode-split scan (twice):** the parent was marked stalled after about 2 minutes (Cancel and Retry then offered) and finished by itself after about 3.5 minutes; exactly two parts each time, no duplicates. Owner Retry raced against the restarted worker also gave exactly two parts; a second Retry and a Reprocess were refused with 409. Cancelling a queued document worked and left a clear "Retry OCR" message.
- **Agents:** tool lists matched the grants (2, 1 and 5 tools). The titles-only agent found nothing for the OCR-only word "otter". Out-of-filter documents answered "Document not found within this grant". An agent could not add another agent's filter tag directly, and a workflow it triggered skipped that tag, so agent A never gained access to the private document. A tag the owner had removed by hand was not re-added by the agent. Revocation gave 401 on the next call, in an open session too.
- **Family accounts:** the second person could not read, export, trash, re-share, link, bundle or merge the owner's unshared documents (404), could not edit a view-only share (403), saw no owner tags, workflows, agents, bundles or backups, and her own agent could not see documents shared with her.
- **API token:** read and filing worked; 15 security, sharing and outbound routes answered 403 with an explanation. An agent token was refused as an API token and the reverse.
- **Account off / reset / password change:** turning the account off killed her session, API token, agent, share link and bundle at once; turning it back on revived none. An admin reset and the owner's own password change did the same (the current session survived, the other session did not), and the Agents screen says "Revoked because your password changed".
- **Public links:** `no-store`, `nosniff`, attachment disposition; wrong tokens 404; a link token does not work on the bundle route.

## Findings

No severe finding.

### High

**H1. Backups fail whenever a document is being processed, and for up to two hours after a worker is killed.**
The OCR worker keeps its work folder inside the media volume (`tasks.py:211`, `tempfile.TemporaryDirectory(dir=media_root, prefix="work-")`). The backup walks the whole media volume and skips only `.pending`, `previews` and `bundles` (`backup.py:136`); any other top-level folder raises "Snapshot contains an unexpected media path" (`backup.py:121-122`). A killed worker leaves its folder behind, and stale folders are only removed after 2 hours (`tasks.py:82`, `remove_stale_work_dirs`).

Reproduction A (no fault needed): upload four images and `tag-barcode-desktop.pdf`, then press **Back up now** within a second. `/data` contains `work-5_64k114/input.pdf`; the run ends `failed · Snapshot contains an unexpected media path`. Once processing finished the same button produced a complete snapshot.

Reproduction B: upload `barcode-batch-desktop.pdf`, `dc kill worker` while it is "processing", `dc start worker`. Documents recover, but `/data/work-2h1kr9ex/split-parts.txt` remains. **Back up now** failed, and **Try again** failed again; after I deleted the two leftover folders by hand the backup passed.

Impact: the 02:00 backup is lost on any night when a mail, source or folder import is being processed at that moment, or when the worker was killed (for example for memory) in the two hours before. The failure is visible on the Backups screen, but the message means nothing to a family user and Try again does not help. I saw no automatic retry. Screenshots: `backup-failed-desktop.png`, `backup-failed-mobile-it.png`.

### Medium

**M1. A workflow started by an agent's change shares the document with people (and queues its webhook and email).**
`workflows.py:293-298` runs `share_with`, the webhook and the email whatever started the run; only tag actions honour the agent guard (`guarded_tags`, `workflows.py:225`).

Reproduction: workflow "when updated and tagged Invoices → add tag Agent-A, share with anna (view), add note". Agent "Tagger C" (tags and filing only, limited to tag Private) called `change_document_tags` to add "Invoices" to "Secret judge scan". The guarded tag was skipped, but the document was shared with anna, who then opened it and downloaded the original on her phone (`anna-shared-doc-mobile.png`).

Impact: an agent holding only "Add or remove tags" can cause any document inside its filter to be disclosed to whoever the owner's workflows share, post or email to. The recipients are the owner's own choices, not the agent's, and the history shows the agent and the workflow. Neither the Agents screen nor `docs/AGENT_ACCESS.md` warns that tag permission can trigger sharing and outbound workflows.

### Low

- **L1. Weak passwords are accepted.** Changing the owner password to `judge3judge3` (the username twice), `aaaaaaaaaaaa` or `qwertyuiopas` returned 200; only the all-digits one was refused. First-time setup checks length only (`views.py:399`).
- **L2. A view-only share exposes the owner's notes and full change history.** anna saw the note "wf ran" and every history entry on the shared document, including the owner's agent names ("Tagger C (Private only)") and tags added and removed.
- **L3. Anyone who can reach the sign-in page can lock a person out.** The 11th wrong password for one username returned 429 for 15 minutes (`throttle.py`, 10 per username). From the code the block is checked before the password, so the right password is refused too; I confirmed the 429 on an unknown username only, not on a real account.
- **L4. Debug error pages on my stack.** My stack runs with `RIPIANO_DEBUG=1` (`settings.py` refuses a non-HTTPS origin otherwise), and during the database outage anonymous requests such as `GET /api/session` received Django's HTML error page. I could not read `.env.example` (blocked in my sandbox), so I do not know whether the README's `http://localhost:8080` install ships with debug on; worth checking.
- **L5. Database outage message.** The app shows only "The server sent an unexpected reply. Try again." (`outage-db1-desktop.png`), although `/livez` and `/healthz` could tell it the database is down.
- **L6. No sign of a dead worker for two minutes.** Until the stalled check fires, a document stuck in "processing" offers neither Cancel nor Retry, and the Inbox does not mention the waiting documents.

## Single most serious finding

**H1:** a backup started while any document is being processed, or within two hours of a worker being killed, fails with "Snapshot contains an unexpected media path", and retrying does not help until the leftover work folder is gone.

## State left behind

Stack `ripiano-j3` is running and healthy (restored from snapshot `20261119T234554756135Z-6c1bb29a`, plus one later upload and one later snapshot). Every agent grant and API token I created is revoked, for both accounts; the test workflow is disabled. Passwords, tokens, ids and scripts are only in my scratch folder.
