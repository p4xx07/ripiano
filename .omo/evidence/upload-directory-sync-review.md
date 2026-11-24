# Mounted media directory sync review — 2026-11-23

Scope: original upload storage after a Docker Desktop bind mount returned `EBADF` at the post-rename directory `fsync`, causing a 500 for a valid PNG. The original file bytes had already been flushed and synced.

## Review

- The implementation retries the directory sync with a newly opened descriptor. If the filesystem still reports `EBADF`, `EINVAL`, or `ENOTSUP`, it logs that rename crash durability is best effort and returns the saved file for ingestion. No original bytes are altered or skipped.
- An `EIO` or other real storage failure still propagates; the fallback does not mask media faults. On NAS filesystems that support directory sync the existing durability behavior remains.
- The first browser upload failure was intermittent; a direct isolated-container write and a full browser rerun succeeded. The regression tests force both permanent unsupported-directory and one-time transient cases. No new runtime dependency or process is introduced.

## Evidence

- New unsupported-directory test failed before the fix with `OSError: [Errno 9] directory sync unsupported` at `storage.py:121`.
- Focused storage, format, and API contract tests after the final change: **33 passed**.
- Full API suite after the production fix: **462 passed, 17 skipped** in 83.42s. The final added test only covers the transient retry; focused suite passed afterward.
- `git diff --check`: exit 0.

Residual limit: on a filesystem that refuses directory sync, a sudden host power loss immediately after an upload can lose the rename even though the file bytes were synced. The server warns about this; a real disk I/O failure still stops the upload.
