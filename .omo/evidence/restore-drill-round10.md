# Clean-stack restore drill — round 10 candidate

Candidate: 5bc8c7de72619aac6ebea44b3cad7c69a610b31a (`5bc8c7d`), clean working tree. New since round 9: migrations `archive:0062_processing_heartbeat_agent_revoked_reason` and `archive:0063_processing_claim_interruptions` (processing claims/heartbeat), an `mcp` container healthcheck, and the `/healthz` and `/livez` endpoints. Local Docker Desktop on macOS; two separate Compose projects with their own empty named volumes (`ripiano-drill-src` on port 18091, `ripiano-drill-dst` on port 18092), each built from this commit, and a fresh shared bind-mounted backup folder (`drill/backup10`, used by no earlier round). Script: the same drill client as rounds 8 and 9 (`client.py`, commands `setup` and `verify`), plus the Django-shell check `check10.py` (`check9.py` with this round's snapshot name and the 0062/0063 lines added) for the migration and document sets. Passwords and the setup key were read from the env files or generated at run time and are not recorded here.

## Procedure and results

1. **Fresh install (source):** `docker compose -p ripiano-drill-src --env-file src.env up -d --build` on empty volumes; `api`, `db`, `broker`, `converter` and `mcp` reported `(healthy)`. Owner created through `POST /api/setup` with the setup key.
2. **Upload / OCR / search:** `three-pages.pdf`, `judge.png`, `office-letter.docx`, `email-notice.eml` uploaded through the API → `statuses ['ready', 'ready', 'ready', 'ready']`. One document retitled "Drill lease" and tagged "Drill tag".
3. **Physical archive:** location "Drill shelf" with nested "Drill box"; a paper copy of "Drill lease" placed in the box (sticker `R-4XW92YTM`).
4. **Agent grants:** two MCP grants created (each confirmed with the owner's password); one revoked. Before the backup: `before backup: mcp active 200 revoked 401`.
5. **Backup:** `POST /api/backups` → `backup complete 20261119T220106551721Z-244358be`. Source database held 4 documents. Manifest: format 1, 81 migrations (last archive migrations `0062_processing_heartbeat_agent_revoked_reason`, `0063_processing_claim_interruptions`), 8 files (4 originals, 4 archive PDFs).
   - `database.dump` SHA-256 `ccd22cb6d623b1d7cac9dac2adfcb00dda00452320fd53b1b3c35b1975837ca4` (241 897 bytes; matches the manifest)
   - `manifest.json` SHA-256 `e982363c5fcca1ad17513806c1ef23adcff008e26f84a5e2a3b35cf7ebadf83d`
   - Source stack then removed (`down -v`) before the target was built and started.
6. **Restore into an empty stack (target)** as in docs/BACKUP_RESTORE.md:
   - `docker compose -p ripiano-drill-dst --env-file dst.env build` (target images from the same commit first)
   - `up -d db broker api` → once `api` was healthy, `showmigrations archive` shows `[X] 0061_…`, `[X] 0062_processing_heartbeat_agent_revoked_reason` and `[X] 0063_processing_claim_interruptions`; all 81 migrations applied, none pending; 0 users and 0 documents in the database
   - `stop web worker maintenance_worker scheduler mcp api`
   - `run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261119T220106551721Z-244358be --yes` → `Snapshot restored. Restart the application services.` (exit 0)
   - `up -d`
7. **Verification on the restored stack** (sign-in with the restored owner), `client.py http://localhost:18092 verify`:

   ```
   documents 4 ['Avviso TARI 2026 lampone', 'Drill lease', 'judge', 'office-letter']
   6706f906 200 checksum ok
   c6b1ce5f 200 checksum ok
   ca5f091f 200 checksum ok
   749397ce 200 checksum ok
   first: Drill lease ['Drill tag']
   search tag:Drill -> ['Drill lease']
   sticker R-4XW92YTM 200 location kept ['Drill shelf', 'Drill box']
   grants revoked state kept | mcp active 200 revoked 401
   RESTORE VERIFIED
   ```

8. **Migration and document set (new for 0062 and 0063)**, `manage.py shell < check10.py` on the restored `api`, reading the snapshot manifest from `/backup`:

   ```
   migrations manifest 81 db 81 match
   has 0061 True
   has 0062 True
   has 0063 True
   documents db 4 manifest archive copies 4 match
   ids ['6706f906', '749397ce', 'c6b1ce5f', 'ca5f091f']
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

9. **Health after the restore (new this round)**, on the restored stack after `up -d`:

   `docker compose -p ripiano-drill-dst ps -a` (service, state, health) — all nine containers running; every container that defines a healthcheck reports `healthy`:

   ```
   api                 running  healthy
   broker              running  healthy
   converter           running  healthy
   db                  running  healthy
   mcp                 running  healthy
   maintenance_worker  running  (no healthcheck defined)
   scheduler           running  (no healthcheck defined)
   web                 running  (no healthcheck defined)
   worker              running  (no healthcheck defined)
   ```

   Endpoints, requested from inside the containers (`exec -T api` / `exec -T mcp`, Python `urllib`):

   ```
   http://localhost:8000/healthz 200 {"status": "ok", "database": "ok", "broker": "ok"}
   http://localhost:8000/livez 200 {"status": "ok"}
   http://localhost:8001/healthz 200 {"status": "ok", "database": "ok"}
   ```

## Summary

| Check | Result |
|---|---|
| Fresh install and owner setup | PASS |
| Four uploads reach `ready` | PASS |
| Backup completes (`20261119T220106551721Z-244358be`) | PASS |
| Target migrates empty database through 0063 | PASS |
| `restore_snapshot --yes` | PASS |
| 4 documents, originals byte-identical (SHA-256) | PASS |
| Title, tag and `tag:Drill` search | PASS |
| Sticker → `Drill shelf / Drill box` | PASS |
| Revoked grant stays revoked (MCP 401), active grant works (200) | PASS |
| Restored migration set = manifest (81, includes 0062 and 0063) | PASS |
| Restored document IDs = manifest archive set | PASS |
| After restore: all containers running, all healthchecks `healthy` (api, mcp, db, broker, converter) | PASS |
| After restore: api `/healthz` 200 (database ok, broker ok), `/livez` 200, mcp `/healthz` 200 | PASS |

Result: **RESTORE VERIFIED**.

Not covered: Synology ACLs, Hyper Backup, and a restore on the DS923+ (out of scope by owner decision D7); no document in this drill carried a processing warning or an interrupted processing claim, so the check covers the 0061–0063 schema, not populated values; `/healthz` and `/livez` were requested inside the `api` and `mcp` containers, not through the published web port (the web path was exercised only by the drill client's API and `/mcp` calls on port 18092); the 503 answer of `/healthz` with the database or Valkey down was not exercised. Both drill stacks and their volumes were removed afterwards; the backup folder (`drill/backup10`) was kept.
