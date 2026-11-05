# Backup and restore

Ripiano writes daily snapshots to a mounted backup volume. The default schedule is 02:00 Europe/Rome and can be changed with `RIPIANO_BACKUP_HOUR` and `RIPIANO_BACKUP_MINUTE`. `RIPIANO_BACKUP_RETENTION` keeps at least one completed snapshot. The owner can also run **Back up now** in the PWA.

## NAS volume

Set `RIPIANO_BACKUP_PATH` to a persistent Synology folder in Portainer, for example `/volume1/ripiano-backups`. Give container UID 10001 write access to it. The worker publishes snapshots only after validating the PostgreSQL dump and every copied media checksum:

```text
/volume1/ripiano-backups/
  staging/              temporary work; never use for recovery
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
   docker compose stop web worker scheduler mcp api
   docker compose run --rm --no-deps api .venv/bin/python manage.py restore_snapshot <snapshot-name> --yes
   docker compose up -d
   ```

4. Sign in with the restored owner account. Search for a known document, open its original, and check the Backups screen.

The restore command verifies all checksums and the migration set before writing. It refuses a populated target. Keep the original snapshot until the restored stack has passed those checks. A clean-stack PostgreSQL/media restore is part of the release verification, not just a manifest test.

The current backup contract assumes originals and archive outputs are immutable and that media garbage collection is disabled. When delete/reprocess workflows are added, they must coordinate with active snapshots before files can be removed.
