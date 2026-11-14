# Custom-field type-change live check — 12 November 2026

The local Ripiano PostgreSQL/Valkey/Compose stack served the production PWA on port 18080. Synthetic test accounts and documents were used; no personal documents were captured.

- The new desktop/mobile browser journey created a text custom field, showed an invalid value blocking a number conversion, corrected the value, previewed `001.20 → 1.2`, confirmed the conversion, and found the document through numeric field search.
- The complete API suite passed 66 tests, including atomic rollback on invalid values, owner isolation, saved-search blockers, converted numeric/boolean/date values, and values on a trashed document. `makemigrations --check --dry-run` reported no changes and Django system check reported no issues.
- The complete Chromium desktop/mobile browser suite passed 60 journeys. The production PWA image built successfully.
- Isolated one-document desktop/mobile blocked and converted-state screenshots are in `qa-artifacts/20261112-custom-type`. Scoped code and UX judge reports are in `.omo/evidence`.

A large-archive conversion benchmark and the broader Paperless parity/release gates remain open.
