# Agreed decisions

Decisions agreed with the project owner that are not yet fully implemented. Read this before starting any of the work below; it overrides older wording in other planning documents where they conflict. Add new decisions with a date; do not silently rewrite old ones.

Status keys: **Agreed** (decided, not started), **In progress**, **Done** (link the commit).

## Status snapshot — 2026-11-22

- `main` contains merge `618e7f8` and pre-release tag `v0.1.0-rc.1`. Round 14 on branch candidate `8a1ab1a` scored 9.410, 9.375 and 9.465 (mean **9.42**), up from round 12's 9.23. Every dimension is at least 9.0, but the 9.5 target in [QUALITY_JUDGES.md](QUALITY_JUDGES.md) has **not** been met. The merge and tag do not establish a final release score. The five items in "Remaining work that needs no further decision" are implemented; their individual statuses below are the source of truth.
- Sources are configured in the app: S3-compatible storage, WebDAV, NAS folders, the built-in consume folder, Google Drive, OneDrive, Dropbox, and Telegram. Cloud connections and Telegram still need real-account validation; the consume folder needs deployment validation on the NAS.
- Semantic search is optional and off by default. Plain-language Library searches now merge keyword and meaning hits into one ranking when semantic search is on; field searches and other sorts stay keyword-based. The NAS embedder's measured memory cost is about 780 MB with its model loaded, so the owner must opt in.
- Round 14 reports and clean-stack restore drills are in `.omo/evidence/`. The round-13 follow-up (`5afee4e`) addressed owner-facing stopped OCR guidance and email-header boilerplate suggestions. Round 14 found a further medium gap: members opening shared pending documents did not see the stopped-worker explanation. The follow-up fix adds per-document status to the shared detail response and panel; it passed focused API and desktop/mobile browser checks. See [round14-summary.md](../.omo/evidence/round14-summary.md) and [HANDOFF_2026-11-22.md](HANDOFF_2026-11-22.md).
- The owner accepted the round-14 score of 9.42 for personal testing and requested no further judge round after the focused fix. That score belongs to the pre-fix candidate; the changed code has no new numeric score. Row-by-row R4 parity verification and owner-side checks remain open. Round 14 demonstrated clean-stack restore on the pre-fix candidate.

## D1 — AI goes through MCP only (2026-11-17) — Agreed

- Ripiano itself never calls a paid remote LLM provider (no Claude/OpenAI API keys in the server). Reason: the archive is mainly for the owner, who works through MCP clients, and per-use API costs are too high.
- "AI suggestions" and "document chat" from the Paperless parity row are served through MCP agents (existing grants, the optional local Mac worker in `agents/local_classifier/`). Record this in FEATURE_PARITY.md as an intentional behavior change, not as a missing feature.
- A local Ollama endpoint on the owner's Mac (OpenAI-compatible API) must be supported as an option, never required.
- paperless-ai and paperless-gpt are **not** used: they are extra always-on containers that need an LLM provider.

## D2 — Semantic search / RAG (2026-11-17) — Done (owner decision 2026-11-17: every mode optional, chosen in settings)

Ripiano finds passages; the MCP client's own model writes answers. Ripiano does not generate text.

1. Postgres image moves from `postgres:17.6-bookworm` to the pgvector image for the same major version (`pgvector/pgvector:pg17`, digest-pinned). Same PostgreSQL major, so existing data carries over.
2. Documents are split into passages; a background job creates embeddings for new and changed documents, plus a management command to rebuild all of them (`manage.py semantic_rebuild [--owner NAME]`).
3. **Both embedding backends**, chosen by the owner in settings:
   - **NAS (default):** a small multilingual model inside the worker (fastembed/ONNX, e.g. multilingual-e5-small, Italian + English). No torch.
   - **Ollama on the Mac:** optional endpoint URL + model name; indexing pauses while the Mac is off.
4. Hybrid search: PostgreSQL full-text + vector results merged (reciprocal rank fusion) in the Library and the API.
5. MCP tool `semantic_search` returning passages with document IDs, enforcing each agent grant's scopes and document filters.
6. No LangChain/LlamaIndex: pgvector + simple chunking is enough for one personal archive.

**Built 2026-11-17 after the owner chose "all optional, toggleable in settings":**

- Settings card under **Agents → Search by meaning** (archive owner): Off (default) / Ollama on another computer / On the NAS, optional model name, and "keep the model loaded" (off = unload after 10 idle minutes).
- One code path: Ripiano calls an Ollama-compatible `POST /api/embed` endpoint. The NAS option is the `embedder` Compose service (`manage.py semantic_embedder`), which installs the hash-pinned `semantic-requirements.txt` into its own volume on first start, so the Ripiano image does not grow. The API process never loads a model.
- pgvector is created only when the feature is switched on; the Postgres image is `RIPIANO_DB_IMAGE` (default unchanged). On a database without pgvector, enabling is refused with instructions and everything else keeps working (full suite verified on plain postgres:17.6).
- Library hybrid ranking (keyword and meaning hits merged with reciprocal rank fusion, similarity ≥ 0.3) and MCP `semantic_search` (scope `documents:text`, grant filter applied).
- Verified end to end with the real model on pgvector: 3 of 4 bilingual test questions ranked the right document first; first model load 17.5 s.
- Still not measured on the DS923+ itself; a real NAS performance check remains an R4 gate.

**Measured 2026-11-17 (before building):**

| Item | Measurement (Apple Silicon, one thread; the DS923+ CPU is slower) |
| --- | --- |
| fastembed packages (onnxruntime, numpy, tokenizers, huggingface-hub, …) | about 146 MB installed (onnxruntime alone 80 MB) |
| Smallest multilingual model offered by fastembed (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions) | 240 MB download; multilingual-e5-small is not offered |
| RAM with the model loaded | about **780 MB**, independent of batch size |
| Speed | about 100 passages of ~1,200 characters in 2.6 s (expect roughly 3–5× slower on the NAS) |

The RAM figure is much higher than the earlier ~300 MB estimate; on a 4 GB DS923+ that is significant next to PostgreSQL, OCR, and other services. Search queries also need the model, so it cannot simply be loaded only during indexing without slow first searches.

**Constraint — the NAS must not get bloated or slow.** The NAS is a Synology DS923+ (4 GB RAM by default, no GPU). Run initial indexing at low priority in small batches. Measure image size, RAM, and indexing time, and record them in the docs. If any part of this work makes the NAS noticeably heavier or slower, stop and report it to the owner before continuing; the owner decides how to avoid it.

## D3 — External access gateway on the Raspberry Pi (2026-11-17) — In progress

Replaces earlier ideas of Kong, Authentik, Border0, or Pangolin.

- **Host:** the owner's always-on Raspberry Pi 4 (own LAN IP, should boot from SSD).
- **Gateway:** Traefik on the Pi owns ports 80 and 443. The Vodafone Power Station router forwards TCP 80 and 443 to the Pi (fixed IP via DHCP reservation). The Synology reverse proxy is no longer the public entry point; pointing the router back to the NAS is the rollback.
- **Certificates:** Traefik obtains per-subdomain Let's Encrypt certificates with the HTTP challenge (port 80). No DNS API is needed. The owner's dynamic DNS (openip, updated by the router) and the existing wildcard DNS record already resolve every subdomain to the home IP.
- **Sign-in:** Authelia (not Authentik — Authentik needs about 2 GB RAM; Authelia about 30–50 MB) as Traefik forward-auth. TOTP, about 30-day sessions, one session cookie for all subdomains.
- **Authelia is a separate gate.** Ripiano keeps its own accounts and sessions; no automatic account creation and no identity header trusted by Ripiano. A user signs in to Authelia, then to Ripiano; both sessions persist.
- **Subdomains, not paths:** `auth.<domain>`, `ripiano.<domain>`, `jellyfin.<domain>`, … Paths break the PWA scope and app cookies.
- **Gateway exceptions** (Ripiano or the app still authenticates these itself): Ripiano share-link/bundle paths, MCP and `/api` requests carrying a bearer token, Jellyfin native-app traffic.
- **Home access:** the owner reconfigures Pi-hole with a dnsmasq wildcard (`address=/<domain>/<Pi IP>`). If the router does not allow handing out the Pi as DNS server, Pi-hole takes over DHCP. Whether the router supports NAT loopback is unknown and not needed with this design.

Deliverables (written and tested locally on 2026-11-17, not yet deployed on the Pi):

| Path | Contents |
| --- | --- |
| `deploy/gateway/compose.yaml` | Traefik + Authelia, ARM64 images, digest-pinned |
| `deploy/gateway/traefik/routes.yaml` | File-provider routes to NAS IP:port per service, plus the exceptions above |
| `deploy/gateway/authelia/configuration.yml`, `users.yml` | Example config with placeholders; no real secrets in Git |
| `deploy/gateway/README.md` | Router forwards, Pi-hole, first start, adding a service, rollback |
| `deploy/gateway/gateway.env.example` | `.env` template (the `.env.example` name is blocked by the owner's tool permissions) |

Local test: the gateway ran with `traefik:v3.5.3` and `authelia/authelia:4.39.4` and a stand-in backend; every routing and bypass rule behaved as intended (see "What was tested" in the gateway README). The test found and fixed one bug: indented multi-line Traefik rules keep their line breaks in YAML and are rejected. Still to verify on the real setup: Let's Encrypt issuance, a full Authelia sign-in with TOTP, the Android app on a phone, and pinning image digests.

**Ripiano Android change — Done (`f05a9f3`):** the server screen has an optional **Sign-in address**. That origin may load inside the WebView (`Origin.allowedInApp`), so the Authelia cookie stays in the app; all other origins still open externally, and the scanner bridge and downloads stay bound to the Ripiano origin. Unit tests in `OriginTest`; debug APK builds. Needs a real-phone check behind the gateway.

## D4 — S3 import (2026-11-17) — Done (`d1bc2c8`), replaced by D6 the same day

- An optional input adapter using the shared ingestion contract in [ARCHITECTURE.md](ARCHITECTURE.md) (same path as the watched folder and Telegram).
- Any S3-compatible service; develop and test against MinIO.
- Least-privilege key limited to one bucket prefix; secret encrypted at rest like mailbox passwords; stable source reference (object key + version/ETag) so restarts never import twice.
- After a successful import the object moves to a `processed/` prefix. Processed objects are deleted after a grace period, **configurable, default 30 days**.
- Implementation: `services/api/archive/s3_input.py` (own SigV4 signer over httpx, no boto3) and `manage.py s3_input`, Compose profile `s3`. Processed objects land in `processed/<UTC date>/<original subpath>`; the grace period counts from the move (S3 LastModified). MinIO no longer publishes public Docker images (Docker Hub repository gone, quay.io needs a login), so the live test used SeaweedFS (`chrislusf/seaweedfs`), which validates signatures: a wrong secret is refused, unicode/space keys import, unsupported files stay, expiry deletes only after the grace period. Unit tests include the AWS documentation signing example.

## D5 — Google Drive import (2026-11-17) — Agreed in principle

- Import new files from one chosen Drive folder through the same ingestion contract, using OAuth like the existing Gmail connection (the same Google Cloud project can enable the Drive API) and the Drive changes list for incremental polling. Google Docs/Sheets are exported to PDF.
- Known limitation: a Google OAuth app left in "Testing" status gets refresh tokens that expire after 7 days. Tell the owner before building it.
- After-import behavior (leave the file or move it to an "Imported" folder) is not decided yet; ask.

## D6 — Sources: external storage set up in the app (2026-11-17) — Done (`59b67f5` … `fb0f2e7`)

The owner wants external storage to work like Synology Hyper Backup destinations: log in to the service inside Ripiano, choose a folder with filters and a recursive option, and Ripiano uses it as an input channel. Telegram must work the same way: paste the bot token in Ripiano, and files sent to the bot become documents. No Compose profiles or environment variables for inputs.

- Done (S3): `StorageSource` model and **Sources** screen; engine in `services/api/archive/storage_sources.py` (Backend interface: `entries`, `download`, `move`, `delete`, `processed_entries`), polled every minute by `archive.tasks.poll_storage_sources` on the maintenance queue with a per-source claim. The env-based `s3_input` command and `s3` Compose profile from `d1bc2c8` were removed.
- Each file version is recorded in `StorageSourceSeen`, so a deleted document is not re-imported. Moves happen only after the original is stored.
- Only the archive owner may use home-network addresses; others need public `https://` endpoints.
- Verified live against SeaweedFS through the UI: preview, filters, recursive import, move to `processed/<date>/`, no second import.
- Done (Telegram): kind `telegram` in the same model and screen (`services/api/archive/telegram.py`). The bot token is pasted in the app (encrypted, format-checked, verified with **Test** via getMe). Chats that write to the bot wait on the source card until the owner chooses **Allow**; groups and messages from other senders are ignored. Polled every minute with a non-blocking `getUpdates` (timeout 0) on the existing scheduler, so no extra process runs; the update offset is saved after each update. The old `telegram_input` command, `telegram` Compose profile, and `RIPIANO_TELEGRAM_*` variables were removed. Not tested against the real Telegram API (needs a bot token); the client is exercised against a fake Bot API.
- Done (WebDAV): `services/api/archive/webdav.py` (PROPFIND Depth 1 with recursion limits, GET, MKCOL + MOVE with `Overwrite: F`, DELETE; Basic auth with an encrypted password). Verified live against rclone's WebDAV server and with an in-memory Nextcloud-like fake in tests.
- Done (folder): `services/api/archive/folder_source.py`. One NAS folder is mounted with `RIPIANO_SOURCES_PATH` at `/sources` (read-only in the API for Preview, read-write in the maintenance worker); the archive owner adds folder sources for its subfolders in the app. Files changed in the last 60 s wait for the next check; symlinks, hidden files, and `..` are refused. The `watch` profile, `watch_folder` command, and `RIPIANO_WATCH_*` variables were removed.
- Done (cloud drives): `services/api/archive/cloud_sources.py` with Google Drive (Drive v3; Docs/Sheets/Slides exported to PDF; full `drive` scope for move/trash), OneDrive (Microsoft Graph; download via the pre-authenticated redirect without the token; rotated refresh tokens saved), and Dropbox (list_folder with cursor pagination; move_v2 with autorename). "Delete" uses each provider's trash. OAuth apps are stored by the archive owner under Sources → Sign-in apps (`CloudApp`, secret encrypted), with the Gmail/Outlook environment clients as fallback. Verified with fake provider APIs in tests and in the browser up to the Google consent redirect; not yet verified against real accounts (needs the owner's app registrations).
- Done (consume folder, owner request 2026-11-17): mounting `RIPIANO_CONSUME_PATH` at `/consume` is enough; a built-in folder source (`StorageSource.builtin`) is created automatically for the first archive owner by the every-minute source poll. It imports recursively and removes each file after it is stored (files must be unchanged for 60 s first). It can be paused or edited but not deleted, and its kind is fixed.
- Was "next": Google Drive / OneDrive / Dropbox (need OAuth app registration by the owner).

## D7 — Judging scope and release path (2026-11-18) — Agreed

- The quality judges (docs/QUALITY_JUDGES.md) score what a local stack and browser emulation can show. By owner decision the following are **out of scope for the judging rounds** and must not lower a score: installed iOS/Android PWA and native Android capture on real phones, real Telegram and cloud-drive accounts, and DS923+ checks (performance, Synology ACLs, a restore on the NAS). They stay listed as open owner-side checks; they are not claimed as demonstrated.
- Published images: once the judges reach an acceptable score, merge to `main`, create a **pre-release**, let the GitHub workflow build the images, and test those images. Do not merge or tag before that.
- Rounds so far (weighted mean of three judges): round 1 on `901d491` 7.12; round 2 on `f2b9416` 7.29. Reports are in `.omo/evidence/judge-*-report.md`.
- Round 3 on `d8724ff` has two reports so far: Judge 2 scored 8.48 and Judge 3 scored 8.67. Judge 1's report is absent, so there is no three-judge round score. Follow-up fixes in the working tree need a fresh candidate run; the earlier scores do not transfer.
- Later status: round 12 on `71315f4` scored 9.23 mean. Merge `618e7f8` and tag `v0.1.0-rc.1` were created despite the 9.5 threshold above; treat them as a pre-release checkpoint, not proof that the quality gate passed. Round 14 on `8a1ab1a` scored 9.42 mean after the round-13 fixes. On 2026-11-22 the owner accepted that score for personal testing, asked to fix the shared pending-document medium finding and explicitly waived another judge round. The score must not be represented as a new score for the changed code. See [round14-summary.md](../.omo/evidence/round14-summary.md).

## D8 — Search index languages (2026-11-18) — Agreed

Full-text search stores Italian and English stems plus the words as written (migration 0055, `archive/fulltext.py`). The owner accepted the disk cost (about 130 MB per 10,000 typical documents); do not drop English to save space.

## D9 — Deactivated accounts' public share links (2026-11-19) — Agreed

When an account is turned off, its public share links (single documents and bundles) stop working at once, as its sessions, API tokens and agents already do. Turning the account back on does not revive them silently: the owner decides again (implementation records how).

Implemented 2026-11-19: turning an account off (People) marks its active links and bundles revoked with `revoked_reason: "account_off"`, next to ending its sessions, API tokens, and agents (`people_views._end_access`). They answer exactly like an unknown link (404 `Link not found`) and stay revoked after the account is turned on again; the owner creates new links if still needed. The public link views also refuse any link whose owner is inactive, as a second guard.

## D10 — Removing a revoked agent's activity log (2026-11-19) — Agreed

Removing a revoked or expired agent together with its activity log (`DELETE /api/agents/<id>?forget=1`) asks for the owner's password, like creating an agent. The log is the audit trail, so deleting it is treated as a sensitive action.

Implemented 2026-11-19: the request carries `{"password": "..."}` in its JSON body and uses the same check, sign-in throttle, and messages as creating an agent (see [AGENT_ACCESS.md](AGENT_ACCESS.md)).

## D11 — Password changes end public share links (2026-11-19) — Agreed

A password change (`POST /api/account/password`) or an admin password reset (`PATCH /api/people/<id>` with `password`) ends that person's public share links and bundles, exactly as it already ends their API tokens and agents. Changing the password is the documented way to recover from a stolen session, and a link or bundle made from that session must not keep anonymous download access afterwards (judge 3 round 8, M1).

Implemented 2026-11-19: the same `pre_save` signal that revokes tokens and agents (`api_tokens.revoke_tokens_on_password_change`) marks the person's active links and bundles revoked with `revoked_reason: "password_changed"`. They answer exactly like an unknown link (404 `Link not found`) and are not revived; the share-link and bundle lists return the reason so the owner sees why they ended, and creates new links if still needed. Re-saving the same password hash (a Django hasher upgrade) revokes nothing.

## D12 — Workflows started by an agent do not share or send the document (2026-11-20) — default chosen while the owner was away — confirm

When an MCP agent's change (tags, sender, type) starts a workflow, the run holds back every action that discloses the document: sharing with people or groups, the webhook, and the email. Actions that stay inside the archive still run. Reason: an agent limited to "Add or remove tags" otherwise caused a private document to be shared with another person through the owner's workflow (judge 3 round 10, M1). This is the same rule as for tags that limit another agent's access.

Implemented 2026-11-20, widened the same day after the independent review (`.omo/evidence/round10-fixes-review.md`, M1 and M2):

- The decision is taken from the document, not only from who started the run. Disclosing actions are held back (a) in the run an agent's own change starts and (b) in every later run — scheduled, the owner's next edit, a bulk change — while the workflow's tag, sender, or type condition is met by a value an agent set (`DocumentTag.origin` / `correspondent_origin` / `document_type_origin` = `model`; `workflows.matched_by_agent`). What a held-back run files is given the same origin, so a chain of two workflows is covered.
- Released when a person sets that value themselves (an explicit tag add, choosing the sender or type; merely re-saving the unchanged tag list does not count), or with **Run now** for that document.
- A held-back run is marked `WorkflowRun.held_back` and recorded as "skipped sharing / webhook / email (an agent made the change)" (English and Italian); status `skipped` when nothing else happened. It does not use up the one-time webhook and email, which go out once with the first run allowed to send them. For scheduled workflows the held-back run is completed in place on a later daily pass.
- Held-back actions are never sent later by themselves. Documented in [AGENT_ACCESS.md](AGENT_ACCESS.md).

**Open for the owner:** this is the safe default, chosen without you. You may prefer an explicit per-workflow switch ("also run sharing and notifications when an agent made the change") for workflows you trust; say so and it will be added. Held-back runs are visible in the workflow's run history only; a place for them under Needs attention is not built yet.

## D13 — ASN barcode and paper sticker codes (2026-11-24) — Done (`f1df164`)

ASN is an optional numeric barcode field used by uploaded scans, including barcode-based page splitting. It is not the normal document code. Sequential topic codes such as `MED-00042` are the visible sticker codes for paper originals. Digital-only documents have no code by default; an advanced action can reserve a sticker code for a document that may be printed later. Reserving does not create a paper copy, and registering one later uses that same code. The paper-copy filter and paper archive must distinguish a reservation from actual paper.

## D14 — Server-neutral product and movable paper (2026-11-24) — In progress

Ripiano requires a server, but no particular server hardware or storage appliance. General UI and product documentation must use server-neutral language. Hardware-specific deployment instructions remain optional examples; older decisions above record the owner's setup rather than a product requirement.

A paper copy keeps its sticker code when moved, including to a newly created location. Creating `Shelf / Top / Row / Box` in one action reuses matching existing levels and creates missing levels. New paper stickers omit the current location so a move cannot make their printed text stale. Existing stickers with an old printed location can be reprinted if desired.

## Remaining work that needs no further decision

In the owner's suggested order:

1. ~~Task controls (cancel/requeue) for background jobs other than backups and NAS browse copies.~~ Done 2026-11-17 (`1aa3872`): Background jobs section on Overview; see [USER_GUIDE.md "Overview"](USER_GUIDE.md#overview).
2. ~~Permissions on tags, senders, types, and saved views.~~ Done 2026-11-17: `ObjectAccess` (view/edit per person or group), Share buttons, Shared with me filters, filing with shared objects; see [USER_GUIDE.md "People and sharing"](USER_GUIDE.md#people-and-sharing).
3. ~~API request/response body schemas in `/api/schema.json` and a versioned compatibility test suite.~~ Done 2026-11-17: `archive/api_contract.py`, `api_contract_v1.json`, `test_api_contract.py` (additions allowed; removals, type or status changes, and removed routes fail).
4. ~~Italian translation of the remaining screens and API messages.~~ Done 2026-11-17: every screen has English/Italian message files; ~130 more API messages translated (see [USER_GUIDE.md "Interface language"](USER_GUIDE.md#interface-language)).
5. ~~Keyboard shortcuts and an accessibility pass.~~ Done 2026-11-17: `?`, `G`+letter, `J`/`K`/Enter, skip link, heading/label fixes, `e2e/accessibility.spec.ts`. A full axe-core scan needs a new dev dependency the owner has not approved yet.

Not possible without the owner's hardware: real iOS/Android device tests, Synology ACL/restore checks, published digest-pinned images, and the R4 parity verification.
