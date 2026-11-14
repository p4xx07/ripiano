# Field-qualified Library search

The search box accepts `title:`, `text:`, `note:`, `tag:`, `sender:`, `type:`, `sticker:`, and `date:YYYY-MM-DD`. Quoted names with spaces work. Field clauses combine with each other, ordinary text, and the visual Library filters. Search help is available directly below the search box. Plain text search remains available.

The API tests cover owner isolation, each field, combined clauses, invalid dates, cursor paging for a field-only query, and a cursor rejected after the query changes. The browser journey combines sender, type, tag, and date, confirms one result, opens the syntax help, and checks mobile overflow. [Desktop](desktop/field-search.png) and [mobile](mobile/field-search.png) screenshots show the running stack with synthetic documents.

Verification on 10 November 2026: 33 API tests passed, `makemigrations --check --dry-run` found no changes, the production PWA built, and all 24 desktop/mobile browser journeys passed. Browser emulation does not satisfy installed-device capture validation. Boolean and range syntax remain outside this slice; independent release scoring remains open.
