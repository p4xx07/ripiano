# Collection export live check — 12 November 2026

The local Compose stack served the production PWA and API on port 18080 with PostgreSQL, Valkey, and a single OCR worker. Only synthetic QA accounts and documents were used.

- The full API suite passed **67/67**. Django reported no pending migrations and no system-check issues. The production PWA image built.
- The collection export browser journey downloaded a ZIP in both desktop and mobile Chromium profiles. The API test inspected the ZIP manifest, per-document UUID folders, original SHA-256 checksums, tag and note metadata, order, owner isolation, Trash exclusion, changed-file rejection, and invalid selections.
- The full desktop/mobile browser suite passed **62/62** with two browser workers. A prior six-worker run produced two OCR timeouts under the local single-worker queue; both affected journeys passed in isolation after that queue drained. The owner-only journeys also passed after the synthetic account was given the owner role.
- Clean desktop/mobile selected-export captures are in `qa-artifacts/20261112-collection-export`. Scoped code and UX judge reports are in `.omo/evidence`.

This is a selected-document export, limited to 20 documents per ZIP. Complete archive export/import and the broader Paperless parity and real-device gates remain open.
