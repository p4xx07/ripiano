# Custom detail filters — 11 November 2026

On the local PostgreSQL stack, create a typed document field, filter the Library by that field and value, save the filter as a search, clear the controls, and reopen the saved search. Then remove the saved search, rename the field, clear its document value, and delete the unused field definition. This end-to-end journey passed in desktop Chromium (1440×900) and mobile emulation (390×844). The screenshots show the active field and value filter on each layout.

The API suite checks owner isolation, type validation, field-only and value filters, cursor binding, saved-search persistence, and deletion protection while a field is used by a document or saved search. The full browser suite passed 42/42 journeys with three workers and a 120-second per-test limit. Browser emulation does not verify installed PWA capture or the native Android scanner on hardware.
