# Scannable shelf and box labels — 11 November 2026

On the local PostgreSQL stack, create a shelf and nested box, file a paper copy in the box, print the shelf's label, follow its QR URL, and open the nested document from the shelf contents. The browser journey passed in desktop Chromium (1440×900) and mobile emulation (390×844). The PNGs in `desktop/` and `mobile/` show the resulting shelf contents.

The full API suite passed 47 tests, including location-code creation, QR destination, HTML escaping, owner isolation, Trash exclusion, nested lookup, and paging beyond 50 copies. Migration check reported no changes, the production PWA build passed, and the full browser suite passed 36/36 journeys on the local PostgreSQL stack. The migration was also applied on that stack. Installed PWA scanning, physical label printing, and real mobile scanner checks remain open release gates.
