# Clean-stack restore drill — round 4 candidate

Candidate: b57e14e6c529d7fdeb5b9b7ff6b023d28fe88a7b (`b57e14e`), the commit the round-4 judges review. Local Docker Desktop on macOS; two separate Compose projects with their own empty named volumes (`ripiano-drill-src`, `ripiano-drill-dst`) built from this commit, and a shared bind-mounted backup folder. Script: `qa-artifacts/20261118-restore-drill/drill_client.py` (commands `setup` and `verify`).

1. **Fresh install (source):** empty volumes; owner created through `POST /api/setup` with the setup key.
2. **Upload / OCR / search:** `three-pages.pdf`, `judge.png`, `office-letter.docx`, `email-notice.eml` uploaded through the API; all four reached `ready`. One document retitled "Drill lease" and tagged "Drill tag".
3. **Physical archive:** location "Drill shelf" with nested "Drill box"; a paper copy of "Drill lease" placed in the box (sticker assigned).
4. **Agent grants:** two MCP grants created; one revoked. Before the backup the MCP endpoint answered 200 to the active token and 401 to the revoked one.
5. **Backup:** `POST /api/backups` → snapshot `20261118T165219546701Z-49971333`, complete.
6. **Restore into an empty stack (target)** exactly as in docs/BACKUP_RESTORE.md: `up -d db broker api` (migrations on an empty database), `stop api`, `run --rm --no-deps api manage.py restore_snapshot <name> --yes` → "Snapshot restored", `up -d`.
7. **Verification on the restored stack** (sign-in with the restored owner):
   - 4 documents; every original downloaded with a SHA-256 identical to the uploaded fixture;
   - title and tag preserved; `tag:Drill` search returns the one document;
   - the sticker lookup returns the copy in `Drill shelf / Drill box`;
   - the revoked grant is still revoked and its token is refused by MCP (401); the active grant still works (200).

   Result: **RESTORE VERIFIED**.

Not covered: Synology ACLs, Hyper Backup, and a restore on the DS923+ (out of scope by owner decision D7). Drill stacks and volumes were removed afterwards.
