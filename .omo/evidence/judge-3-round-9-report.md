# Judge 3 — round 9 report (security, privacy, reliability)

- Candidate: `1a365f35c12509f79da9cd9c459b426dca1f4ec4` (HEAD `c2156fc` adds only `.omo/evidence/restore-drill-round9.md` and `round9-verification.md`; `git diff --stat 1a365f3 HEAD` = 2 evidence files).
- Date: 2026-11-19.
- Stack: my own Compose project `ripiano-j3`, http://localhost:18103, started empty; I did the first-time setup myself in the browser with the setup key (owner `owner`; passwords kept only in my scratch folder).
- Browser: Playwright `Version 1.64.1`, Chrome channel `157.0.8103.79`. Desktop 1440x900 and mobile emulation 390x844 (`isMobile`, `hasTouch`); locale `it-IT` (the app followed the device language, Italian, throughout). No screen reader: Playwright `ariaSnapshot()` used as a stand-in.
- Artifacts: `qa-artifacts/20261119-r9-judge-3/` (10 screenshots). Scripts, ids, passwords and tokens: scratch folder `.../scratchpad/j3r9/` (not in the repo).

## Commands and scripts run

| What | Command / script |
| --- | --- |
| Owner setup in the browser | `node j3r9/setup.mjs go` (fills Nome utente / Password / Chiave di configurazione) |
| API client | `j3r9/rc.py` (stdlib; session + CSRF header + Origin, Token and MCP bearer helpers) |
| Family accounts, uploads, tags | `python3 -I j3r9/p1_setup.py` |
| Isolation, CSRF, headers, API-token boundaries | `python3 -I j3r9/p2_security.py` |
| Share links/bundles, D11 own change and admin reset, D9 off/on, Trash revocation | `python3 -I j3r9/p3_shares.py` |
| Agents (3 grants), tool lists, filters, guarded tags, agent-started workflow, MCP transport, revoke, D10 | `python3 -I j3r9/p4_agents.py`, `p4b.py` |
| Kill worker mid-OCR, stop broker, stop db, restart api during uploads | `j3r9/dc.sh kill worker` / `stop broker` / `stop db` / `restart api` with `p5.py` and inline scripts |
| Simulated 1 h stale recovery of the interrupted document | `manage.py shell` (set `processing_started_at` back 2 h, call `reconcile_pending_documents()`) |
| Backup → `down -v` → restore (docs/BACKUP_RESTORE.md) | `p6_drill.py prep` (state capture + `POST /api/backups`); `dc.sh down -v`; `dc.sh up -d db broker api`; `showmigrations archive`; `dc.sh stop web worker maintenance_worker scheduler mcp api`; `dc.sh run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261119T153334822719Z-1b70f292 --yes`; `dc.sh up -d`; `p6_drill.py verify` |
| Browser journeys | `ui1.mjs` (Agenti/Persone/Panoramica), `ui3.mjs` (document → Condividi l'originale), `ui4.mjs mobile` (upload while api stopped), `ui5.mjs` (keyboard reset password, revoked agents) |
| Gate 5 re-run | `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` → `372 passed, 15 skipped in 64.64s` |

`dc.sh` = `docker compose -p ripiano-j3 --env-file .../jstacks/j3/stack.env "$@"`. No image was rebuilt; no other project was touched; the stack is left running. All agent grants I created are revoked (MCP answers 401 for all three tokens); the owner API token was ended by the password change.

## Fixture IDs used

`three-pages.pdf`, `judge.png`, `office-letter.docx`, `email-notice.eml`, `office-sheet.xlsx`, `office-open.odt` (uploaded by member `anna`), `barcode-batch-desktop.pdf` (split by barcode), `office-slides.pptx` (mobile UI upload while the API was down).

## What I verified (evidence summary)

**Account isolation (owner, anna, bruno).** anna gets 404 for the owner's document, its original, share link, bundle and Trash; the admin owner also gets 404 for anna's document (admins do not see members' archives). Shared *view* → read 200, edit 403, cannot create links, cannot re-share to bruno (404). Shared *edit* → edit 200, still no Trash, no links. Non-admin `GET /api/people` returns only id/username/name (needed for sharing).

**CSRF / headers.** POST without `X-CSRFToken` → 403; correct token with `Origin: http://evil.example` → 403 with a translated message; no CORS headers for a foreign origin; CSP `default-src 'self' … frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, API `Cache-Control: private, no-store`. Session cookie HttpOnly + SameSite=Lax (Secure is off only because this judge stack runs `RIPIANO_DEBUG=1` on http; compose default is `0`). `/admin/` redirects to `/` at the proxy; admin login POST 403.

**API tokens.** Creating one needs the password (wrong → 400). A token can read/download/edit, but is refused (403, clear message) for share links, bundles, agents, password, people, workflows, object access, backups, new tokens, sign-out, `/api/%61gents`, `/api/share-bundles/`, document email. `Bearer`/lowercase schemes → 401; token on `/mcp` → 401.

**Share links and bundles — D11 and D9.** Anonymous downloads before: 200, `no-store`, SHA-256 of `judge.png` original matches the fixture (`4d64026e2eea…`). Owner changes own password → owner link, owner bundle and the link created from a second ("stolen") session all → 404 `Link not found`; the stolen session → 401; the owner's API token and agent → 401; the current session stays signed in; anna's links are unaffected. List shows `revoked_reason: password_changed`; the document panel says "Revocato perché la password è cambiata" (screenshot `d-doc-share-links-ended.png`). Admin reset of anna (wrong admin password → 400) → anna's link and bundle 404, her old session ends. anna turned off → fresh link and bundle 404, login 401; turned on again → still 404 (`account_off`). Trash → link 404; Restore → link stays 404. Malformed tokens → 404.

**Agents (MCP).** Three grants: A `search+tag` filter Casa, B `search+text` filter Lavoro, C `search` only. `tools/list` returns exactly the permitted tools. A sees only Casa documents, B only Lavoro, C all titles. C and A searching an OCR-only word (`heron`, page 2 of `three-pages.pdf`) get no results; C/A `get_document_text` → "Tool is not permitted"; B on a Casa document or on anna's document → "not found within this grant". A adding B's filter tag → refused with an explicit message. **Workflow started by an agent:** owner workflow "updated + tag Urgente → add Lavoro, share with bruno"; A adds Urgente → run detail "skipped tag Lavoro (it limits another agent's access and an agent made the change), shared with bruno (view)"; B's view unchanged. MCP transport: foreign `Origin` 403, foreign `Host` 421, no/garbage token 401, agent token on `/api` 401. Deleting a tag that limits an active agent → 409 with a clear message. Revoke B → 401 at once; removing B with its log without a password → 400 (D10). Audit list shows ok/denied/error entries with document titles, no text (`d-agents.png`).

**Recovery.** Backup → `down -v` (media, postgres and sources volumes removed; backup is a bind mount) → empty `db broker api` migrated through `0061` → restore → `up -d`: 17 documents identical, 17 original SHA-256 identical, tags identical, sticker `R-DMH9QZDS` → `Drill shelf J3 / Drill box J3`, anna/bruno sign in, anna's own and shared documents, document-access grant (edit), workflow, ended links/bundles with reasons, active link still 200, agents: active 200 / revoked 401. **RESTORE VERIFIED** on my stack. Uploads during a broker outage (existing session) return 202 and are processed after the broker returns. API restart during a 6-upload loop: 2×202, 3×502, then 202, no orphans. Mobile PWA upload with the API stopped was held and sent automatically when the API returned (17 → 18 documents, `m-upload-*.png`). An interrupted barcode split, recovered by the stale-job task, produced no duplicate children.

## Scores

| Dimension | Weight | Score | Evidence | Not exercisable / not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | 8 fixture types reach `ready` (PDF OCR, PNG, DOCX/XLSX/ODT/PPTX conversion, EML, barcode split); mobile upload while the server is down is queued and sent without user action; no mandatory TODO screen. | Filing-suggestion learning and correcting an uncertain suggestion (other judges' emphasis); camera scan; Telegram/watched folder (real accounts out of scope by D7). The one capture defect I found is reliability-related (M1). |
| Retrieval and physical filing | 20% | 9.0 | OCR phrase found by a text-scoped agent and hidden from others; tag filters; sticker lookup with nested location survives a clean restore; paper copy creation from the document. | Label printing and camera sticker scan; Library search UI only lightly touched. |
| UX and accessibility | 20% | 8.8 | Italian throughout; D11/D9 reasons shown in plain words on links and bundles; keyboard Enter on "Reimposta password" moves focus into the new-password field; the reset text explains exactly what ends; mobile library and upload status fit 390 px. | Real installed PWAs and Android client (D7). Defects: L1–L3. |
| Reliability and recovery | 20% | 8.3 | Clean backup → `down -v` → restore passed with checksums, locations, permissions and revoked grants; broker/API outages lose no uploads; interrupted split recovers idempotently. | DS923+ restore (D7). Defects: **H1** (MCP dead after a DB restart), M1 (stuck "processing" up to 1 h with no action), L4 (health check blind to DB/broker), L5 (sign-in 500 while broker down). |
| Privacy and agent control | 15% | 9.4 | Two (three) agents with different scopes and filters, tool lists, audit, revoke, no content without text permission, guarded tags also inside agent-started workflows, token boundaries, D9/D10/D11 all verified live. | Real cloud MCP client (used raw JSON-RPC instead). Minor: L3 (revoked agents don't say why). |

**Weighted mean: 0.25·9.0 + 0.20·9.0 + 0.20·8.8 + 0.20·8.3 + 0.15·9.4 = 8.88**

## Hard gates

| Gate | Result |
| --- | --- |
| 1. Parity scenarios | Not re-audited row by row by me; the rows I touched (sharing, links, bundles, agents, workflows, backups, physical copies) work. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **Demonstrated on my own stack** (setup in browser, uploads, backup `20261119T153334822719Z-1b70f292`, `down -v`, restore, originals/tags/locations/permissions/revoked grants verified). `.omo/evidence/restore-drill-round9.md` is consistent with this. |
| 3. Real iOS/Android PWA and native Android capture | Out of scope by owner decision (D7). |
| 4. Security review | Demonstrated for account and agent isolation, token revocation, CSRF, origin checks, D9/D10/D11, no content to agents without text scope, no provider calls. Upload validation and external-input boundaries not specifically fuzzed this round. |
| 5. Tests, builds, journeys, migrations | **Credible.** I re-ran the API suite: `372 passed, 15 skipped in 64.64s`, matching the record (`372 passed, 15 skipped in 65.74s`); migration `0061` was present and applied on an empty DB during my restore. Build and e2e not re-run (forbidden). The one recorded e2e flake is plausibly explained (shared account across two workers). Note: no test covers H1 (MCP after a database reconnect). |
| DS923+ performance, Synology ACLs, NAS restore, real Telegram/cloud accounts | Out of scope by owner decision (D7). |

## Findings

### Severe
None.

### High

**H1 — After the database restarts, every MCP agent request fails with HTTP 500 until the `mcp` container is restarted by hand.**
Repro: with a working agent (`tools/list` → 200), run `docker compose -p ripiano-j3 … stop db`, then `start db` (or let PostgreSQL be OOM-killed/updated on its own). The API, workers and PWA recover by themselves; `POST /mcp` with a valid bearer token keeps answering 500 (`django.db.utils.OperationalError: the connection is closed` / `terminating connection due to administrator command` in `mcp` logs). I re-checked three times over ~4 minutes: all three agents `[500, 500, 500]`. Only restarting `mcp` (here: the restore's `up -d`) fixed it. Revoked agents still could not get in (fails closed), but every agent — the owner's main AI path per D1 — is silently down, the owner's activity log shows nothing, and Docker shows `mcp` as plain "Up".
Cause: `services/api/archive/mcp_server.py:108-116` (`GrantVerifier.lookup`), `:129-133` (`_grant`), `:321-345` (`_list_allowed`, `_call`) run ORM queries through `sync_to_async` in a long-lived Uvicorn process without `django.db.close_old_connections()` (Django only does this around its own request cycle), so the broken connection is reused forever; `compose.yaml:134-141` gives `mcp` no healthcheck, so nothing restarts it. On a 4 GB DS923+ a PostgreSQL restart alone is realistic.

### Medium

**M1 — A document whose worker is killed mid-processing stays "processing" for up to an hour, with no action available.**
Repro: upload `three-pages.pdf`, `barcode-batch-desktop.pdf`, `judge.png`; `docker compose … kill worker` ~2 s later; `start worker`. The pending file finishes, but `barcode-batch-desktop` stays `processing` (still so after 3+ minutes; `/api/jobs` lists it with `can_cancel: false`). Retry → 409 "Only failed documents can be retried", Cancel → 409 "already being processed and cannot be stopped midway", Reprocess → 409. It is only recovered by `reconcile_pending_documents` after `processing_started_at` is 1 h old (`services/api/archive/tasks.py:218-227`; `job_views.py:160-163`), plus Redis' 1 h visibility timeout with `CELERY_TASK_ACKS_LATE`. I simulated the hour: recovery was clean and did not duplicate the split children. Suggest: on worker start, reset `processing` rows not held by a live task, or allow retry after a few minutes without progress.

### Low

- **L1 — Field hints are read as part of the label without a space.** Accessible names such as "Nuova password per annaAlmeno 12 caratteri", "NomeFacoltativo", "La tua passwordServe per aggiungere persone…" (Persone screen, aria snapshot). Cause: `apps/web/src/ui.tsx:59` puts `{label}{hint && <small>{hint}</small>}` inside one `<label>`; use `aria-describedby` for the hint or add a separator.
- **L2 — Semantic-search warning box breaks its sentence into three columns** ("Passa a" | `pgvector/pgvector:pg17` | "prima di attivarla (vedi il README).") on desktop Agenti (`d-agents.png`, bottom).
- **L3 — Revoked agents don't say why.** The "pre-pw" agent ended by the password change is shown only as "Revocato", while links and bundles now show "Revocato perché la password è cambiata". Same D11 cause, inconsistent explanation.
- **L4 — `/healthz` returns `{"status":"ok"}` with the database or the broker stopped** (`services/api/archive/views.py:300-301`), so the api container stays "healthy" while every request fails with 500.
- **L5 — Sign-in fails with HTTP 500 while the broker (Valkey) is down**, because the sign-in throttle reads the Redis cache without a fallback (`archive/throttle.py:20`); signed-in sessions keep working and their uploads are processed later. On this judge stack (`RIPIANO_DEBUG=1`) the 500 is a Django debug page; with the compose default it would be a generic 500.

## Single most serious finding

**H1:** a PostgreSQL restart leaves the MCP server permanently returning HTTP 500 to every agent until someone restarts the `mcp` container by hand. There is no healthcheck to catch it and nothing about it in the owner's activity log (`mcp_server.py:108-133, 321-345`; `compose.yaml:134-141`).
