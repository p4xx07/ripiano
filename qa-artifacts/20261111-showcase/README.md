# Clean app screenshots — 11 November 2026

These six screenshots come from the running local PostgreSQL/Compose stack at `http://localhost:18080`. A separate `showcase` account contains three fictional, selectable-text PDF documents. They were uploaded through the ordinary document API and reached `ready` through the normal processing worker. Their tags, senders, types, saved search, nested locations, and two paper copies were added through the app API. No personal documents were used.

`capture.mjs` signs into that account and captures the Library, Add dialog, and binder contents in desktop Chrome (1440×900) and mobile Chrome emulation (390×844). It requires `RIPIANO_SHOWCASE_USERNAME` and `RIPIANO_SHOWCASE_PASSWORD` in the environment; the local demo password is not stored in Git. The script asserts that the first Library card displays its document date while sorted by document date, using Europe/Rome on desktop and America/Los_Angeles on mobile. This caught and verified a date-only timezone/display fix.

The six PNGs were reviewed at their rendered sizes. Mobile Chrome emulation does not validate camera behavior, an installed PWA, or the Android native scanner on a physical device. The screenshots show an interface state, not a release-readiness score.
