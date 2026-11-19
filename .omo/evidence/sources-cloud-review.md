# Sources and cloud drives — independent review (2026-11-17)

Scope: commits `9d7cd7c` through `b2b1009`; shared source engine, S3, WebDAV, Telegram, folder, Google Drive, OneDrive, Dropbox, source endpoints, and tests.

Evidence: full API baseline: `242 passed, 9 skipped`; inspected `storage_sources.py`, `cloud_sources.py`, source OAuth callback, and provider download paths. The callback binds signed state to the signed-in person and source. OneDrive's pre-authenticated file URL is fetched with a separate client, without the OAuth bearer header. `source_json` does not return stored secrets.

No high/medium finding in the inspected authorization and import path. Operational limits: provider APIs were exercised with fakes, not the owner's real accounts; S3 and WebDAV tests do not prove every provider variant. R4 needs real-account and NAS validation.

Final full API verification after the review fixes: `243 passed, 9 skipped` (`RIPIANO_DEBUG=1 .venv/bin/pytest -q`).
