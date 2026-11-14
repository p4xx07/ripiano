# Saved searches

The Library now keeps owner-scoped saved searches containing text, tag, sender, document type, and document-date filters. A person can create one from the current search, reopen it, rename it, replace its criteria, or delete it. Results and filter controls update together. The actions remain usable at mobile width, and focus returns to the relevant control after saving or deleting.

The desktop/mobile browser journey saves a filtered search, clears filters, reopens it, renames it, changes its date criteria, reopens it again, deletes it, and checks focus and horizontal overflow. [Desktop screenshot](desktop/saved-search.png) and [mobile screenshot](mobile/saved-search.png) show the running development stack with synthetic documents. The API test checks ownership, validation, and CRUD.

Verification on 9 November 2026: 32 API tests passed, `makemigrations --check --dry-run` found no changes, the production PWA image built, and all 24 desktop/mobile browser journeys passed. Browser emulation does not satisfy the installed-device capture gate. Independent release scoring remains open.
