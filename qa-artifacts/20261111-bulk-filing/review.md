# Bulk sender and document type filing

The Library's selection controls can set or clear the sender and document type on up to 100 loaded documents. The additional controls stay collapsed until requested. Changes are atomic, owner-scoped, and recorded as manual filing choices; clearing a value also prevents a later phrase rule from silently restoring it.

The [desktop](desktop/bulk-filing.png) and [mobile](mobile/bulk-filing.png) screenshots show two synthetic documents after their sender and document type were set together. The browser journey also adds and removes a tag, clears the sender, checks both document rows after each change, and checks the mobile viewport for horizontal overflow.

Verification on 11 November 2026: 36 API tests passed; the PostgreSQL bulk-filing test passed; `makemigrations --check --dry-run` found no changes; the production PWA build passed; all 26 desktop/mobile browser journeys passed. The compact-control journey passed again after the layout change. Installed-device capture and the wider Paperless parity/release gates remain open.
