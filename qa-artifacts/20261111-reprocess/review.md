# Rebuild OCR from the original

A ready or failed document can queue OCR again from its preserved original. Pending or processing documents cannot queue a duplicate run. The document panel keeps the original download available, polls processing status, and restores the searchable PDF link when the new run completes. Failed documents still have the existing Inbox retry path.

The [desktop](desktop/reprocess.png) and [mobile](mobile/reprocess.png) screenshots show the files section after a successful rebuild. The browser journey uploads a synthetic image, waits for OCR, requests another run, compares the original download bytes before and after, waits for the new searchable PDF, and finds its OCR text again.

Verification on 11 November 2026: 41 API tests passed; PostgreSQL reprocess/retry tests passed; `makemigrations --check --dry-run` found no changes; the production PWA build passed; all 30 desktop/mobile browser journeys passed with three workers and a 120-second per-test limit. Browser profiles are emulated; installed-device capture and wider Paperless parity remain open.
