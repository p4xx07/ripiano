# Library filters

The Library can combine free-text search with one tag, sender, document type, and document-date range. Result counts and signed page cursors are bound to the selected filters; a cursor from a different filter combination returns HTTP 400. Invalid IDs and inverted dates are rejected. The API test used 51 matching documents, one same-owner exclusion, and a foreign owner's document to check both pages and isolation.

The desktop/mobile browser journey created a tag, sender, and type, assigned them with a date to a new document, narrowed the Library to that document, verified an empty result after changing the date, cleared filters, and searched again. It includes a mobile panel-overflow assertion. [Desktop screenshot](desktop/library-filters.png) and [mobile screenshot](mobile/library-filters.png) show the final layout.

Verification: 31 API tests, production PWA build, and 24 desktop/mobile browser journeys passed. Browser emulation does not satisfy the installed-device capture gate. Independent release scoring remains open.
