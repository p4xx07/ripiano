# Ripiano

Ripiano is a self-hosted document archive for a NAS. It combines quick mobile capture, automatic filing, full-text search, and a simple way to locate paper originals with stickers. The web app is an installable PWA for iOS and Android. An Android client shares the web interface and adds a native document scanner.

Ripiano is an independent implementation. Paperless-ngx v3.4.2 is the capability baseline, not a backend dependency or a workflow template. The product target is feature parity with that release plus a better day-to-day filing process.

## Planning documents

- [Product specification](docs/PRODUCT_SPEC.md): users, workflows, interaction design, and acceptance criteria.
- [Feature parity](docs/FEATURE_PARITY.md): Paperless capabilities and Ripiano delivery gates.
- [Architecture](docs/ARCHITECTURE.md): services, data model, classification, agents, security, deployment, and backup.
- [Backup and restore](docs/BACKUP_RESTORE.md): mounted volume layout, schedule, and clean-stack recovery.
- [Agent access](docs/AGENT_ACCESS.md): named MCP grants, permissions, and privacy boundaries.
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): build order and verification gates.
- [Quality judges](docs/QUALITY_JUDGES.md): the 9.5 target, independent review rubric, and release blockers.

## First implementation slice

The current slice has owner setup and sign-in, PDF/JPEG/PNG upload, preserved originals, background OCR to PDF/A, text search, a responsive installable PWA, scheduled or manual checksum-verified backups, tags, local phrase-based automatic filing, a physical archive, and named MCP agent grants. Camera, gallery, and file selection are available through the browser. Paper copies can receive a stable sticker and QR label, be placed in nested locations, and be found again from a sticker link. An agent can be given separate search, OCR-text, and tag-changing permissions, with optional tag filtering, expiry, revocation, and an activity log. Failed OCR can be retried, and the searchable PDF can be opened directly. This is the beginning of the staged implementation, not the complete Paperless feature set. Native Android scanning, pretrained classification, automatic OAuth agent sign-in, and the rest of the [parity matrix](docs/FEATURE_PARITY.md) are still to be built.

### Run locally

1. Copy `.env.example` to `.env` and replace the three example secrets with strong unique values.
2. Run `docker compose up --build -d` from this directory.
3. Open `http://localhost:8080`. Enter the `RIPIANO_SETUP_KEY` from `.env` to create the owner account.

For a NAS deployment, set `RIPIANO_DEBUG=0`, an HTTPS `RIPIANO_PUBLIC_ORIGIN`, the reverse proxy host in `RIPIANO_ALLOWED_HOSTS`, and bind `RIPIANO_MEDIA_PATH`, `RIPIANO_DB_PATH`, and `RIPIANO_BACKUP_PATH` to persistent NAS folders. Give UID 10001 write access to the media and backup folders. The Compose stack exposes only the web service. Place HTTPS in front of it with Synology's reverse proxy. These current `build:` definitions require a Portainer environment that can build from the checked-out repository; a pinned GHCR release stack follows in a later milestone. A local clean-stack restore passed, but NAS-specific permissions and restore still need verification before storing real documents.

### Work on the services

- API: `cd services/api && uv sync && RIPIANO_DEBUG=1 uv run pytest -q`
- Web: `cd apps/web && npm ci && npm run build`
- Browser journey (running local stack and a disposable owner account): `cd apps/web && RIPIANO_E2E_ORIGIN=http://localhost:8080 RIPIANO_E2E_USERNAME=... RIPIANO_E2E_PASSWORD=... npm run test:e2e`. This creates test documents, tags, and locations in that account.

The document originals are stored under the mounted media path. OCR output is derived and can be rebuilt. The current search is text-only and lists 50 results at a time; richer filters and pagination are scheduled for the next slices.

### Optional Telegram input

Create a bot with BotFather. Set `RIPIANO_TELEGRAM_BOT_TOKEN` and `RIPIANO_TELEGRAM_OWNER_USERNAME` in `.env`, then run `docker compose --profile telegram up -d`. Send `/start` to the bot in a private chat; it returns your numeric chat ID. Put that ID in `RIPIANO_TELEGRAM_ALLOWED_CHAT_IDS` and restart the Telegram service. You can now send or forward PDF, JPEG, PNG, or photos to the bot. Each accepted file enters the same OCR and search pipeline as web uploads. For multiple people, list IDs separated by commas; all currently file into the configured owner archive. Only private chats are accepted, and the bot exposes no inbound NAS port.

Telegram's [Bot API limits standard bot downloads to 20 MB](https://core.telegram.org/bots/api#getfile). Telegram handles the file before Ripiano downloads it, so use the direct app upload when the document must never pass through Telegram. Updates remain on Telegram for at most 24 hours; prolonged NAS downtime can miss messages. The bot token must remain secret.

The planning documents remain the implementation baseline. No Paperless source code is included in this repository.
