# Two-step sign-in review (and workflow fix verification)

Independent read-only reviewer: **REQUEST CHANGES**, with no critical findings, 1 high, 4 medium, and 9 low.

It confirmed the following are correct:
- RFC 6238 maths (appendix B vector), `compare_digest`, the ±1-step window, and replay protection.
- Locking with `select_for_update`, and single-use recovery codes.
- Session rotation on login, and CSRF protection on the new endpoints.
- XSS safety of the segno QR SVG.
- The earlier workflow fixes for action reopen, notification crashes, `filter_sources`, IDNA validation, redirects, scheduled starvation, the PATCH trigger scope, and the deep link.

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | Django admin login bypassed 2FA and shared the app session. | The admin login form now redirects to Ripiano's sign-in. `admin.site.has_permission` needs active staff **and** a session flag set only by Ripiano's sign-in after the code check. Tested: the admin form, `force_login`, and Ripiano sign-in. |
| MEDIUM | Key rotation or a bad key caused 500s and a lockout with no way back in. | Recovery codes are checked before decrypting. An unreadable secret gives "use a recovery code". `manage.py reset_two_factor <user>` turns 2FA off for one account. MultiFernet key rotation is documented. Tested. |
| MEDIUM | Anyone with the password could keep the owner locked out; password guessing was unthrottled. | Recovery codes work even while TOTP entry is locked. Sign-in is throttled per username (10 failures per 15 minutes) and per client address (30), using the Valkey cache shared across workers. nginx passes `X-Real-IP`. Tested (429). |
| MEDIUM | DNS rebinding between the webhook check and the connection. | The webhook connects to the vetted IP literal, with the original `Host` header and TLS SNI or certificate check for the name. IPv4-mapped, 6to4, and NAT64-embedded addresses are checked too. Tested. |
| MEDIUM | The webhook deadline did not cover slow headers, and the task had no time limit. | `send_workflow_notifications` has `soft_time_limit=40` and `time_limit=60`. |
| MEDIUM | "Updated" side effects repeated after a failed delivery, and there was a first-time race. | "First time" means no run of any status for that workflow and document, decided under a document row lock. |
| LOW | Slow TOTP brute force at 5 guesses per 15 minutes. | Partly addressed: sign-in throttling also counts wrong codes. Escalating locks remain open. |
| LOW | Recovery codes were unsalted SHA-256 over 48 bits. | Raised to 80-bit codes. A keyed hash is not used, so `SECRET_KEY` rotation cannot break recovery. |
| LOW | Password confirmations on the Security screen were unthrottled. | Open. The confirmation needs an authenticated session; recorded. |
| LOW | Other sessions survive enabling 2FA. | Open; recorded. |
| LOW | The pending secret never expires. | Open (it is encrypted and replaced on the next setup). |
| LOW | Scheduled scans grow over time. | Open; bounded per run by the keyset loop. A high-water mark is a follow-up. |
| LOW | The setup field truncated pasted codes. | Whitespace is stripped and up to 7 characters are allowed. |
| LOW | The sign-in code prompt was silent and stayed set after a username change. | A status message is announced; changing the username resets the prompt. |

## Verification

- `test_two_factor.py` and `test_workflows.py`: 10 passed. Full API suite: 130 passed, 6 skipped (zbar tests, which pass in the Linux image).
- Desktop browser journey `e2e/two-factor.spec.ts`, on its own disposable account: turn on with the QR secret, see 10 recovery codes, sign out, reject a wrong code, sign in with a recovery code, then turn off with another recovery code.

This scoped review is not the R4/9.5 release score.
