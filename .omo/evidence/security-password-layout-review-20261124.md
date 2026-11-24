# Security password layout review — 24 November 2026

## Symptom and cause

The owner's screenshot showed the three Security password labels, hint, and browser-default inputs flowing inline. `PasswordPanel` used the shared `Field` component without the `detail-label` class that supplies the project's stacked field layout and input styling.

## Change and review

Each password `Field` now uses `detail-label`. This keeps the existing accessible names, password handling, validation, and submission behavior. The Security form still limits its width to 520 CSS pixels. A separate review pass found no other fields in this form missing the class and no new runtime dependencies. The fix changes presentation only.

## Evidence

- TypeScript check and production web build: passed.
- Playwright against the rebuilt local stack: **2 passed** (desktop and mobile Chrome emulation). The test checks that each field label uses the grid layout and each input fills the form width. The first exploratory run used an exact label locator that missed the new-password hint; the role-based locator passed without changing application code.
- Rendered form screenshots: [desktop](../../qa-artifacts/20261124-security-password/desktop.png) and [mobile](../../qa-artifacts/20261124-security-password/mobile.png). Both show separate labels, hint, full-width inputs, and aligned button.
- The temporary test account was removed after the browser run. No password change was submitted and no user archive data was touched.
