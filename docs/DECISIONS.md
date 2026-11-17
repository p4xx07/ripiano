# Agreed decisions

Decisions agreed with the project owner that are not yet fully implemented. Read this before starting any of the work below; it overrides older wording in other planning documents where they conflict. Add new decisions with a date; do not silently rewrite old ones.

Status keys: **Agreed** (decided, not started), **In progress**, **Done** (link the commit).

## Status snapshot — 2026-11-17

- Branch `codex/initial-implementation` (draft PR #1). Do not merge into `main` until every parity row is verified and the 9.5 judge score is reached (see [QUALITY_JUDGES.md](QUALITY_JUDGES.md)).
- Roughly 85% of [FEATURE_PARITY.md](FEATURE_PARITY.md) is implemented (counting partial rows as half); 0 rows are verified for R4.
- Latest slices: `0640042` hide Library batch controls until a document is selected; `bbe32e3` "Unlock PDFs" workflow action (password removal). The unlock action still needs a live-browser run and an independent review in `.omo/evidence/`.

## D1 — AI goes through MCP only (2026-11-17) — Agreed

- Ripiano itself never calls a paid remote LLM provider (no Claude/OpenAI API keys in the server). Reason: the archive is mainly for the owner, who works through MCP clients, and per-use API costs are too high.
- "AI suggestions" and "document chat" from the Paperless parity row are served through MCP agents (existing grants, the optional local Mac worker in `agents/local_classifier/`). Record this in FEATURE_PARITY.md as an intentional behavior change, not as a missing feature.
- A local Ollama endpoint on the owner's Mac (OpenAI-compatible API) must be supported as an option, never required.
- paperless-ai and paperless-gpt are **not** used: they are extra always-on containers that need an LLM provider.

## D2 — Semantic search / RAG (2026-11-17) — Done (owner decision 2026-11-17: every mode optional, chosen in settings)

Ripiano finds passages; the MCP client's own model writes answers. Ripiano does not generate text.

1. Postgres image moves from `postgres:17.6-bookworm` to the pgvector image for the same major version (`pgvector/pgvector:pg17`, digest-pinned). Same PostgreSQL major, so existing data carries over.
2. Documents are split into passages; a background job creates embeddings for new and changed documents, plus a management command to rebuild all of them.
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
- Library "Related by meaning" (top 5, similarity ≥ 0.3) and MCP `semantic_search` (scope `documents:text`, grant filter applied).
- Verified end to end with the real model on pgvector: 3 of 4 bilingual test questions ranked the right document first; first model load 17.5 s.
- Not done: merging meaning results into the main Library ranking (hybrid ranking); measuring on the DS923+ itself.

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

## D6 — Sources: external storage set up in the app (2026-11-17) — In progress

The owner wants external storage to work like Synology Hyper Backup destinations: log in to the service inside Ripiano, choose a folder with filters and a recursive option, and Ripiano uses it as an input channel. Telegram must work the same way: paste the bot token in Ripiano, and files sent to the bot become documents. No Compose profiles or environment variables for inputs.

- Done (S3): `StorageSource` model and **Sources** screen; engine in `services/api/archive/storage_sources.py` (Backend interface: `entries`, `download`, `move`, `delete`, `processed_entries`), polled every minute by `archive.tasks.poll_storage_sources` on the maintenance queue with a per-source claim. The env-based `s3_input` command and `s3` Compose profile from `d1bc2c8` were removed.
- Each file version is recorded in `StorageSourceSeen`, so a deleted document is not re-imported. Moves happen only after the original is stored.
- Only the archive owner may use home-network addresses; others need public `https://` endpoints.
- Verified live against SeaweedFS through the UI: preview, filters, recursive import, move to `processed/<date>/`, no second import.
- Next, in order: WebDAV (Nextcloud, Synology WebDAV, ownCloud), Telegram bot (token pasted in the app; replaces the `telegram` profile), watched folder (choose subfolders of a mounted root in the app), then Google Drive / OneDrive / Dropbox (need OAuth app registration by the owner).

## Remaining work that needs no further decision

In the owner's suggested order:

1. ~~Task controls (cancel/requeue) for background jobs other than backups and NAS browse copies.~~ Done 2026-11-17 (`1aa3872`): Background jobs section on Overview; see README "Overview".
2. Permissions on tags, senders, types, and saved views.
3. API request/response body schemas in `/api/schema.json` and a versioned compatibility test suite.
4. Italian translation of the remaining screens and API messages.
5. Keyboard shortcuts and an accessibility pass.

Not possible without the owner's hardware: real iOS/Android device tests, Synology ACL/restore checks, published digest-pinned images, and the R4 parity verification.
