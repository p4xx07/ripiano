# NAS browse copy evidence — 12 November 2026

The Backups screen now starts an owner-only maintenance job that writes a separate, readable copy under `<RIPIANO_BACKUP_PATH>/browse/owners/<owner-id>/complete/<run-id>`. This is a disposable navigation copy. Restorable snapshots remain under `<RIPIANO_BACKUP_PATH>/complete`.

The desktop and mobile Playwright journeys each uploaded one synthetic PNG, waited for OCR, started the browse job from the live UI, waited for completion, and found the resulting folder in the status API. The local maintenance worker published `original.png` and a manifest with one document in each account. The screenshots show the live NAS browse section on both viewports. No personal documents or production NAS paths were used.

The focused API tests cover owner-only access, duplicate-job rejection, year/tag folders, original/PDF/OCR/metadata contents, manifest checksums, interrupted-publication reuse, retention, changed-original rejection, and no partial publication. The final API suite passed 74 tests with one PostgreSQL-only skip. The isolated full desktop/mobile browser suite passed 66 journeys; four dedicated-account journeys (NAS browse and Trash retention, two viewports each) were skipped in that shared-account run. Both NAS browse journeys passed separately on the final local stack. The production PWA build, Django system/migration checks, both Compose validations, and diff check passed.

Scoped code, UX, and gate judge reports are in `.omo/evidence`. Their approval covers this browse-copy slice, not the full R4/9.5 release gate.
