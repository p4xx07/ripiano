# Missing paper-copy review — 11 November 2026

On the local PostgreSQL stack, create a location and sticker, report its paper copy missing, check that moving is blocked while missing, scan its sticker to see the last known location and warning, then mark it found. This passed in desktop Chromium (1440×900) and mobile emulation (390×844). The four PNGs in `desktop/` and `mobile/` capture the copy card and sticker lookup.

API coverage checks the last known location, distinct missing/found history events, duplicate-status rejection, move blocking, owner isolation, and Trash isolation. The full API suite passed 45 tests with no pending migrations; the production PWA build passed; the full browser suite passed 34/34 desktop/mobile journeys. After adding live status feedback for screen readers, the two missing/found journeys passed again. Installed mobile PWA and real scanner hardware checks remain open release gates.
