# Related documents review — 11 November 2026

On the local PostgreSQL stack, upload two documents, search for the second from the first document's detail panel, link them, open the second through the link, confirm the reciprocal link, then unlink them. This passed in desktop Chromium (1440×900) and mobile emulation (390×844). The PNGs in `desktop/` and `mobile/` show the linked state.

The full API suite passed 49 tests. Link coverage checks reciprocal lookup, duplicate rejection, owner isolation, renamed titles, Trash hiding and Restore, and deletion from either side. Migration check reported no changes, migration 0019 was applied on the local PostgreSQL stack, the production PWA build passed, and the full browser suite passed 38/38 journeys after separating the new section from Files. Installed mobile PWA and native scanner checks remain open release gates.
