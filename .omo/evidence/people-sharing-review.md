# People, groups, and document sharing — independent review

Reviewer: independent code/security/UX pass on the uncommitted slice (no edits by the reviewer).

## Fixed before commit
- **High — no re-authentication on People:** creating people, setting a password, and turning accounts on/off now require the admin's current password (same throttle as sign-in). Admins cannot reset another admin's password or their own from People.
- **Medium — tokens could share documents:** non-GET `/api/documents/<id>/access` is blocked for API tokens (test added).
- **Medium — shared search leaked ASN/sticker:** `asn:`, `sticker:`, `is:`, `field:` are rejected in the shared view; sticker matches and sticker/field snippets are off for non-owners (test added).
- **Medium — editor changes ran owner workflows:** UPDATED workflows now run only on the owner's own changes (test added).
- **Medium — no self-service password:** `POST /api/account/password` (current password required, other sessions and tokens end, this session stays). Security screen has a Password form.
- **Low:** last-admin check locks all active admins; non-owner payload drops `error`; group export drops Django permission IDs; Share clears the picker only on success; Turn off account has a confirm step; Retry button typed; group name input has a visible label.

## Accepted / open (low)
- Username case race between two simultaneous creates (pre-check plus DB unique on exact username).
- Turning an owner off does not end their existing shares or public links (documented behavior: their documents stay as they are).
- Owner and editor edits are last-write-wins, like owner edits from two devices.
- Shared view has no page preview (download and searchable PDF only).
- People screen has no browser journey (the e2e account is not an admin); API tests cover it.

## Verification
- API: full suite green; `archive/test_people.py` covers admin rules, tokens, sharing levels, search leaks, workflows, password change, last admin.
- Browser: `people-sharing.spec.ts` (owner shares → reader edits and notes → owner removes access) passes; share-links, notes, dialog-focus, location-label, physical-missing, two-factor rerun green.
