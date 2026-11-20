# Clean-stack restore drill — round 9 candidate

Candidate: 1a365f35c12509f79da9cd9c459b426dca1f4ec4 (`1a365f3`), the commit the round-9 judges review. It adds migration `archive:0061_processing_warning_skipped_runs_sticker_created` (processing warnings). Local Docker Desktop on macOS; two separate Compose projects with their own empty named volumes (`ripiano-drill-src` on port 18091, `ripiano-drill-dst` on port 18092), each built from this commit, and a fresh shared bind-mounted backup folder (`drill/backup9`, used by no earlier round). Script: the same drill client as round 8 (`qa-artifacts/20261118-restore-drill/drill_client.py`, commands `setup` and `verify`), plus a small Django-shell check (`check9.py`) for the migration and document sets. Passwords and the setup key were read from the env files or generated at run time and are not recorded here.

## Procedure and results

1. **Fresh install (source):** `docker compose -p ripiano-drill-src --env-file src.env up -d --build` on empty volumes; owner created through `POST /api/setup` with the setup key.
2. **Upload / OCR / search:** `three-pages.pdf`, `judge.png`, `office-letter.docx`, `email-notice.eml` uploaded through the API → `statuses ['ready', 'ready', 'ready', 'ready']`. One document retitled "Drill lease" and tagged "Drill tag".
3. **Physical archive:** location "Drill shelf" with nested "Drill box"; a paper copy of "Drill lease" placed in the box (sticker `R-4JB7ACN5`).
4. **Agent grants:** two MCP grants created (each confirmed with the owner's password); one revoked. Before the backup: `before backup: mcp active 200 revoked 401`.
5. **Backup:** `POST /api/backups` → `backup complete 20261119T142011471143Z-cfc7e57c`. Source database held 4 documents. Manifest: format 1, 79 migrations (last archive migration `0061_processing_warning_skipped_runs_sticker_created`), 8 files (4 originals, 4 archive PDFs).
   - `database.dump` SHA-256 `e1aa9b65f78764e8c91385ef5c8d3b204fefa20e35e7b3d9e6b4d8abe6f5534d` (239 892 bytes; matches the manifest)
   - `manifest.json` SHA-256 `de4f3da31d8f43d08ae317beb1c9d5c02a0bd8eece64cdd4ec5f78dd6f1255c4`
   - Source stack then removed (`down -v`) before the target was started.
6. **Restore into an empty stack (target)** as in docs/BACKUP_RESTORE.md:
   - `docker compose -p ripiano-drill-dst --env-file dst.env build` (target images from the same commit first)
   - `up -d db broker api` → `showmigrations archive` shows `[X] 0060_…` and `[X] 0061_processing_warning_skipped_runs_sticker_created` on the empty database
   - `stop web worker maintenance_worker scheduler mcp api`
   - `run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261119T142011471143Z-cfc7e57c --yes` → `Snapshot restored. Restart the application services.`
   - `up -d`
7. **Verification on the restored stack** (sign-in with the restored owner), `client.py http://localhost:18092 verify`:

   ```
   documents 4 ['Avviso TARI 2026 lampone', 'Drill lease', 'judge', 'office-letter']
   e264da8a 200 checksum ok
   cb64f1b1 200 checksum ok
   c24c87fe 200 checksum ok
   e9457a20 200 checksum ok
   first: Drill lease ['Drill tag']
   search tag:Drill -> ['Drill lease']
   sticker R-4JB7ACN5 200 location kept ['Drill shelf', 'Drill box']
   grants revoked state kept | mcp active 200 revoked 401
   RESTORE VERIFIED
   ```

8. **Migration and document set (new for 0061)**, `manage.py shell < check9.py` on the restored `api`, reading the snapshot manifest from `/backup`:

   ```
   migrations manifest 79 db 79 match
   has 0061 True
   documents db 4 manifest archive copies 4 match
   ids ['c24c87fe', 'cb64f1b1', 'e264da8a', 'e9457a20']
   warning fields ['processing_warning', 'processing_warning_reviewed_at']
   manifest original sha256 set ['4d64026e2eea8209', '731c8397f9084a2a', '921d4537b141dddd', 'f7817718ea99894c']
   processing_warning set 0
   ```

   Fixture SHA-256 (`apps/web/e2e/fixtures`), identical to the manifest originals and to the downloads in step 7:

   | Fixture | SHA-256 |
   |---|---|
   | three-pages.pdf | `731c8397f9084a2a6fe0b84b1f1fa882d932c81b1b148ae7bb69a33f94c8bad0` |
   | judge.png | `4d64026e2eea82094e40bf7d9c5e674eac4d5caee487e3470eb3234b37c0b61c` |
   | office-letter.docx | `f7817718ea99894c285cdd739e43d7b1aac3a67e0d57733959229893c4fc44dc` |
   | email-notice.eml | `921d4537b141dddd4c0f20c246deada56317b3ca97db9da9345270fbebe95a95` |

## Summary

| Check | Result |
|---|---|
| Fresh install and owner setup | PASS |
| Four uploads reach `ready` | PASS |
| Backup completes (`20261119T142011471143Z-cfc7e57c`) | PASS |
| Target migrates empty database through 0061 | PASS |
| `restore_snapshot --yes` | PASS |
| 4 documents, originals byte-identical (SHA-256) | PASS |
| Title, tag and `tag:Drill` search | PASS |
| Sticker → `Drill shelf / Drill box` | PASS |
| Revoked grant stays revoked (MCP 401), active grant works (200) | PASS |
| Restored migration set = manifest (79, includes 0061) | PASS |
| Restored document IDs = manifest archive set | PASS |

Result: **RESTORE VERIFIED**.

Not covered: Synology ACLs, Hyper Backup, and a restore on the DS923+ (out of scope by owner decision D7); no document in this drill carried a processing warning, so the check covers the 0061 schema, not a populated warning value. Both drill stacks and their volumes were removed afterwards; the backup folder was kept.
