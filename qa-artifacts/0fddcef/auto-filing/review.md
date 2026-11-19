# Automatic filing checkpoint

The running local Compose stack was tested with a disposable owner account and a synthetic PNG. On both desktop and mobile browser profiles, the user created a sender and document type, attached a title phrase to each, uploaded the file, and found it in the Library with both fields populated after OCR. The details panel identified each value as a phrase match. Changing only the title preserved the automatic origins for both fields and an existing automatic tag.

Evidence: [desktop matching phrases](desktop/matching-phrases.png), [desktop filed document](desktop/automatic-filing.png), [mobile matching phrases](mobile/matching-phrases.png), and [mobile filed document](mobile/automatic-filing.png).

Verification at this checkpoint: 28 API tests passed, Django migration drift check found no changes, production web build passed, and 24 desktop/mobile Playwright journeys passed. Browser profiles are emulated; this does not establish installed PWA or physical Android camera behavior.
