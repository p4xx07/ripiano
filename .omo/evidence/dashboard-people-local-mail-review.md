# Dashboard collections, People form, and local email — scoped review, 23 November 2026

Scope: the first checkpoint from the owner's hands-on testing. The personal dashboard is an initial set of up to six live saved-search cards, not the later configurable widget layout. No new NAS process or dependency was added. Local GreenMail settings are gitignored and do not affect deployment defaults.

## Read-only review after implementation

- Checked saved-view mutation permissions: the API reads and changes only the signed-in owner's views. The six-card limit is checked while locking the owner row, so simultaneous requests cannot each take the last slot. `dashboard_pinned` is additive in the v1 response; existing fields remain the same.
- Checked card data access: each card calls the existing owner-scoped document search with the saved filters. It requests newest order for the three preview rows; opening one document uses the existing detail authorization path. No document text or other user's data is stored in browser localStorage; only the optional home-view preference is stored there.
- Checked People fields against the screenshot: the missing `detail-label` classes caused the browser-default inputs and adjacent label text. The same class now applies to every affected field; desktop/mobile screenshots show stacked labels, hints and inputs.
- Checked both file links on a real browser test: original and ZIP create completed browser downloads. The specific document shown by the owner had original and archive files and both backend routes returned HTTP 200 in the local stack. The in-app browser's download UI remains unverified, so no browser-agnostic download fix is claimed.
- Checked email only on an isolated stack connected to GreenMail. The document email UI reported Sent after the fake SMTP server accepted it. The owner's local `.env` is gitignored and uses GreenMail; no real recipient was contacted.

## Verification

- API full suite: `RIPIANO_DEBUG=1 .venv/bin/pytest -q` — 460 passed, 17 skipped (zbar-dependent cases skipped locally).
- Focused API/contract/language suite: 40 passed.
- `makemigrations --check --dry-run` — no changes.
- Web typecheck and production build — passed; Vite reported its existing large chunk warning.
- Isolated Chrome desktop/mobile (`ripiano-r14-j2`, synthetic data): dashboard/create/unpin/repin/start-page, People form CSS, document original and ZIP downloads, and document email to GreenMail — 8 passed, 0 failed.

Remaining design work: the owner requested additional widget types, ordering and hiding, a simpler document screen, workflow layout, paper code unification and detected future dates. None of these are claimed by this checkpoint. No new judge score was assigned, per the owner's decision.
