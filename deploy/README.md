# Portainer on Synology

`compose.portainer.yaml` is the pull-only stack for the DS923+ (`linux/amd64`). It serves the PWA, API, and MCP on one web port. PostgreSQL, Valkey, OCR worker, scheduler, and MCP have no published port. Put Synology's HTTPS reverse proxy in front of the web port, then install the PWA from that HTTPS origin.

The images are built and published to GHCR by `.github/workflows/verify-and-publish.yml` after a `v*` release tag passes the automated jobs. No release images are published by the draft PR. The workflow summary prints image digest references. Set `RIPIANO_API_IMAGE` and `RIPIANO_WEB_IMAGE` in Portainer to those full `ghcr.io/...@sha256:...` values. A digest pins exactly what the NAS runs. If the packages are private, give Portainer read access to GHCR; public packages can be pulled anonymously.

Required Portainer environment variables:

| Variable | Example | Purpose |
| --- | --- | --- |
| `RIPIANO_API_IMAGE` | `ghcr.io/p4xx07/ripiano-api@sha256:...` | API, OCR worker, scheduler, MCP image |
| `RIPIANO_WEB_IMAGE` | `ghcr.io/p4xx07/ripiano-web@sha256:...` | PWA and reverse proxy image |
| `RIPIANO_SECRET_KEY` | long random value | Django signing key |
| `RIPIANO_SETUP_KEY` | long random value | First-owner setup key |
| `RIPIANO_DB_PASSWORD` | long random value | PostgreSQL password |
| `RIPIANO_PUBLIC_ORIGIN` | `https://ripiano.example.com` | Exact browser/MCP origin and sticker QR links |
| `RIPIANO_ALLOWED_HOSTS` | `ripiano.example.com` | Hostname accepted by API and MCP |
| `RIPIANO_MEDIA_PATH` | `/volume1/docker/ripiano/media` | Immutable originals and derived PDFs |
| `RIPIANO_DB_PATH` | `/volume1/docker/ripiano/postgres` | PostgreSQL state |
| `RIPIANO_BACKUP_PATH` | `/volume1/ripiano-backups` | Snapshot output for Hyper Backup |

Set `RIPIANO_DEBUG=0`. `RIPIANO_PORT` defaults to 8080 and is the **host** port connected to Synology's reverse proxy. Create the three NAS folders before deployment. The API/worker run as UID 10001 and must be able to write media and backup; the PostgreSQL image must be able to write its own database folder. Test those permissions on the NAS before adding personal documents.

`RIPIANO_BACKUP_HOUR`, `RIPIANO_BACKUP_MINUTE`, and `RIPIANO_BACKUP_RETENTION` are optional. The schedule is in Europe/Rome. Point Synology Hyper Backup at `<RIPIANO_BACKUP_PATH>/complete`. The Backblaze B2 configuration stays entirely in Synology; Ripiano has no B2 credentials. See [backup and restore](../docs/BACKUP_RESTORE.md) before an upgrade.

The optional Telegram service uses the `telegram` profile and three additional environment variables described in the [root README](../README.md). It must be enabled deliberately because Telegram handles forwarded files before Ripiano receives them.

The optional `watch` profile adds a read-only bind mount from `RIPIANO_WATCH_PATH` to `/watch`. Set `RIPIANO_WATCH_OWNER_USERNAME` to the account that owns imported files. The watcher waits for a stable file, keeps the source file in place, and uses a path/content key to avoid duplicate imports after restarts. Create and grant read access to the NAS folder before enabling the profile.
