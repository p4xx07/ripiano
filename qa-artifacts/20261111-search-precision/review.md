# Search precision and visible manual tags

PostgreSQL's `SearchRank` can return a positive score for a query that does not fully match a document. The Library now requires the full text-search predicate before using the rank for ordering. A regression test distinguishes `invoice-2026-AB123` from `invoice-2026-AB456` and checks the result on PostgreSQL. The local archive's previously broad `bulk-1794390744111-desktop` query returned 20 documents before the fix and only the intended two after it.

The compact tag summary puts manually chosen tags before model or rule tags. The [desktop](desktop/search-precision.png) and [mobile](mobile/search-precision.png) browser screenshots show a plain hyphenated search with two results and the newly added manual tag visible on each row. The browser journey also completes bulk filing and checks mobile horizontal overflow.

Verification on 11 November 2026: 37 API tests passed; three targeted PostgreSQL search tests passed; `makemigrations --check --dry-run` found no changes; the production PWA build passed; all 26 desktop/mobile browser journeys passed. The screenshots use synthetic documents and browser emulation. Wider parity and release gates remain open.
