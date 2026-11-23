# Replacement paper labels review — 2026-11-23

Scope: migration 0068, retired sticker aliases, replacement API, document and Paper archive UI, portable restore, English/Italian copy, and synthetic browser regression.

## Review

- Existing `R-…` labels remain current unless a person explicitly replaces one. Replacement stores the previous code as an owner-scoped alias and allocates a new code under the chosen category row lock. All earlier codes continue to resolve to the same copy; the lookup response identifies a retired label, and the Paper archive shows the new code and a reprint hint.
- The current code is owner-scoped before alias lookup. A different account cannot use another person's old QR or replace its copy. Trashed documents still answer 410 through either current or alias code. Permanent copy deletion cascades to its aliases; numbers remain consumed.
- Portable export includes `PaperStickerAlias` through its model registry. The restore test now checks a retired code, current category, and next counter. This avoids a restored archive reissuing an old code.
- **Medium, fixed during review:** a bare code such as `MED22222` could match both `MED-22222` and an older `R-MED22222`; the former OR lookup returned whichever copy was older. Lookup now tries the exact/current code, then the canonical sequential code, then legacy variants, checking each against current codes and aliases in that order. A regression test covers both current and retired sequential codes alongside the colliding legacy code.
- The replacement control is collapsed inside each paper-copy card, with a confirmation and a category selector. The normal Keep paper copy path stays short. No new dependency or background process was added.

## Verification

- Focused API physical/portable/contract tests after the collision fix: **16 passed**.
- Django `manage.py check`: no issues; migration check: no changes detected.
- Web `npm run build`: passed; Vite's existing large-chunk advisory remains.
- Isolated PostgreSQL stack `ripiano-r14-j2`: migration 0068 applied successfully; **8 Playwright tests passed** across desktop/mobile against the final lookup code, including replacing a label and finding the old QR, document essentials, missing paper, and archive search/filter.
- Full API suite after the collision fix: **467 passed, 17 skipped** (host zbar unavailable).
- `git diff --check`: passed.

No known high or medium finding remains in this slice. Automatic category suggestions are still separate planned work.
