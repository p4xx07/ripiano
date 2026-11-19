# Reversible Trash review — 11 November 2026

## Scenario

On the local PostgreSQL stack, upload a synthetic image, wait for OCR, search by title, move it to Trash from the document panel, confirm it disappears from the Library and detail API, open Trash, restore it, and find it again. The scenario passed in Chromium desktop (1440×900) and mobile emulation (390×844). The screenshots in `desktop/trash-page.png` and `mobile/trash-page.png` show the reviewed restore surface.

## Verification

- API: 45 tests passed, including owner isolation, MCP denial, download and note denial, sticker restore notice, preserved original/archive bytes, trash cursor ordering, OCR-in-progress guard, and Android scan retry behavior.
- Migration check: no model changes pending.
- Production PWA build: passed.
- Full browser suite: 32 of 32 desktop/mobile journeys passed with 3 workers on the local stack. After the document-row locking review, the 10 affected archive, note, filing, bulk edit, and Trash journeys passed again against PostgreSQL.

Trash is reversible. There is no permanent purge or retention timer yet. Browser mobile emulation does not prove installed PWA or Android hardware behavior; those remain release gates.
