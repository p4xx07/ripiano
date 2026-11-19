# Mixed-file capture evidence

Base commit: `15bdc1d`.

The browser previously stopped a multi-file selection at its first rejected file. The upload loop now attempts every selected file, returns to the Library with the search cleared so accepted files are visible, and reports rejected filenames without losing the accepted uploads. Progress shows the current file number. Background document refreshes no longer dismiss the upload error before the user can read it.

Verification: `npm run build` passed; the local Compose web stack rebuilt and became healthy; 18 Playwright journeys passed across desktop and mobile before the final refresh-feedback check. The focused two browser journeys then passed after that check was added. They selected valid PNG, invalid text, valid PNG in one batch, checked both PNG documents and the one rejection, refreshed the Library, and verified the rejection remained visible. This used the real upload API and the disposable synthetic QA account.

The browser suite uses emulation. Installed PWA behavior and Android native capture still require physical-device validation.
