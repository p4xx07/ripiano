# Built-in consume folder — independent review (2026-11-17)

Scope: commit `cb001b8`; auto-created built-in source, folder backend, Compose mount, source API restrictions, and tests.

Evidence: full API baseline: `242 passed, 9 skipped`; inspected `ensure_consume_source`, `FolderBackend`, and `test_folder_source.py`. It waits for an active owner and a mounted directory, ignores symlinks and hidden files, waits 60 seconds for stable files, imports through the shared durable path, and blocks deletion or kind changes of the built-in source.

No high/medium finding in the inspected path. Synology ACLs, scanner write behavior, and a clean-stack NAS restore still need owner-side validation.

Final full API verification after the review fixes: `243 passed, 9 skipped` (`RIPIANO_DEBUG=1 .venv/bin/pytest -q`).
