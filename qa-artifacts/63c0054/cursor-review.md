# Cursor paging and metadata search follow-up

The read-only code judge blocked checkpoint `63c0054`: offset paging repeated or skipped rows when an import arrived between page requests, and SQLite search lacked an explicit tie-breaker. This change replaces offset paging with a signed cursor bound to the owner, query, and view. The cursor follows the list's order: creation time and ID, due date plus creation time and ID, or an integer search score plus creation time and ID. Refresh starts a new list so newly imported documents are visible.

Simple search now includes tag names, action notes, and physical sticker codes. PostgreSQL uses a plain-text search query; the product has no advanced query editor yet. An integer score avoids floating-point equality errors in PostgreSQL cursor comparisons.

## Verification

- Local SQLite API suite: 25 tests passed after cursor and search changes, including mutation between pages, owner/query/view cursor binding, equal-timestamp search ordering, and dated/undated action pages.
- Running Compose/PostgreSQL: desktop and mobile browser suite passed, 12 journeys. The capture/search journey finds a newly created tag by its name.
- PostgreSQL transaction probe: created 51 synthetic same-timestamp search hits, fetched page 1, inserted another matching document, fetched page 2, checked 51 unique original IDs and fresh-page visibility of the new document; the test transaction was rolled back.
- Web production build, Docker rebuild, and `git diff --check` passed.
- Android JDK 17 unit tests and debug APK assembly passed locally after setting the Gradle wrapper download timeout to 60 seconds. This only addresses a transient CI download timeout; it is not a scanner hardware test.
- The [mobile Library](visual/mobile/library.png) and [mobile action list](visual/mobile/actions.png) captures show the compact Refresh control without crowding the headings.

The earlier [static paging report](../02e536d/pagination-review.md) remains historical evidence and does not certify mutation safety. No personal documents were used.
