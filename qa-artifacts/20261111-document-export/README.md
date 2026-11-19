# Portable document export — 11 November 2026

On the local PostgreSQL stack, upload a document and download its ZIP from the Files section. The browser journey passed in desktop Chromium (1440×900) and mobile emulation (390×844); the PNGs show the export action. The browser download was available even while OCR was still preparing the searchable PDF.

The full API suite passed 51 tests. Export tests inspect ZIP members and manifest checksums, metadata, OCR text, derived PDF, owner isolation, missing or changed originals, and Trash isolation. Migration check reported no changes, the production PWA build passed, and the full browser suite passed 40/40 journeys. This is a single-document export; full archive export and import remain open. Installed mobile PWA and real scanner checks remain open release gates.
