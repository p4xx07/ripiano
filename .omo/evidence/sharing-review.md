# Share bundles and document email review

An independent read-only reviewer covered code, security, and UX, and returned **REQUEST CHANGES**: no critical findings, 2 high, 4 medium, and 10 low. It confirmed the following match the single-document share links:
- token format and hashing;
- the same 404 for every failure;
- no-store, no-referrer, and nosniff headers;
- no route collision between bundle IDs and tokens;
- owner isolation;
- email header-injection safety.

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | Every anonymous download rebuilt the ZIP synchronously, which could block the 4 API threads and fill `/tmp`. | The ZIP is built **once** on the maintenance queue (`build_share_bundle`) under `media/bundles/`, verified in a single pass, and served as a file with a row-locked status check. A download while it is building returns 503 with `Retry-After`. The ZIP is deleted when the link is revoked or expires (hourly task), and backups skip `bundles/`. The size cap is lowered to 200 MB. |
| HIGH | Restoring a document from Trash re-shared it through live bundles. | Trash (single and bulk) and new versions revoke every bundle containing the document. Restoring never re-shares. Tested: trash, restore, 404. |
| MEDIUM | A revoke, Trash, or new version during a download did not stop it. | Bundles are immutable. Revoke and download both lock the bundle row. A revoke during the build discards the result. |
| MEDIUM | The bytes that were verified were not the bytes that were zipped. | Each original is hashed and size-checked while it is copied into the ZIP entry. A mismatch marks the bundle failed. Tested. |
| MEDIUM | Document email was enabled by any SMTP setup, a spam-relay risk. | Separate opt-in `RIPIANO_DOCUMENT_EMAIL=1` (off by default). The limit counts recipients (30 per hour), `reply_to` is the owner's address, and API tokens cannot mint agent grants. Tested. |
| MEDIUM | Rate-limit race, stuck queued sends, endless polling. | The limit is checked under a user-row lock. Queued sends older than 15 minutes are closed as failed. SMTP and OS errors retry 3 times with backoff. The UI stops polling after about a minute. |
| LOW | The email task skipped path validation, the checksum check, and the Trash check. | It uses `_media_path`, verifies the original's SHA-256, and does not send trashed documents. Tested. |
| LOW | Recipient overflow and a missing searchable PDF caused 500s. | Recipients are stored as `TextField` with a 1,000-character input cap and de-duplicated. A missing archive returns 409. |
| LOW | Lost download counts. | `F("downloads") + 1` under the row lock. |
| LOW | ZIP entry names. | NFC-normalised, stem capped at 150 characters, suffix sanitised, case-insensitive de-duplication. |
| LOW | Split sources leaking. | The build excludes `is_split_source`. |
| LOW | README size contradiction. | Corrected to 200 MB. |
| LOW | What the email reveals. | A hint before sending says the subject, sender, and reply address. |
| LOW | Bundle panel UX. | The old link clears when the selection changes, the >50 limit is explained, each bundle lists its documents, and errors clear on revoke. |
| LOW | Test gaps. | Added tests for version and trash revocation, restore not re-sharing, tampered originals, stale sends, the per-recipient limit, and the opt-in. |

## Verification

- `test_bundles.py` (3 tests), `test_versions.py`, and `test_api_tokens.py` pass, and so does the full API suite.
- The desktop and mobile journey `e2e/sharing.spec.ts` covers:
  - selecting two documents and creating a bundle;
  - an anonymous ZIP download once the bundle is ready;
  - revoking it, after which it returns 404;
  - emailing a document through the local GreenMail SMTP, with "Sent" shown in the history.

This scoped review is not the R4/9.5 release score.
