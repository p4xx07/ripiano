# Document notes

Documents can keep dated notes independently of follow-ups. The owner can add a note, read older notes in pages of 50, and delete a note after an inline confirmation. Plain Library search and `note:` find note text and show a matching excerpt. Note responses and search remain scoped to the document owner.

The [desktop](desktop/document-notes.png) and [mobile](mobile/document-notes.png) screenshots show a synthetic note in the document panel. The browser journey creates it, finds the document by note text, reopens it, deletes the note, and confirms that the search result disappears.

Verification on 11 November 2026: 39 API tests and the migration check passed; PostgreSQL note ownership/search/paging tests passed; the production PWA build passed. The full 28-journey desktop/mobile browser suite passed with three workers and a 120-second per-test limit. A six-worker run first timed out on two late mobile OCR/filing steps while synthetic reclassification jobs queued; those journeys passed alone after the queue drained. The final note-search prefetch adjustment passed targeted PostgreSQL tests and desktop/mobile note journeys. Installed-device and wider Paperless parity gates remain open.
