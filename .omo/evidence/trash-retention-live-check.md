# Trash retention live-stack check — 12 November 2026

Local synthetic PostgreSQL/Valkey/Compose stack on port 18080, using the real API, maintenance worker, scheduler image, and PWA. No personal documents were used.

- Migration `archive.0024_trashretentionpolicy` applied in the running API container.
- A synthetic owner had an enabled 30-day policy and one document with `trashed_at` 31 days earlier. The maintenance-queue task `archive.tasks.purge_expired_trash` was queued as `ed9a00ab-8b6a-4adc-8148-7242b4f1f0fe`.
- For document `22b6432d-c537-4a89-b2f8-ab0d000e85d0`, the follow-up query returned `document_exists False`, purge job `complete`, and `file_exists False` for its preserved original. The synthetic policy was then disabled.
- A later manual snapshot `20261112T144226196228Z-bffd5c05` completed, and `verify_snapshot` checked its manifest, database dump, schema migration set, and 2,659 media files.
- `RIPIANO_DEBUG=1 uv run pytest -q` passed 64 API tests; migration and Django system checks passed. The full Chromium desktop/mobile browser suite passed 58 journeys. After the final spacing-token adjustment, the production PWA image rebuilt and both targeted retention journeys passed again.

These checks do not replace the NAS ACL/restore or real-device release gates.
