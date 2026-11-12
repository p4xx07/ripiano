# Office upload evidence — 12 November 2026

Synthetic `.docx`, `.xlsx`, and `.pptx` fixtures only; no personal documents. The desktop and mobile Playwright journeys uploaded it through Browse files, waited for processing, compared the downloaded original byte-for-byte, checked the archive begins with `%PDF-`, and found the document using `text:Ripiano`. Each screenshot uses a fresh one-document local account.

- `desktop/search.png`, `mobile/search.png`: live Library result and extracted-text snippet.
- `desktop/document.png`, `mobile/document.png`: original, portable ZIP, searchable PDF, and reprocess actions.
- Focused API tests: 3 passed. Full local API suite: 72 passed, 1 PostgreSQL-only test skipped. Full PWA browser suite: 64 passed, 2 retention tests skipped because dedicated retention credentials were not supplied.
- The converter route was smoke-tested inside Docker with the same fixture. Before choosing normal PDF output for Office, the PDF/A step altered extracted letters; normal PDF retained the exact text.

The code judge was unavailable due to an agent usage limit. This is working implementation evidence, not a full parity or R4 release approval.

A second desktop/mobile browser journey batch-uploaded the synthetic Excel and PowerPoint files, waited for both PDFs, checked each preserved original byte-for-byte, and searched for each document's converted text. The full three-format browser suite now has four journeys.
