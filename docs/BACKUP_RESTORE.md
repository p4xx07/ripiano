# Backup and restore

Ripiano writes daily snapshots to a mounted backup volume. The default schedule is 02:00 Europe/Rome and can be changed with `RIPIANO_BACKUP_HOUR` and `RIPIANO_BACKUP_MINUTE`. `RIPIANO_BACKUP_RETENTION` keeps at least one completed snapshot. The owner can also run **Back up now** in the PWA.

## NAS volume

Set `RIPIANO_BACKUP_PATH` to a persistent Synology folder in Portainer, for example `/volume1/ripiano-backups`. Give container UID 10001 write access to it. The maintenance worker publishes snapshots only after validating the PostgreSQL dump and every copied media checksum:

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

Configure Synology Hyper Backup to protect the `complete` folder. Its Backblaze B2 destination and credentials remain under your control. Each snapshot has a consistent PostgreSQL dump and immutable original files; unchanged media are hard-linked between local snapshots when the backup filesystem supports it. Snapshot files must not be edited in place.

The `.env` or Portainer secrets are deliberately outside the snapshot. Keep a separate secure record of those values and replace credentials after recovery as needed. Backups made by this release require the same database migration set when restored; use a matching Ripiano image.

## Restore into an empty stack

1. Make the completed snapshot folder available as `RIPIANO_BACKUP_PATH` on the target NAS. Start only `db`, `broker`, and `api` once so migrations create an empty database.
2. Stop `api`. The target database must have no users or documents, and the media volume must contain no files.
3. From the Compose project directory, run:

   ```sh
   docker compose stop web worker maintenance_worker scheduler mcp api
   docker compose run --rm --no-deps api .venv/bin/python manage.py restore_snapshot <snapshot-name> --yes
   docker compose up -d
   ```

4. Sign in with the restored owner account. Search for a known document, open its original, and check the Backups screen.

The restore command verifies all checksums and the migration set before writing. It refuses a populated target. Keep the original snapshot until the restored stack has passed those checks. A clean-stack PostgreSQL/media restore is part of the release verification, not just a manifest test.

Originals and archive outputs are immutable until an owner confirms permanent deletion from Trash or explicitly enables automatic Trash cleanup. Automatic cleanup is off by default; the owner chooses 30–3650 days in Trash, previews the number currently eligible, and confirms before the daily 03:00 Europe/Rome task may act. The maintenance worker holds the same backup lock while removing live files, so a snapshot in progress finishes before cleanup starts. A pending cleanup is retried by the scheduler after a busy backup; a failed cleanup appears in Trash with a Retry action. Completed snapshots keep their existing copies until snapshot retention removes them. Ripiano cannot erase copies already transferred by Synology Hyper Backup to Backblaze B2; configure that retention separately in Synology.

Trash retention settings live in the database and return with a restored snapshot. If you restore an older archive, inspect the setting before starting the scheduler: documents that have already exceeded the chosen age can be queued at its next daily run. Snapshot retention and Synology Hyper Backup retention are separate from this Trash setting.

## NAS browse copies

The on-demand **Build browse copy** action writes ordinary files under `<RIPIANO_BACKUP_PATH>/browse/owners/<owner-id>/complete/<run-id>`. These copies are separate from checksum-verified restore snapshots under `<RIPIANO_BACKUP_PATH>/complete`. Keep Synology Hyper Backup pointed at the snapshot `complete` folder. Browse copies can be rebuilt from the managed archive and are not a restore source. Give the browse folder the same NAS access controls as the archive because it contains originals, OCR text, and metadata.
