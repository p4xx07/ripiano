# Workflows review

An independent read-only reviewer covered code, security, and UX, and returned **REQUEST CHANGES**: no critical findings, 2 high, 3 medium, and 9 low. It confirmed that savepoint and `on_commit` handling are correct inside the PATCH view's transaction, that owner scoping is consistent, that payloads carry metadata only, and that manual sender and type choices are preserved.

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | Webhook SSRF to internal hosts, and slow or large responses stalling the single maintenance worker. | The host is resolved before each call, and private, loopback, link-local, or other non-global addresses are refused unless `RIPIANO_WEBHOOK_ALLOW_PRIVATE=1`. Redirects are off, proxy environment variables are ignored, the per-phase timeout is 5 s with a 15 s overall deadline, and at most 64 KB of the response is read. Hostnames are IDNA-validated when saved. Tested. DNS rebinding between check and connect remains a narrow residual risk. |
| HIGH | "Updated" workflows reopened a follow-up the owner marked done. | `set_needs_action` only starts a follow-up when none exists; it never reopens one. "Updated" fires only after title, date, sender, type, or tag changes. Tested. |
| MEDIUM | Scheduled runs re-read the same 500 candidates, and new workflows backfilled all history. | `~Exists` subquery, keyset pagination until 500 apply, and only documents that become due after the workflow was created. Tested. |
| MEDIUM | "Updated" repeated notes, webhooks, and emails on every edit. | Notes, webhooks, and emails happen only on the first applied run per workflow and document. Tested. |
| MEDIUM | A non-HTTP error (such as an over-long host label) crashed notifications and left the run marked "applied". | Each channel catches all errors, payload preparation is guarded, and the run is always finalised. Tested with `UnicodeEncodeError`. |
| LOW | Attachment silently dropped; hard-coded 10 MB in the UI. | The run says "sent without the file (over N MB)" or "(could not be read)"; the UI wording is generic. |
| LOW | Newlines in the title broke the email subject. | Whitespace in the subject is collapsed. |
| LOW | An `IntegrityError` inside actions was reported as "already ran". | Only the run-insert savepoint maps `IntegrityError` to "already ran"; other errors record a failed run. |
| LOW | Misleading failure text. | Reworded: "could not be applied to this document; will not retry automatically". |
| LOW | `filter_sources` with non-strings returned 500. | Type-checked, returns 400. Tested. |
| LOW | The `?document=` deep link was not validated. | Only UUIDs are used, and other query parameters and the hash are kept. |
| LOW | Negative days unexplained. | The label says "Negative means before". |
| LOW | Run-now records trigger `updated`. | Accepted: run-now is an explicit manual action, and side effects still happen only once per document. |
| LOW | `processed_at` is committed before "added" workflows run. | Open: a worker crash in that window skips "added" workflows for that document. Recorded as residual. |

## Verification

- `test_workflows.py` (7 tests) passes, and so does the full API suite.
- Desktop and mobile browser journeys pass: create a workflow from a recipe, upload matching and non-matching documents, see the tag with origin `source` on the match only, find the run in Recent runs, and open the document from the run.
- The full browser suite passed before the review fixes (74 passed, 4 admin-only failures). A post-fix suite was run before commit.

This scoped review is not the R4/9.5 release score.
