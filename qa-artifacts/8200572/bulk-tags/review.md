# Bulk tagging

The Library can select individual loaded documents or the first 100 loaded results, then add or remove one tag from the selection. The API checks all document and tag ownership before writing, caps the batch at 100, and treats the change as a manual correction so later filing does not immediately reverse it.

The [desktop](desktop/bulk-tags.png) and [mobile](mobile/bulk-tags.png) screenshots show the running stack after adding a tag to two selected documents. The browser journey then removes the tag and checks both rows again. The mobile viewport had no horizontal overflow.

Verification on 11 November 2026: 35 API tests passed; the PostgreSQL bulk-tag test passed; `makemigrations --check --dry-run` found no changes; the production PWA build passed; all 26 desktop/mobile browser journeys passed. The screenshots use browser emulation and synthetic documents. The wider Paperless parity and release judges remain open.
