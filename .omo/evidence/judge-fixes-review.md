# Independent review: judge-fix changes (2026-11-18)

## Scope

- Commit `b4cb086` (API-token outbound blocking, offline upload queue, error parsing, single manual backup, nginx real_ip + JSON 413, document history, search syntax, semantic_rebuild).
- Uncommitted working tree on `codex/initial-implementation`: date/sender detection (`archive/date_detection.py`, migration `0054_document_date_origin`), location PATCH/DELETE and label layout (`archive/physical_views.py`, `PhysicalPanel.tsx`), readable job errors (`tasks.readable_error`), MCP semantic-tool hiding and audit document id (`mcp_server.py`), navigation/accessibility changes (`App.tsx`, `DocumentPanel.tsx`, `AgentPanel.tsx`, `i18n.ts`, `style.css`).
- Not run: Docker, Playwright (shared stack in use).

## Commands

| Command | Result |
|---|---|
| `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` | 297 passed, 9 skipped (49 s) |
| `cd apps/web && npx tsc --noEmit -p .` | exit 0, no errors |
| `search_syntax.parse` probes (`date:>9999`, `date:<0001`, `a OR OR b`, `"date:2026"`, `-`) | see finding L1 / L7 |

## Findings

### High

**H1. The offline queue permanently deletes queued files on any non-network error** — `apps/web/src/App.tsx:1029-1033` (`sendWaiting`).
Only 0/502/503/504 stop the loop; every other failure calls `uploadQueue.forget(item.id)`. That includes 401/403 (signed out or session expired, CSRF failure), 429, 500 (database hiccup, disk full during write), and a 200 that is not JSON (captive-portal or misrouted HTML gives `ApiError(status 200)` in `api.ts:255`).
Scenarios:
- Person A takes 10 scans offline, comes back online, and the flush starts. A signs out while the first large file is still uploading. Every remaining item gets 401/403 and is deleted. A's scans are gone. If B signs in quickly, `owner` is still A from the closure. The loop keeps posting with B's cookie, so A's files are filed into B's account. The loop does not check `session.username` again on each pass.
- The app stays open while the device is offline past session expiry. On `online`, the stale `session.authenticated` triggers the flush, each POST returns 401, and the whole queue is erased. The person only sees the "rejected" report.
- A transient 500 during the flush drops the file instead of retrying it.
Fix: forget only on definite content refusals (400/413/415/409). Stop and keep the item on 401/403/429/5xx/unexpected. Abort the loop when the signed-in username changes (re-read the session before each item, or pass an AbortController that `signOut` cancels).

### Medium

**M1. Queued uploads survive sign-out on a shared device** — `apps/web/src/App.tsx:1114-1125` (`signOut`), `apps/web/src/uploadQueue.ts`.
Sign-out clears documents and the selection but leaves `ripiano-uploads` in IndexedDB. On a shared or family tablet, the next person (or anyone with devtools) can read A's queued originals, and they stay until A signs in again on that browser. Sign-out should either warn ("N files are still waiting; sign out and discard them?") or delete the owner's entries. The parity text should also stop saying entries are private to the person.

**M2. nginx `real_ip` trusts every private range, including the Docker bridge gateway** — `apps/web/nginx.conf:9-15`.
Behind Traefik (which overwrites untrusted XFF) or the Synology reverse proxy (which appends), `real_ip_recursive on` picks the rightmost untrusted address, so internet clients cannot spoof through those paths. That part is correct. But:
- Any LAN or VPN client (192.168.x, 10.x) can send `X-Forwarded-For: 203.0.113.N`. nginx walks past the trusted client address and adopts the spoofed one, so a different N on every request bypasses the per-IP sign-in throttle (`throttle.py:13` keys on `X-Real-IP`).
- If port 8080 is published and reached directly (router port-forward to the NAS, or a Docker setup that uses userland-proxy, where `$remote_addr` becomes `172.17.0.1`), an internet client is "trusted" and can do the same.
Mitigation: trust only the known proxy addresses (Pi gateway IP, Docker gateway) via an env-templated `set_real_ip_from`, and keep the per-username throttle key as the main brute-force control. If that key already exists in `sign_in_throttle_key`, say so in the docs.

### Low

- **L1. Date comparisons at the calendar edges leak raw Python errors** — `archive/search_syntax.py:58-61`. `date:>9999` gives `400 "year 10000 is out of range"`, and `date:<0001` gives `"ordinal must be >= 1"`. These are untranslated and not `DATE_HELP`. Wrap `date.fromordinal` with `except (ValueError, OverflowError): raise ValueError(DATE_HELP)`.
- **L2. "One backup at a time" is enforced only for manual POST** — `archive/job_views.py:41-45` (retry) and `archive/tasks.py:199` (schedule) create runs without checking for an active run. The `flock` in `backup.py:166-170` prevents two concurrent snapshots, so the effect is a spurious FAILED run ("Another backup is already running"), not corruption. On SQLite (dev) there is no advisory lock, so two simultaneous POSTs can both pass the `.first()` check. Postgres is fine.
- **L3. The upload-queue comment says a retry "never creates a duplicate"** — `uploadQueue.ts:3`. Web uploads have no idempotency key (only Android `scan_id`, `views.py:600`). A retry after a lost 502 response creates a second document flagged `duplicate_of` (`ingestion.py:45`). Either send a client-generated id like the Android path or fix the comment and docs.
- **L4. History shows people the owner shared with the owner's automation names** — `archive/history.py:93-105`. `actor_label` (mail rule, source, workflow, and agent grant names) and the actor username are returned for non-owner viewers. Owner-only *fields* are filtered, but labels are not. Consider showing only the actor kind to non-owners.
- **L5. API tokens can still share filing objects and saved views with other people** — `api_tokens.py:16`. `/api/object-access/...` POST/PATCH/DELETE is not in `BLOCKED_PREFIXES`. It grants no document access (`object_access.py` docstring), but it is "sharing with people", which the token policy says tokens cannot manage. Path-variant bypasses checked and not possible: Django routes are case-sensitive, `//api/...` and trailing slashes do not resolve, and `request.path` is percent-decoded.
- **L6. The upload queue is keyed by username** — `uploadQueue.ts:10`. If an account is deleted and the username reused on the same browser, the new account receives the old person's queued files. This is rare and needs owner action.
- **L7. Quoted field terms are still parsed as fields** — `search_syntax.py:98-110`. `shlex` drops the quotes, so `"date:2026"` cannot be searched as literal text. Cosmetic.
- **L8. Location PATCH relies on `select_for_update` for cycle safety** — `physical_views.py:128`. This is a no-op on SQLite, so two concurrent moves could create a cycle in dev only. Postgres is fine.

### Checked and found correct

- **Token blocking.** Outbound prefixes cover mail, sources, source-apps, workflows, backups, restore, browse exports, semantic settings, and trash retention. `/documents/<id>/email` is blocked for all methods, and `/shares` and `/access` writes are blocked. Share-link listing does not return tokens (hash only; URL only on create).
- **History authorization.** `document_history` uses `access.readable`. Non-owners have `storage_path`, `asn`, and `custom_field` changes removed, and diff events that end up empty are dropped. No document text, OCR, or notes are stored. Event writes share the edit transaction (a failure rolls back the save, which is acceptable). Detection history failures are caught in `tasks.py`.
- **Migration 0054.** It marks every existing dated document `manual` and also marks documents whose date a person cleared (from 0053 events). Detection fills only a NULL date whose origin is not `manual`, under `select_for_update`, and skips trashed documents. Single and bulk date edits by people and sharees set `manual`. No other code path writes `document_date`.
- **Location PATCH/DELETE.** Owner-scoped at every lookup (`_location` filters on owner, and an invalid UUID returns 400). It rejects a parent that is the location itself or a descendant, rejects duplicate names among siblings, and DELETE refuses when the location has children or copies (including copies of documents in Trash).
- **MCP.** `semantic_search` is hidden from the list when the feature is off. The audit `document_id` is looked up only within the grant owner's documents, and nothing more is returned to the agent.
- **API contract.** `api_contract_v1.json` gained 99 lines with no removals. `document_date_origin` is an added field only.
- **Search blowup.** `q` is capped at 200 characters (`views.py:330`), so an OR chain is limited to about 66 terms. That is acceptable.

## Verdict

**Approve with required fix.** H1 is a real data-loss path in the offline queue (and can file one person's scans into another account) and should be fixed before release. M1 and M2 should be fixed or explicitly accepted by the owner. Everything else is low. The backend changes (token policy, history access, date detection, migration 0054, location editing) are sound, and the tests and typecheck pass.

## Resolution (main session, 2026-11-18)

- **H1 fixed:** the offline queue removes a file only when the server refuses the file itself (400/409/413/415). Any other answer (401/403, 429, 5xx, a captive-portal page, no answer) keeps it and stops the pass. The loop stops as soon as the signed-in user changes, so files are never sent into another account (`App.tsx` `sendWaiting`, `uploadQueue.isRefusal`).
- **M1 fixed:** with files still waiting, Sign out first asks: keep them for the next sign-in on this device, discard them, or stay signed in (`App.tsx` `requestSignOut`, `uploadQueue.forgetAll`).
- **M2 fixed:** nginx no longer trusts every private range. It trusts only localhost and Docker networks (how the Synology proxy on the same NAS arrives), plus addresses in `RIPIANO_TRUSTED_PROXIES` (for example the Pi gateway), generated at container start by `apps/web/real-ip.sh`; invalid entries are ignored. Documented in both Compose files, `deploy/portainer.env.example`, and `deploy/gateway/README.md`.
- **Low fixed:** `date:>9999`, `date:<0001` and similar now return the readable date message (`search_syntax.date_range`, tested). The upload-queue comment no longer claims retries can't duplicate (exact copies are flagged for duplicate review instead).
- **Low, left as documented behavior:** retries and scheduled backups are serialized by the existing backup lock; history shows rule/workflow/agent names to share recipients (the owner chose to share the document; no content is exposed); API tokens may share tags/saved views (no document access); upload-queue entries keyed by username; quoted `"date:…"` still parsed as a field; SQLite-only row-lock gap for location moves (production uses PostgreSQL).
