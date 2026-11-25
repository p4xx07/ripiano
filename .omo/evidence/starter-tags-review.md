# Starter tags and automatic paper category: review (2026-11-25)

## Scope

New accounts (first owner through setup, people created by the admin) start with English starter tags whose top-level areas match the default paper categories; existing accounts add only missing ones with **Tags & filing → Add missing starter tags**. The paper-category suggestion now flags tags that point to more than one category and asks the person to choose. No migration, dependency, or new process.

## Independent review (Opus 5.5)

No High or Medium findings. Low findings and resolutions:

- **Fixed:** setup created the owner and the starter tags in separate transactions; now one `transaction.atomic()`, with a test that a failed seed leaves no owner and setup can be retried.
- **Fixed:** in People, a starter-tag error inside the `IntegrityError` handler would be reported as "That username is taken"; it now rolls back and returns a server error (test added). A test also checks every starter name and colour against the manual tag rules.
- **Fixed:** `POST /api/tags` rechecks the case-insensitive name under the account lock, so a concurrent starter seed cannot produce "Home" and "home". (A case-insensitive database constraint would need a duplicate check on existing data first; not done.)
- **Fixed:** the Tags screen keeps a persistent live region for the result, so a repeated message is announced, and the notice is cleared by other tag actions.
- **Added tests:** a child name already used in another case or place is skipped; an API token can add its own starter tags without CSRF; other accounts are untouched.

## Verification

- API: 487 passed, 17 skipped (full suite before the Low fixes); `test_starter_tags.py`, `test_people.py`, `test_api_tokens.py`: 19 passed after them.
- Web: `tsc --noEmit` clean; `paper-category-suggestion.spec.ts` 2 passed (all starter areas map to their category, including Italian renames; Warranties alone stays Other without a warning).
- Browser, full suite on a throwaway stack whose setup account received 22 starter tags: 411 passed, 20 failed, 51 skipped. Every failure is in the pre-existing set recorded in `location-path-server-neutral-review.md` (none new); `starter-tags.spec.ts` passed on desktop and phone.
