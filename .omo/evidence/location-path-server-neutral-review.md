# Location paths and server-neutral copy: review (2026-11-24)

## Scope

Reviewed the API and web diff for one-step physical location paths, paper-copy moves, label stability, and general server wording. Checked that the changes add no dependency, process, or persistent schema field and retain the existing `location_id` and semantic-mode API values.

## Findings and resolutions

- **High, fixed:** creating a paper copy with a new path could leave locations behind if the paper category was invalid, because returning a 400 inside `transaction.atomic` does not roll back. Path creation now happens after category validation and code allocation; the API test checks that the rejected path is absent.
- **Medium, fixed:** a printed paper sticker included its current location, so a successful move left stale text on the sticker. New paper labels omit the location; the QR resolves the current location. Location labels still show their own paths. Old printed paper stickers can be reprinted.
- **Medium, fixed:** a failure to refresh the location selector after a successful create or move could be reported as a failed action. Selector refresh is now best effort after the saved response.
- **Low, fixed:** typing a path and choosing an existing place could leave conflicting UI values. Each choice clears the other. Scanning another sticker clears a previously typed move path.
- **Low, fixed:** the new move input was cramped in the old horizontal row. The row now uses a two-column grid: existing-place selector above, path and Move below, with the path allowed to shrink on narrow screens.

## Verification

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q`: 483 passed, 17 skipped (optional zbar-dependent cases).
- `npx tsc --noEmit -p . && npm run build`: passed; existing large-chunk warning remains.
- `docker compose -f deploy/docker-compose.yaml --env-file deploy/env.example config --quiet`: passed.
- `git diff --check`: passed.
- Product-facing README, user guide, parity table, deployment example, and EN/IT web messages were scanned for NAS and device-specific terms; only historical decisions and optional hardware-specific guides retain them.

## Remaining manual check

Verify the two path fields and the move row at desktop and phone widths in the running browser. The user's existing local archive must not be modified for this check.

## Browser verification (second pass)

Ran on a throwaway stack built from this working tree (fresh volumes, port 18140); the owner's local archive was not used.

- `e2e/location-path.spec.ts`: the first run failed only because the new path also appears as an option in the "Inside" list (strict-mode match); the test now looks in the location list. Passes on desktop and phone.
- Physical-archive specs (`location-*`, `physical-missing`, `sticker-reservation`, `paper-category-suggestion`): pass.
- Specs that asserted the old NAS/Mac wording were updated to the new copy: `judge-round11`, `nas-browse`, `job-controls`, `agents`, `round2-navigation`, `judge-round6` (move notice).
- Full suite (`--grep-invert visual`): 401 passed, 26 failed, 51 skipped before those test updates. The same failing files were rerun against a second stack built from `HEAD` without these changes: 23 failures already happen there (pre-existing, from earlier commits or the test environment: `dashboard-collections`, `email-intake` and `sharing` need the test mail server, `judge-round4-j2` ASN hint, `judge-round6` sticker focus and unsaved-edit cases, `judge-round7` unsaved step, `judge-round11` workflow "Came from" checkbox, `nested-tags`, `storage-paths`). These are not caused by this change and are left for a separate fix.
- `language.spec.ts` expects an empty To do list; it fails only after the full suite has left open items on the shared test account, and passes on the baseline stack.
