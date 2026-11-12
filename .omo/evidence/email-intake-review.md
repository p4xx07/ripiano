# Email intake review

An independent read-only reviewer covered code, security, and UX, and returned **REQUEST CHANGES**: no critical findings, 2 high, 4 medium, and 10 low. Every finding was addressed before the checkpoint, except where noted.

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | A malformed header (e.g. `From: =Z:Z; [")[><<:`), or any unexpected error, could stall a mailbox forever and leave its claim held. | Headers are read defensively, falling back to raw text. Each message is processed in isolation and recorded as `FAILED` on any error. `poll_account` releases its own claim in `finally` and sets a generic error. Tests cover the malformed header, an injected parser failure, and an unexpected connection error. |
| HIGH | Attachments inside `multipart/signed` (PEC/S-MIME), Apple Mail `multipart/alternative`, and forwarded `message/rfc822` parts were missed and marked done. | The whole MIME tree is walked. A test covers all three layouts. |
| MEDIUM | Inline logos and tracking images were imported. | Inline or Content-ID images are skipped by default. A per-rule "Also import pictures shown inside the email" option (`include_inline`) turns them on. Tested. |
| MEDIUM | The 200-message window was applied before removing handled messages, so a backlog was never reached. | Handled messages are removed first, then the oldest remaining are processed. A test runs a backlog across several polls. |
| MEDIUM | Passed-over messages were never reconsidered after a rule edit, and a mailbox change reused old records. | Changing the mailbox or folder clears the rule's records. Changing filters, inline handling, or age clears everything except imports. Tested; the UI says so. |
| MEDIUM | Filing was not atomic with document creation; a crash lost it; a phrase rule could later remove an email tag. | The document and its filing are written in one transaction, and OCR is queued with `on_commit(robust=True)`. When a message is seen again, missing filing and email origin are repaired. Tags that phrase rules had set to `RULE` are changed to `SOURCE`. Tested. |
| LOW | Distinct network errors allowed internal port probing. | All network failures share one message. Sign-in failure stays distinct, because people need it. Hosts on the local network stay allowed, because local IMAP is a supported use. |
| LOW | Unencrypted connections had no warning. | The UI shows a warning when security is "None". |
| LOW | Key rotation, invalid keys, OAuth wording. | `RIPIANO_MAIL_KEY` accepts a comma-separated list (MultiFernet: the first key encrypts, older keys still decrypt). An invalid key gives a clear message. Wording differs for password and OAuth accounts. |
| LOW | A PATCH could write back a stale rotated refresh token. | A PATCH saves only the fields it changes, and the secret only when a new one is entered. |
| LOW | Outlook `preferred_username` might be a UPN. | Accepted: the `email` claim is preferred and the scope requests it. |
| LOW | The OAuth redirect showed arbitrary text from the URL. | The callback sends fixed error codes, and the client maps them to fixed text. |
| LOW | Poll claims could expire mid-run and release another poll's claim. | Claims last 35 minutes, longer than the 30-minute task limit. A poll releases only its own claim. |
| LOW | Re-adding a mailbox caused duplicates. | The import key is now owner + Message-ID + attachment hash, independent of the mailbox. |
| LOW | Move/copy failures were silent, and folder names were shown raw in modified UTF-7. | Move and update status is checked and reported on the mailbox. Folder names are encoded and decoded (RFC 3501 modified UTF-7), with a round-trip test. |
| LOW | UI: Edit focus, focus lost on remove, test results not announced, no mailbox pause, rule order not editable, endless "Checking now…". | Edit scrolls to and focuses the form. Remove focuses the page heading, and the confirmation focuses "Keep". Test results go through the status/alert regions. Mailboxes can be paused and resumed. Order is editable. Waiting stops after 60 seconds with a "queued" note. |

## Verification after fixes

- `archive/test_mail.py`: 10 passed. Full API suite: 91 passed, 1 PostgreSQL-only skip. One earlier full run had a single unreported failure that did not reproduce in four consecutive reruns.
- Migration check is clean (one `0027_mail_intake` migration). TypeScript and the production build pass. The local, Portainer, and mail-test Compose files validate.
- Desktop and mobile browser journeys passed against a real local IMAP server (GreenMail, `deploy/compose.mailtest.yaml`). Each journey connects and tests a mailbox, adds a rule, sends matching and non-matching mail over SMTP, imports only the match with byte-identical originals, re-checks without duplicates, removes the mailbox, and shows the email origin on the kept document.

This scoped review is not the R4/9.5 release score.
