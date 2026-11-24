# Paper category and sequential labels review — 2026-11-23

Scope: model/migration 0067, category API, paper copy allocation and lookup, Paper archive category controls, document copy picker, legacy barcode compatibility, tests and docs.

## Findings and disposition

- **Medium, fixed:** six new API errors were missing from the Italian message catalog. `test_api_language.py` caught this in the first full run (464 passed, 17 skipped, 1 failed). Added exact translations; the next full run passed.
- **Medium, fixed:** the new category selector made three older browser tests' broad `.new-copy select` locator ambiguous, and an old test expected Save changes after a copy action that now saves immediately. Replaced locators with the labelled location selector and updated the assertion.
- **Low, fixed:** the first browser prefix generator used base-26 digits; the form correctly stripped them, making the asserted prefix differ. Switched to explicit A–Z letters.
- **Reviewed:** the dropped global uniqueness of `sticker_code` is necessary for independent owner sequences. Allocation locks the owner/category row and checks any existing same-owner code; lookup is owner-scoped. Migration 0067 applied on the isolated PostgreSQL stack without rewriting existing `R-…` stickers. `L-…` location codes and ASN scan processing remain separate.
- **Reviewed:** portable whole-archive export includes the new model automatically. A restore test now verifies the category, number, and next counter. Document ZIP still includes the sticker code; adding category name there is optional metadata.
- **Open by design:** automatic topic suggestions from explicit filing rules/confident tags, and a Replace label flow that preserves old codes as aliases, are documented in `docs/PHYSICAL_LABELS_PROPOSAL.md`. Their absence does not affect existing or new label lookup; they need a later slice.

## Verification

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q`: **465 passed, 17 skipped**. Skips require the host zbar library.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`: no changes detected.
- `npx tsc --noEmit -p .` and `npm run build`: passed. Vite emitted its existing large-chunk advisory.
- Focused Playwright flows on isolated `http://localhost:18122`: **8 passed** across desktop and mobile. Included category add/rename, sequential code, QR location, document essentials, archive search/filter, missing paper. The initial run at `127.0.0.1` was rejected by CSRF because the synthetic stack's configured origin is `localhost`; rerunning with the configured origin passed.
- `git diff --check`: passed.

No new runtime dependency or always-on process was added. The owner's local stack on port 18125 was not changed.
