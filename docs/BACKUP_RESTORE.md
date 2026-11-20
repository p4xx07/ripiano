# Backup and restore

Ripiano writes daily snapshots to a mounted backup volume. The default schedule is 02:00 Europe/Rome and can be changed with `RIPIANO_BACKUP_HOUR` and `RIPIANO_BACKUP_MINUTE`. `RIPIANO_BACKUP_RETENTION` keeps at least one completed snapshot. The owner can also run **Back up now** in the PWA.

## NAS volume

Set `RIPIANO_BACKUP_PATH` to a persistent NAS folder in the stack's environment, for example `/volume1/ripiano-backups`. Give container UID 10001 write access to it. The maintenance worker publishes snapshots only after validating the PostgreSQL dump and every copied media checksum:

```text
/volume1/ripiano-backups/
  staging/              temporary work; never use for recovery
  browse/               disposable human-readable copies; not a restore source
  complete/             validated snapshots for Synology Hyper Backup
    <timestamp-id>/
      database.dump
      manifest.json
      media/originals/…
      media/archive/…
```

A backup may run at any time, also while documents are being processed or right after a worker was killed. Document processing keeps its temporary files in a `.work` folder on the media volume; a snapshot never reads that folder (nor unfinished uploads, page previews, and share ZIPs, which are rebuilt). Any other unknown file in the media volume still fails the backup, on purpose. A document that was being processed when the snapshot started is saved as it was at that moment: its original, marked as waiting for processing. After a restore Ripiano queues it again and finishes it within a minute or two of the workers starting; nothing has to be uploaded again. Temporary files of a killed worker are removed when a worker starts and as soon as Ripiano notices the stopped run (a few minutes while the maintenance worker is free; after a running backup otherwise), not hours later.

Because the database is dumped first and the files are copied after it, a snapshot can contain a file its own dump does not mention yet: the finished PDF of a document that completed during the copy, or the parts of a barcode-split scan that was split during the copy. The restore removes such files after loading the database (the document is processed, and the scan split, again), so they do not pile up in the media volume. A file that disappears from the media folder while it is being copied fails the backup if any document uses it.

Configure Synology Hyper Backup to protect the `complete` folder. Its Backblaze B2 destination and credentials remain under your control. Each snapshot has a consistent PostgreSQL dump and immutable original files; unchanged media are hard-linked between local snapshots when the backup filesystem supports it. Snapshot files must not be edited in place.

The `.env` file and any secrets set in your stack manager are deliberately outside the snapshot. Keep a separate secure record of those values and replace credentials after recovery as needed. Backups made by this release require the same database migration set when restored; use a matching Ripiano image.

## Restore into an empty stack

1. Make the completed snapshot folder available as `RIPIANO_BACKUP_PATH` on the target NAS. Get the images of the Ripiano release that made the backup first (`docker compose pull`, or `docker compose build` for a source checkout): `up -d` reuses whatever images are already on the machine, and the restore refuses a different migration set. Then start only `db`, `broker`, and `api` once so migrations create an empty database.
2. Stop `api`. The target database must have no users or documents, and the media volume must contain no files (leftover temporary files in `.work` do not count).
3. From the Compose project directory, run:

   ```sh
   docker compose stop web worker maintenance_worker scheduler mcp api
   docker compose run --rm --no-deps api .venv/bin/python manage.py restore_snapshot <snapshot-name> --yes
   docker compose up -d
   ```

4. Sign in with the restored owner account. Search for a known document, open its original, and check the Backups screen. Documents that were still being processed when the backup was made show as processing for a short while and then become ready.

The restore command verifies all checksums and the migration set before writing. It refuses a populated target. Keep the original snapshot until the restored stack has passed those checks. A clean-stack PostgreSQL/media restore is part of the release verification, not just a manifest test.

Originals and archive outputs are immutable until an owner confirms permanent deletion from Trash or explicitly enables automatic Trash cleanup. Automatic cleanup is off by default; the owner chooses 30–3650 days in Trash, previews the number currently eligible, and confirms before the daily 03:00 Europe/Rome task may act. The maintenance worker holds the same backup lock while removing live files, so a snapshot in progress finishes before cleanup starts. A pending cleanup is retried by the scheduler after a busy backup; a failed cleanup appears in Trash with a Retry action. Completed snapshots keep their existing copies until snapshot retention removes them. Ripiano cannot erase copies already transferred by Synology Hyper Backup to Backblaze B2; configure that retention separately in Synology.

Trash retention settings live in the database and return with a restored snapshot. If you restore an older archive, inspect the setting before starting the scheduler: documents that have already exceeded the chosen age can be queued at its next daily run. Snapshot retention and Synology Hyper Backup retention are separate from this Trash setting.

## Health checks

| Endpoint | Where | Answers |
| --- | --- | --- |
| `GET /healthz` | api, port 8000 inside the stack | 200 `{"status":"ok","database":"ok","broker":"ok"}`; 503 with `"status":"unavailable"` and `"down"` for the database or the queue server (Valkey) when either cannot answer. One `SELECT 1` and one `PING` (1 s timeout); the answer is reused for 5 seconds. |
| `GET /healthz` | through the web container at `https://<your-origin>/healthz`, no sign-in | The same status codes, but only `{"status":"ok"}` or `{"status":"unavailable"}`: it does not say which part is down. |
| `GET /livez` | api, and through the web container at `https://<your-origin>/livez` | 200 while the web process answers; checks nothing else. Use it for a "restart if dead" monitor. The app uses it to tell "Ripiano can't be reached" from "busy". |
| `GET /healthz` | mcp, port 8001 inside the stack only | 200 `{"status":"ok","database":"ok"}` or 503. One query on its own connection with a 2.5 s limit, so a slow agent call cannot make the check fail. |

The `api` container's healthcheck uses `/healthz`, so Docker shows `api` as unhealthy while the database or the queue server is down (after 15 failed checks, about 2.5 minutes, so short blips do not flip it). Compose never restarts a container because it is unhealthy; `restart: unless-stopped` only restarts one that exits, so a broker outage cannot cause a restart loop. If you add a tool that restarts unhealthy containers, point it at `/livez` instead. The `mcp` container has its own healthcheck. The `worker` and `maintenance_worker` containers are healthy while their heartbeat (every 30 s, also during a long scan) keeps touching `/tmp/ripiano-worker-alive`; the check is a shell `find`, with no Python start-up. The same heartbeat is stored in the database, so Background jobs and the Overview report documents that wait because no OCR worker is running. As before, the `api`, worker, `mcp`, and `web` containers are only started once the database and the queue server are healthy, so an update while Valkey cannot start leaves the interface down until Valkey is fixed. After the database restarts (an update, or PostgreSQL killed for memory), agents work again with their next request: the MCP server, like the api, replaces a broken database connection before each request, so no container needs restarting.

## NAS browse copies

The on-demand **Build browse copy** action writes ordinary files under `<RIPIANO_BACKUP_PATH>/browse/owners/<owner-id>/complete/<run-id>`. These copies are separate from checksum-verified restore snapshots under `<RIPIANO_BACKUP_PATH>/complete`. Keep Synology Hyper Backup pointed at the snapshot `complete` folder. Browse copies can be rebuilt from the managed archive and are not a restore source. Give the browse folder the same NAS access controls as the archive because it contains originals, OCR text, and metadata.
