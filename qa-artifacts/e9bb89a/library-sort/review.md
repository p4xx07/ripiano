# Library sorting

The Library offers recommended order (relevance for text searches, newest otherwise), newest/oldest added, newest/oldest document date, and title A–Z/Z–A. Documents without a document date come last in both date orders. Changing sort reloads the first page; signed cursors bind later pages to the selected order.

The API test pages through 51 documents with repeated titles, repeated or missing document dates, and tied creation times under every explicit order. It checks that every result appears once, counts remain stable, and a cursor cannot be reused after changing sort. PostgreSQL also ran the sort, relevance, and action-cursor tests. The desktop/mobile browser journey changes sort after loading page two, confirms a fresh first page, and checks toolbar overflow. Its [desktop](desktop/library-sort.png) and [mobile](mobile/library-sort.png) screenshots use the browser test fixture; API tests establish the actual ordering.

Verification on 11 November 2026: 34 API tests passed, `makemigrations --check --dry-run` found no changes, the production PWA build passed, and all 24 desktop/mobile browser journeys passed. Browser emulation does not satisfy installed-device capture validation. Independent release scoring remains open.
