# NAS deployment with pre-built images

`compose.portainer.yaml` is the pull-only stack for the DS923+ (`linux/amd64`). It serves the PWA, API, and MCP on one web port. PostgreSQL, Valkey, OCR worker, private LibreOffice converter, maintenance worker, scheduler, and MCP have no published port. The OCR worker handles new documents and retries; the maintenance worker handles rule rechecks and backups, so a long archive scan does not hold new uploads. Put Synology's HTTPS reverse proxy in front of the web port, then install the PWA from that HTTPS origin. To reach Ripiano and other services from outside through one sign-in, use the [Raspberry Pi gateway](gateway/README.md) (Traefik + Authelia) instead.

The images are built and published to GHCR by `.github/workflows/verify-and-publish.yml` after a `v*` release tag passes the automated jobs. No release images are published by the draft PR. The workflow summary prints image digest references. Set `RIPIANO_API_IMAGE` and `RIPIANO_WEB_IMAGE` in the stack's environment to those full `ghcr.io/...@sha256:...` values. A digest pins exactly what the NAS runs. If the packages are private, log the NAS in to GHCR (`docker login ghcr.io`) or give your Compose tool read access; public packages can be pulled anonymously.

Required environment variables:

The checked-in [environment example](portainer.env.example) collects the values in one place. Set its variables wherever your Compose tool reads them (for example an `.env` file next to the Compose file) with your own secrets, paths, and published image digests; the file's image tags are placeholders and cannot deploy the current draft PR.

| Variable | Example | Purpose |
| --- | --- | --- |
| `RIPIANO_API_IMAGE` | `ghcr.io/p4xx07/ripiano-api@sha256:...` | API, OCR worker, maintenance worker, scheduler, MCP image |
| `RIPIANO_WEB_IMAGE` | `ghcr.io/p4xx07/ripiano-web@sha256:...` | PWA and reverse proxy image |
| `RIPIANO_SECRET_KEY` | long random value | Django signing key |
| `RIPIANO_SETUP_KEY` | long random value | First-owner setup key |
| `RIPIANO_DB_PASSWORD` | long random value | PostgreSQL password |
| `RIPIANO_PUBLIC_ORIGIN` | `https://ripiano.example.com` | Exact browser/MCP origin and sticker QR links |
| `RIPIANO_ALLOWED_HOSTS` | `ripiano.example.com` | Hostname accepted by API and MCP |
| `RIPIANO_MEDIA_PATH` | `/volume1/docker/ripiano/media` | Immutable originals and derived PDFs |
| `RIPIANO_DB_PATH` | `/volume1/docker/ripiano/postgres` | PostgreSQL state |
| `RIPIANO_BACKUP_PATH` | `/volume1/ripiano-backups` | Snapshot output for Hyper Backup |

Set `RIPIANO_DEBUG=0`. `RIPIANO_PORT` defaults to 8080 and is the **host** port connected to Synology's reverse proxy. Create the three NAS folders before deployment. The API and workers run as UID 10001: the OCR worker needs media write access, and the maintenance worker needs media and backup write access for snapshots and permanent deletion. The PostgreSQL image must be able to write its own database folder. Test those permissions on the NAS before adding personal documents.

`RIPIANO_BACKUP_HOUR`, `RIPIANO_BACKUP_MINUTE`, and `RIPIANO_BACKUP_RETENTION` are optional. The schedule is in Europe/Rome. Point Synology Hyper Backup at `<RIPIANO_BACKUP_PATH>/complete`. The Backblaze B2 configuration stays entirely in Synology; Ripiano has no B2 credentials. See [backup and restore](../docs/BACKUP_RESTORE.md) before an upgrade.

The converter is the pinned Gotenberg LibreOffice image on a private Compose network. The OCR worker sends `.docx`, `.xlsx`, and `.pptx` files to it; no public port or cloud API is involved. Leave the `converter` service and worker network/URL settings in place when customizing the stack. The API accepts up to 25 MiB by default, and Gotenberg's 27 MB request-body cap leaves room for the multipart envelope. The converter may need extra NAS memory for large Office files; test representative files before relying on it for personal archives.

The **Build browse copy** action in Backups creates an owner-scoped, on-demand folder at `<RIPIANO_BACKUP_PATH>/browse/owners/<owner-id>/complete/<run-id>`. It contains year folders, tag folders, readable titles, original files, available searchable PDFs, OCR text, metadata JSON, and a checksum manifest. Tag paths use hard links to the files in the year view when supported, so they usually do not multiply storage inside the same volume. This is a disposable navigation copy, not a restorable backup or a writable source of truth; edit documents in Ripiano and rebuild the copy afterward. Ripiano keeps the newest two completed browse copies by default. `RIPIANO_BROWSE_RETENTION` changes that count. A rebuild temporarily needs enough free space for the old and new copies. The separate `<RIPIANO_BACKUP_PATH>/complete` folder remains the destination for Hyper Backup.

Telegram and S3 inputs are set up in the app under **Sources** (see [Sources in the user guide](../docs/USER_GUIDE.md#sources-external-storage)); they need no Compose profile or environment variable. A Telegram source must be added deliberately, because Telegram handles forwarded files before Ripiano receives them.

`RIPIANO_CONSUME_PATH` mounts the consume folder at `/consume` (read-only in the API, read-write in the maintenance worker): files dropped there are imported for the archive owner and removed, with no setup in the app. `RIPIANO_SOURCES_PATH` mounts one NAS folder at `/sources` (read-only in the API for Preview, read-write in the maintenance worker). The archive owner then adds **Folder on the NAS** sources in the app for its subfolders. Create the folder and give UID 10001 read access (and write access if sources move or delete imported files) before deploying. The former `watch` profile and `RIPIANO_WATCH_*` variables are gone.
