# Share-link live check — 12 November 2026

The local Compose stack served the production PWA and API on port 18080 using PostgreSQL, Valkey, and a single OCR worker. Only synthetic QA accounts and documents were used.

- The local API suite passed **69 tests with one PostgreSQL-only concurrency case skipped**; the isolated PostgreSQL share suite passed **3/3**, including that case. Django migration drift and system checks passed; migration `0025_sharelink` applied in the local stack. The production PWA built.
- The complete desktop/mobile Chromium browser suite passed **64/64** with two Playwright workers. The new sharing journey created a one-day link, downloaded exact original bytes with an anonymous request, revoked the link, and confirmed a 404 afterward in each profile.
- After a code judge found a revocation race, the public read, owner revoke, and Trash flows now use matching document/link row-lock order. The three share-link tests passed in an isolated PostgreSQL test database, including a concurrent revoke waiting for locked authorization. The targeted desktop/mobile sharing journeys passed again on the rebuilt API.
- The desktop/mobile created and revoked captures are in `qa-artifacts/20261112-share-links`; the bearer token is masked in screenshots. Scoped code, UX, and gate judge reports are in `.omo/evidence`.

This slice shares original bytes only. Share bundles, email sending, broader human permissions, full archive import, real-device checks, and other R4/9.5 release gates remain open.
