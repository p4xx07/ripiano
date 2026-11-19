# Custom-field type-change code review

## Recommendation

**APPROVE**

## Scope reviewed

- API conversion preview and commit: `services/api/archive/custom_field_views.py:146-232`.
- Owner-lock serialization added around saved-view create/update: `services/api/archive/metadata_views.py:219-269`.
- Route and PWA management/review dialog: `services/api/ripiano/urls.py:31-35`, `apps/web/src/CustomFieldsPanel.tsx:105-223`.
- API and desktop/mobile browser scenarios: `services/api/archive/test_custom_field_type_change.py`, `apps/web/e2e/custom-field-type-change.spec.ts`.

## Verification reproduced

- `RIPIANO_DEBUG=1 uv run pytest -q archive/test_custom_field_type_change.py archive/test_custom_fields.py` — **4 passed**.
- `RIPIANO_DEBUG=1 uv run python manage.py check` — no issues.
- `RIPIANO_DEBUG=1 uv run python manage.py makemigrations --check --dry-run` — no changes detected.
- `git diff --check` — clean.

The evidence provided for this slice also includes a passing desktop/mobile Playwright journey and clean synthetic screenshots under `qa-artifacts/20261112-custom-type`; I inspected those artifacts and the browser scenario source.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Review notes

The commit path re-runs the preview while holding the owner and field locks. Custom-field value writes now acquire the same field lock first, and saved-view create/update acquire the owner lock before validating their custom-field rules. This avoids a stale preview being committed after an incompatible value or saved search is introduced. Conversion is transactional: invalid input or an active saved-search dependency returns 409 before any values or the field kind change.

The implementation reuses existing normalization for text, number, and date. The small boolean compatibility mapping is required because historic text values use human-readable `yes`/`no`, while boolean storage requires `true`/`false`; it is scoped to the conversion boundary. The conversion test covers atomic rejection, normalization, field-qualified and range search behavior, saved-search dependencies, owner isolation, and values on trashed documents. The browser test exercises the actual blocked-review and successful-confirmation flows instead of mirroring internals.

## Skill-perspective check

I searched the configured local skill roots for `remove-ai-slops` and `programming` skill files; they were unavailable. I applied their stated review criteria directly. The production extraction is necessary to share one conversion protocol between preview and commit; it does not introduce a parallel parser or untyped escape hatch. The API and browser tests are behavior-driven, not deletion-only, tautological, or brittle prompt tests. No violation found.

## Verdict

`codeQualityStatus`: **CLEAR**

`recommendation`: **APPROVE**

`blockers`: None.
