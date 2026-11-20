# Clean-stack restore drill — round 12 candidate

Candidate: 71315f4531f0ef02d0205aa77bfdce0019c9c127 (`71315f4`), clean working tree. New since round 11: migration `archive:0065_worker_heartbeat_queued_at` (worker heartbeat, queue mark), and healthchecks on `worker` and `maintenance_worker`. As in round 11, the restored snapshot was taken **with the OCR worker killed in the middle of a split**.

Local Docker Desktop on macOS; two separate Compose projects with their own empty named volumes (`ripiano-drill-src` on port 18091, `ripiano-drill-dst` on port 18092), each built from this commit, and a fresh shared bind-mounted backup folder (`drill/backup12`, used by no earlier round). Scripts: the drill client of rounds 8–10 (`client.py`, commands `setup` and `verify`), a new `interrupt.py` (upload, kill the worker, back up), and `check12.py` (`check10.py` with this snapshot's name and the 0064 and 0065 lines). Passwords and the setup key were read from the env files or generated at run time and are not recorded here.

## Procedure and results

1. **Fresh install (source):** `docker compose -p ripiano-drill-src --env-file src12.env up -d --build` on empty volumes; api healthy. Owner created through `POST /api/setup` with the setup key.
2. **Upload / OCR / search:** `three-pages.pdf`, `judge.png`, `office-letter.docx`, `email-notice.eml` → `statuses ['ready', 'ready', 'ready', 'ready']`. One document retitled "Drill lease" and tagged "Drill tag".
3. **Physical archive:** location "Drill shelf" with nested "Drill box"; a paper copy of "Drill lease" placed in the box (sticker `R-EFRXR2YY`).
4. **Agent grants:** two MCP grants created (each confirmed with the owner's password); one revoked → `before backup: mcp active 200 revoked 401`.
5. **First backup:** `backup complete (first backup, not restored)`.
6. **Backup with the worker killed (new):** `asn-batch-mobile.pdf` uploaded; once it reported `processing`, one more second, then `docker compose -p ripiano-drill-src kill worker`; then `POST /api/backups`:

   ```
   status before kill: processing
   worker killed
   backup with worker killed: complete 20261120T101022109306Z-a58bfa65
   document status in snapshot: processing
   ```

   The killed run left its work folder behind (`/data/.work/68f10cfe-…`); the media root held only `.work`, `archive`, `originals`. The manifest lists **no** path outside `originals/` and `archive/` (`[]`), 11 files (7 originals: the four fixtures, `asn-batch-mobile.pdf` and the two part files written before the kill; 4 archive PDFs), and 83 migrations including `archive:0065_worker_heartbeat_queued_at`. This snapshot is the one restored below.
   - `database.dump` SHA-256 `91140dc421c3b3bdac0f0146be51cebff8778e51af2ab6c40b06d17f9f609d92`
   - `manifest.json` SHA-256 `e7352bdef477a4df7844cbe67a2ee855156fef632511dbdbfc392c6e127c083b`
   - Source stack then removed (`down -v`) before the target was built and started.
7. **Restore into an empty stack (target)** as in docs/BACKUP_RESTORE.md:
   - `docker compose -p ripiano-drill-dst --env-file dst12.env build`
   - `up -d db broker api` → api healthy; `showmigrations archive` ends with `[X] 0062 … [X] 0063 … [X] 0064 … [X] 0065_worker_heartbeat_queued_at`; `users 0 documents 0`
   - `stop web worker maintenance_worker scheduler mcp api`
   - `run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261120T101022109306Z-a58bfa65 --yes` → `Snapshot restored. Restart the application services.` (exit 0)
   - `up -d` → api healthy
8. **Verification on the restored stack**, `client.py http://localhost:18092 verify`:

   ```
   documents 6 ['Avviso TARI 2026 lampone', 'Drill lease', 'asn-batch-mobile (1/2)', 'asn-batch-mobile (2/2)', 'judge', 'office-letter']
   f5ac43fe 200 checksum ok
   4b76b9fe 200 checksum ok
   620ca0c5 200 checksum ok
   617062ee 200 checksum ok
   first: Drill lease ['Drill tag']
   search tag:Drill -> ['Drill lease']
   sticker R-EFRXR2YY 200 location kept ['Drill shelf', 'Drill box']
   grants revoked state kept | mcp active 200 revoked 401
   RESTORE VERIFIED
   ```

9. **The interrupted document after the restore (new):** it was `processing` in the snapshot. With the restored worker running, it finished by itself: `interrupted doc ready after 66s`. The library then shows the two split parts once each (`asn-batch-mobile (1/2)`, `(2/2)`), with no duplicate parts although the part files of the killed run were in the snapshot.
10. **Migration and document set**, `manage.py shell < check11.py` on the restored api:

    ```
    migrations manifest 83 db 83 match
    has 0061 True
    has 0062 True
    has 0063 True
    has 0064 True
    has 0065 True
    documents db 7 manifest archive copies 4 MISMATCH
    manifest original sha256 set ['4d64026e2eea8209', '731c8397f9084a2a', '78d8a1f3bbbcaccf', '921d4537b141dddd', 'd46e1068f71f5fa1', 'd4c8cafe95fd192b', 'f7817718ea99894c']
    processing_warning set 0
    ```

    The `MISMATCH` line is expected for this snapshot, not a restore defect: the check compares database documents with archive copies, and the interrupted document had no archive copy yet when the backup ran. By the time the check ran, the restored worker had split it, so the database held 7 rows (the 4 fixtures, the split source, which the library hides, and its 2 parts). `d46e1068f71f5fa1` is `asn-batch-mobile.pdf`; the other two new hashes are its part files.
11. **Health after the restore**, `docker compose -p ripiano-drill-dst ps -a`: api, broker, converter, db, mcp, maintenance_worker, worker `running healthy` (the two workers have a healthcheck from this round); scheduler and web running (no healthcheck defined). Endpoints:

    ```
    /healthz 200 {"status": "ok", "database": "ok", "broker": "ok"}   (inside api)
    /livez 200 {"status": "ok"}                                         (inside api)
    web /healthz 200 {"status": "ok"}                                   (through the published web port 18092)
    web /livez 200 {"status": "ok"}                                     (through the published web port 18092)
    ```

    Both stacks were removed with `down -v` afterwards.

## Result

PASS. Original bytes, title and tag, search, nested physical location, sticker lookup, agent grant states, and the migration set (83, including 0065) survived the restore. A backup taken with the worker killed mid-split completed, and the document caught in processing finished by itself after the restore without duplicate parts.

Not checked: a restore on the owner's Synology NAS (out of scope by owner decision D7); the exact content of the snapshot's database for the interrupted document (whether its parts were already rows before the kill) was not inspected.
