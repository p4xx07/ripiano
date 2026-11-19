# Round 7 fixes — independent review

Scope: uncommitted changes on `codex/initial-implementation` (git diff plus untracked `migrations/0060_…`, `test_round7_fixes.py`, `e2e/judge-round7.spec.ts`), checked against the judge round 7 reports and DECISIONS D9 and D10. I read the code only. I ran:

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_round7_fixes.py archive/test_round5_fixes.py archive/test_round2_language.py`: 22 passed, 6 skipped. The skipped tests need PostgreSQL, including the hyphenated-number search test.
- `npx tsc --noEmit`: clean.
- A small script that calls `run_detail_to_italian` directly, with tricky inputs and worst-case inputs.

I did not run Playwright or docker.

No high-severity findings.

## Medium

### M1. A link from an account turned off before this change, or outside People, comes back when the account is turned on again (D9)
`services/api/archive/people_views.py:186-188` runs `_end_access(user)` only when the account goes from active to inactive (`if user.is_active and not body["is_active"]`). Some accounts are inactive without passing through that step:

- accounts turned off before this deploy (migration 0060 does not backfill revocations);
- accounts turned off in Django admin (`/admin/` is mounted, `ripiano/urls.py:145`, and the auth User change form edits `is_active` directly);
- accounts turned off with a shell or SQL update.

Their links and bundles keep `revoked_at = NULL`. While the account is off, only the new owner-inactive guard refuses them (`share_views.py:98-99`, `bundle_views.py:199`). When an admin turns the account back on in People, the guard passes again and every old link and bundle works again without the owner choosing to share anything. D9 says turning the account on "does not revive them silently". `test_round7_fixes.py:89` sets up exactly this state (`update(is_active=False)`) but never turns the account back on, so the gap is untested.

Scenario: Anna was turned off last week, before this deploy. Her 7-day link to a lease is still unexpired. Today an admin turns her back on in People, and the link downloads the lease again.

Fix options:
- in `person_detail`, also revoke (reason `account_off`) any unrevoked links and bundles when turning an inactive account **on**, if the account was inactive;
- or add a data migration that revokes the links and bundles of currently inactive users.

The same gap already exists for API tokens and agent grants (judge round 5, M2). This change keeps that pattern.

## Low

### L1. A bundle revoked with the account keeps its ZIP on disk for up to an hour
`people_views.py:148` revokes bundles with a queryset `.update()`. When the owner revokes a bundle (`bundle_views.py:183-186`), `remove_bundle_files` is called on commit. Here it is not, so the ZIP of the owner's documents stays in MEDIA_ROOT until the hourly `expire-share-bundles` beat (`ripiano/celery.py:56-58`, `bundle_views.expire_bundles`). Nothing serves the ZIP during that time, because the link view refuses the bundle. The issue is data at rest and is inconsistent with a manual revoke.

Fix: collect the bundles and call `transaction.on_commit(lambda: remove_bundle_files(bundles))`, as `bundle_views.py:77-79` already does.

### L2. A custom field whose value is the text "yes" or "no" is shown translated
`messages_it.RUN_DETAILS` maps `"set field {0} to yes"` to "… a sì" and sorts these entries ahead of `"set field {0} to {1}"`. `workflows.py:213` writes the literal `yes`/`no` only for BOOLEAN fields, but a text field whose value is `yes` produces the same English detail. I confirmed with the script that `run_detail_to_italian("set field Note to yes")` returns `"impostato il campo Note a sì"`, which rewrites user data.

The other separator and name cases behave safely:
- tag names containing `, ` are absorbed correctly by backtracking (`"added tag Rossi, Mario"` stays one tag);
- `{1}`, `\1` and `\g<0>` inside names are not expanded (`_fill` uses a lambda replacement);
- details cut at 500 characters fall back to the English text unchanged;
- worst-case 500-character inputs translate in well under 1 ms.

Two remaining ambiguities are inherent in the English format and harmless:
- a field name containing " to " splits at the first " to " (`"set field Ref to 3 to 4"` becomes `"… campo Ref a 3 to 4"`);
- a tag named like `"a, removed tag b"` is read as two parts.

Fix: write booleans differently in `workflows.py` (for example `set field {0} on/off`), or keep the yes/no templates only when the stored detail marks the field as boolean.

### L3. A locked PDF counts as an OCR failure, so the next real failure says "failed again … probably damaged"
`tasks.py:165` increments `processing_failures` for every exception, including `LockedPdfError` (`tasks.py:117-119`). A locked PDF shows its own message. If a later retry fails with a low-level error, the fallback chosen at `tasks.py:167` is `generic_again` ("probably damaged") on what is the first real OCR failure.

The counter logic is otherwise correct:
- it resets to 0 only on success (`tasks.py:154`) and survives Retry OCR;
- `damaged_pdf` increments it too;
- it is capped at 1000, inside PositiveSmallIntegerField.

Migration 0060 is a plain AddField with constant defaults, so it is cheap on PostgreSQL. The `processing_failures` value comes from the row loaded at claim time, so the theoretical lost update needs two workers on the same document, which the PENDING→PROCESSING claim prevents.

### L4. Numeric searches now also match numbers after a hyphen in dates and ranges
`fulltext.py:81-84` ORs `plainto_tsquery('simple', '-<digits>')` into each all-digit word. This is safe from SQL injection:
- the word is restricted to ASCII digits (`isascii() and isdigit()`);
- it is passed as a bound SearchQuery parameter.

The cost is broader matching. PostgreSQL's parser stores the later parts of hyphenated numbers as signed ints, which is the premise of the fix. Searches such as `11`, `05` or `2026` should now also match any text with an ISO-style date or a range like `2026-11-05` or `1-5`. Before the change they did not. This is intended for codes like `Fattura-2026-031`. It is a recall change, not a bug, and worth a line in USER_GUIDE. I could not check this on PostgreSQL: the search test is skipped on SQLite.

## Checked and fine

**D9, leaks and revival paths.**
- Unknown, revoked, expired and inactive-owner links all return the same `404 {"error": "Link not found"}` (`share_views.py:89-100`, `bundle_views.py:192-200`).
- `revoked_reason` appears only in owner-authenticated JSON (`_share_json`, `_bundle_json`), never to anonymous callers.
- No endpoint un-revokes a ShareLink or ShareBundle.
- The bundle builder only updates rows with `revoked_at__isnull=True` (`bundle_views.py:125`).
- Person-to-person grants (`DocumentAccess` / `ObjectAccess`) are not touched by `_end_access`. D9 covers only public links, so this matches the decision; note it if the owner expects grants to end too.

**D10, check order.** The forget path checks, in order:
1. owner (403);
2. grant exists and belongs to the caller (404);
3. grant is not still active (409);
4. JSON body (400);
5. sign-in throttle (429);
6. password (400, counted towards the throttle).

The grant is deleted only after all of these pass. Plain revoke (without `forget`) still needs no password, as intended. The throttle keys are shared with sign-in (tested in `test_round7_fixes.py:131`). The web client sends the body on DELETE (`AgentPanel.tsx`, `remove()`).

**CSRF retry (`api.ts`).**
- It triggers only for an unsafe request that gets a 403 and either sent no token or received the exact CSRF-failure message. That message comes only from `CSRF_FAILURE_VIEW` (`security_views.py:15-25`), which Django calls before the view runs. The app has no `csrf_exempt` views, so the first attempt cannot have had side effects.
- It retries at most once (`csrfRetried`), so it cannot loop.
- Re-sending a `FormData` or string body is valid.
- Uploads carry `X-Ripiano-Scan-ID`, so even a later queue resend is deduplicated.
- `isRetryable(403, csrfFailed)` keeps a file only for a CSRF 403. Any other 403 is still treated as a refusal.

**`stickerCodeFrom` (PhysicalPanel).**
- The regex is anchored on `[?&#]`, so `notsticker=` does not match.
- A bad `%` falls back to the code as typed.
- The code is `encodeURIComponent`-ed into the path, so `../` and `/` inside a pasted URL cannot change the API route. Unknown codes give a 404, shown as "not found".

**`useFieldError` (ui.tsx).** The ref callback is recreated on each render, so React detaches and reattaches it, and the Map stays consistent. `aria-describedby` points at the error element only while the field is marked invalid.

**DocumentPanel.**
- The `beforeunload` listener is added only while `dirty` and removed in the effect cleanup, so there is no leak and no prompt once the edits are saved.
- The inline `alertdialog` has `aria-labelledby` and `aria-describedby` pointing at elements that exist.

## Resolution (before commit)

| Finding | Outcome |
|---|---|
| M1 links revived for accounts turned off outside People | Fixed: `person_detail` runs `_end_access` on any on/off change, so turning an account back on also ends leftovers from an account switched off in admin, a shell or an older version. Test `test_turning_on_an_account_turned_off_elsewhere_does_not_revive_its_links`. Re-activation through Django admin itself is still outside this path; the inactive-owner check covers links only while the account is off. |
| L1 bundle ZIP kept up to an hour | Open (low): removed by the hourly cleanup; the link already refuses access. |
| L2 text value "yes" shown as "sì" | Open (low). |
| L3 locked PDF counted as OCR failure | Open (low). |
| L4 number search widening | Accepted: matches the user's digits as written; judged a reasonable trade-off. |
