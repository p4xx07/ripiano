# Conservative paper category suggestion review — 2026-11-24

Scope: browser-side suggestion when registering a paper copy from an already tagged document. No model call, background job, or backend change.

## Review

- The proposal uses an attached tag or its parent only when that name exactly matches a paper category or a small broad-topic synonym. It never classifies from OCR text, title, location, or sender, which could silently make a permanent printed code misleading. `VAR` remains the fallback.
- If two distinct categories match, the proposal stays `VAR`. Duplicate category names are treated as ambiguous. The existing copy's category wins for another copy, preserving the topic already on paper. A person's selection stops automatic updates while the dialog is open.
- **Low, fixed during review:** `Auto` is ambiguous between a vehicle and "automatic" in an English/Italian archive. It was removed as an `AUT` synonym; `Automobile` and `Veicoli` remain clear.
- The suggestion source tag is shown beside the selector and the person can change it before creating the sticker. No new always-on component or dependency was added.

## Verification

- `npm run build`: passed (existing Vite large-chunk advisory).
- Pure suggestion cases run in Playwright: parent tag, conflicting topics, unknown bill tag, ambiguous duplicate category name, ambiguous `Auto`, and category of an existing copy.
- Isolated `ripiano-r14-j2` stack: **10 Playwright checks passed** across desktop/mobile against the final build. The full flow created a custom category and matching tag, uploaded a document, confirmed the suggested prefix, printed/located the copy, replaced its label, and found its old QR. Archive, missing-paper, and document-essentials regressions also passed.
- `git diff --check`: passed. Backend code did not change in this slice; the preceding backend checkpoint passed **467 API tests, 17 skipped**.

No high or medium finding remains in this slice.
