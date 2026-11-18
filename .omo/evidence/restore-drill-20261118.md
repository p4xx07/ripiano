# Clean-stack restore drill — 18 November 2026

Candidate: f2b94168ff7af0bb914bb3f644eef7ee7490394a (code identical to the round-2 judging build). Local Docker Desktop on macOS; two separate Compose projects with their own empty named volumes (`ripiano-drill-src`, `ripiano-drill-dst`) and a shared bind-mounted backup folder. Script: `qa-artifacts/20261118-restore-drill/drill_client.py`.

1. **Fresh install (source):** `docker compose -p ripiano-drill-src --env-file src.env up -d --build` on empty volumes; owner created through `POST /api/setup` with the setup key.
2. **Upload/OCR/search:** fixtures `three-pages.pdf`, `judge.png`, `office-letter.docx`, `email-notice.eml` uploaded through the API; all four reached `ready` (OCR worker + Office converter). One document retitled "Drill lease" and tagged "Drill tag".
3. **Backup:** `POST /api/backups` → snapshot `20261118T093248316575Z-96133cd6` completed and published under `complete/`.
4. **Restore into an empty stack (target),** exactly as in docs/BACKUP_RESTORE.md: `up -d db broker api` (migrations on an empty database), `stop api`, `run --rm --no-deps api manage.py restore_snapshot <name> --yes` → "Snapshot restored", `up -d`.
5. **Verification on the restored stack:** sign-in with the restored owner; 4 documents listed; every original downloaded with a SHA-256 identical to the uploaded fixture; title and tag preserved; `tag:Drill` search returns the one document. Result: **RESTORE VERIFIED**.

Not covered by this drill: Synology ACLs and Hyper Backup, a restore on the DS923+, revoked-grant and permission checks after restore (covered by unit tests in `test_portable.py`/`test_backup.py`, not by this live drill). Drill stacks and volumes were removed afterwards.
