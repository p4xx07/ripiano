# Contextual search excerpts

The Library shows a short passage around the matching OCR text instead of the document's opening text. Search matches in action notes and physical sticker codes are labelled with their source. The unfiltered Library stays compact and does not show unrelated OCR text.

The API test covers a match deep in OCR text, action-note and sticker matches, the unfiltered result, and owner isolation. The desktop/mobile browser journey uploads a document, waits until its OCR text is searchable, and checks that the result row contains a labelled excerpt and the searched text. [Desktop](desktop/search-snippet.png) and [mobile](mobile/search-snippet.png) screenshots show that row in the running stack.

Verification on 10 November 2026: 32 API tests passed, `makemigrations --check --dry-run` found no changes, the production PWA build passed, and all 24 desktop/mobile browser journeys passed. Browser emulation does not satisfy the installed-device capture gate. Independent release scoring remains open.
