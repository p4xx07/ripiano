# Round 8 fixes — independent review

Scope: the uncommitted changes on `codex/initial-implementation`. That is the `git diff` plus the untracked files `migrations/0061_…`, `test_round8_fixes.py`, `StickerCamera.tsx`, `locales/StickerCamera.ts` and `e2e/judge-round8.spec.ts`. I checked them against the judge round 8 reports and DECISIONS D11. I only read the code and ran checks; I did not edit it. I ran:

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_round8_fixes.py archive/test_round7_fixes.py`: 18 passed, 1 skipped.
- `npx tsc --noEmit`: clean.
- A script that compares every server `{"error": "…"}` string, in English and Italian, with exact `toHaveText` / `toHaveAccessibleDescription` assertions in `apps/web/e2e`. It looks for messages that the new final period would break. The only hit is `judge-round7.spec.ts:99` "Sticker not found", which is a client-side message (`m.stickerNotFound`), so it is not affected.

I did not run Playwright, Docker, or the migration against a real database.

No high-severity findings.

## Medium

### M1. Migration 0061 marks salvaged PDFs ready but never files them; later reprocessing never runs "added" workflows or learned filing
`migrations/0061_…py:14-15` changes `status="failed"` to `ready` and sets `processed_at=timezone.now()`.

In rounds 6 and 7, the damaged-PDF branch of `process_document` saved the document and **returned before any filing step** (see `git show 2e97ca1:services/api/archive/tasks.py:141-148`). These documents therefore never went through any of the following (`tasks.py:179-206`):
- `apply_rules`
- date and sender detection
- `apply_learned_filing`
- `run_for_document(document, "added")`
- semantic-index queueing

The migration does not run them either. It also sets `processed_at`, and `first_run = document.processed_at is None` (`tasks.py:80`). So when the owner later chooses Retry OCR / Reprocess, the run is treated as a repeat: "added" workflows (tags, sharing, notes, webhooks, emails) and learned filing are skipped for good. New documents processed by the new code do get all of these steps, so migrated documents end up treated differently from new ones.

Scenario: Anna's "Bank statements" workflow tags and shares every new document from her bank. A damaged statement uploaded last week sat in Needs attention as failed. After the deploy it shows as Ready with "Check pages", with no tags, sender or sharing. Retry OCR does not apply the workflow either, because `processed_at` is already set.

Fix options:
- leave `processed_at` as NULL and set these rows to `status="pending"`, so `reconcile_pending_documents` reprocesses them through the normal path. The new path sets the warning itself. This costs one OCR run per affected document; on a NAS there should be only a handful;
- or at least leave `processed_at` NULL, so a manual reprocess still counts as the first run.

Add a migration test either way. There is none now.

### M2. A draft restored after sign-in puts back every field, not only the edited ones, so Save silently undoes changes made meanwhile on the server
`DocumentPanel.tsx:658-661` stores a full snapshot of every field: title, date, ASN, sender, type, storage path, action status, due date, action note and the complete tag list. `DocumentPanel.tsx:84-107` uses that snapshot as the initial state of **every** field. The document is loaded fresh in `reopenKeptDraft` (`App.tsx:1440`), but the fresh server values are overridden for fields the person never touched. Every field that changed on the server since then now looks "edited" against the new baseline. Save then PATCHes the old values back.

The draft can be hours or days old. It lives in sessionStorage for as long as the tab stays on the sign-in screen, and nothing checks its age or version.

Scenario:
1. Anna edits a title on the laptop, and her session expires.
2. On her phone she sets the sender of that document and adds the tag "Tax". Or a workflow, auto-filing, a page edit or OCR finishing changes it.
3. Back on the laptop she signs in. The dialog reopens with "Your unsaved edits were put back", and she presses Save.
4. The sender is cleared and "Tax" is removed. The tag list is sent as a whole list.

Fix: store only the dirty fields (compare against the last saved document when the snapshot is taken) and apply only those. Also store the document's `updated_at`/version. When the server copy changed, either show the server values with a "this document changed since" notice, or apply only the fields that did not change on both sides.

## Low

### L1. A kept draft stays readable on a shared device until someone else signs in, and an editor's draft is dropped without notice
- `App.tsx:1420-1428`, `1461`: when a session ends, the draft is written to `sessionStorage["ripiano.keptDraft"]`. It holds the title, the unsaved note text and the action note. Nothing clears it unless someone signs in in that tab (`reopenKeptDraft` clears it first, then checks the username, which is correct) or the tab is closed. A shared kiosk or family PC left on the sign-in screen keeps the text readable in devtools.
- The sign-in screen also shows the document's title to whoever is at the device (`m.sessionEndedDraft(open.title)`, `App.tsx:1466`). The session may have ended because of a password change (D11) or an account being turned off, so the next person at the device may not be the owner.
- Explicit sign-out does not create a draft (it does not go through `onSessionEnded`), which is correct.

Fix: add a "Discard" control next to the notice on the sign-in screen, and avoid the title in that notice (say "a document").

Separately, `App.tsx:1442` (`if (doc.access !== "owner") return;`) drops the draft of a person with **edit** access on a shared document without telling them. The sign-in notice had already promised the edits would come back. Either restore for `edit` access too, limited to `SHARED_EDIT_FIELDS`, or show `m.draftLost`.

### L2. Bundles revoked by a password change keep their ZIP on disk until the hourly expiry job
This is the same issue as round 7 L1, now also on a second path. `api_tokens.py:64` revokes bundles with a queryset `.update()` and does not call `remove_bundle_files` on commit, unlike the owner's own revoke (`bundle_views.py:183-186`). `people_views._end_access:148` still has the same gap. The ZIP is no longer served, so the issue is data at rest.

### L3. Page previews cached from the damaged original can keep showing after the switch to the searchable PDF
`versions.render_page` caches pages as `previews/…/v{version_number}-{n}.png` (`versions.py:84`). While a damaged document was `failed`, `page_source` used the **original** damaged PDF, and opening it cached Ghostscript renders of it. After the migration, or after reprocessing, `page_source` switches to the searchable PDF for these documents (`versions.py:43-48`), but `version_number` does not change. The old PNGs are therefore served next to a page count that may now differ (`page_info` reads the searchable PDF). The result can be blank or garbled pages, or page N showing a different page.

Fix: include the source (`original` or `searchable`) in the cache key, or clear `_preview_dir` when processing sets or clears `processing_warning`.

### L4. "Mark as checked" is offered to people the document is shared with, and the server refuses it with 403
`DocumentPanel.tsx:763-772` shows the button whenever `hasOpenWarning(current)`, whatever `current.access` is. `processing_warning_reviewed` is not in `SHARED_EDIT_FIELDS` (`views.py:44`), so a viewer gets "You can view this document but not change it". An editor gets "Only the owner can change archive details…".

The server behaves correctly: owner only, and agents cannot set it through MCP. Only the UI is misleading. Hide the button unless `current.access === "owner"`, and say in the text that the owner checks it.

### L5. Migration 0061 cannot be reversed without losing the "needs checking" state, and a failed reprocess keeps a stale warning
- The reverse operation is `RunPython.noop`, and the AddField reverses then drop both columns. After a rollback to 0060, salvaged PDFs stay `ready` with no flag and drop out of Needs attention without anyone checking them. A reverse function that turns `processing_warning="damaged_pdf"` rows back into `status="failed", error=DAMAGED` would make the rollback lossless.
- The failure branch of `tasks.py` (around line 160) does not clear `processing_warning`. A salvaged document whose reprocess then fails is `failed` with `processing_warning="damaged_pdf"` still set. Current UI and queries check `status` first, so nothing visible breaks. The stale value is still returned in the API and counted in Overview `warnings` (`stats_views.py:30` does not filter by status).

### L6. Test gaps
- `test_resaving_the_same_password_hash_keeps_share_links` only calls `anna.save()` without a new password. It never runs the actual hasher-upgrade path, `check_password` → `setter` → `set_password` + `save(update_fields=["password"])`. I confirmed in the installed Django (`base_user.py:106-110`) that the setter resets `_password = None`, so the code is correct. A test that changes `PASSWORD_HASHERS` and signs in would protect it.
- There is no test for the data migration (see M1).
- `ApiNotFoundMiddleware` is tested only for an unknown path and for a view's own JSON 404. A 405 on a real route, `/mcp`, and a trailing-slash path are untested. All three behave correctly by reading; see below.

## Checked and fine

**D11: every path that changes a password.** The `pre_save` signal (`apps.py:14`) covers:
- your own change (`security_views.py:161-162`);
- an admin reset in People (`people_views.py:201`, saved through `user.save(update_fields=fields)`);
- Django admin's password form and `manage.py changepassword`, both of which use `set_password` + `save`.

There is no email-based password reset. `reset_two_factor` and recovery-code sign-in do not change the password. Restore and loaddata produce `_password is None` and skip the signal.

The signal does not revoke anything in these cases:
- hasher upgrades, because Django's setter clears `_password`;
- plain saves;
- new users (`pk` is None).

If an admin sets a password and turns the account off in the same PATCH, the reason is `account_off`, because `_end_access` runs first. Revoked links still answer like unknown ones.

**Partly salvaged PDF.**
- The PATCH `processing_warning_reviewed` is accepted only from the owner or the owner's API token. `SHARED_EDIT_FIELDS` blocks shared users, and the MCP tools do not expose the field. It needs a boolean and a warning that is set.
- `page_source` uses the searchable PDF only when the document is `ready` with an `archive_path`. Page edits on such a document create a new version from the readable pages, and the old original stays as a version, so nothing is overwritten.
- The download, bundle and export endpoints gate the searchable file on `READY` and `archive_path` as before.
- The `warning` message is translated through `api_language`, because the `warning` key was added there.
- On reprocessing, the reviewed timestamp is kept when the warning is unchanged and cleared when it changes or goes away.

**MCP `denied` vs `error`.** The agent receives the same payload as before. Only the owner-side `AgentAudit.outcome` differs, and no MCP tool reads the audit log back. The document lookup is scoped to `grant.owner`, so another person's document still logs `error` and records no document.

**Workflow `skipped`.**
- A run is skipped only when every entry starts with "skipped ", "kept tag " or "could not share with ". Those prefixes are generated by the code, not by tag names.
- Webhook and email entries mean the run is not skipped, so notifications still go out.
- The failed-run counts (`stats_views.py:60`, `job_views.py:118`) still count only `FAILED`.
- The notification error path keeps `run.status`.

**`ApiNotFoundMiddleware`.**
- It sits inside `ApiLanguageMiddleware`, so "Not found" is translated, and inside `PrivateApiCacheMiddleware`, so `no-store` is still added.
- It sits outside `CommonMiddleware`, so APPEND_SLASH redirects (301) pass through. None of the routes end in a slash anyway.
- It changes only 404s, so 405s pass through.
- `/mcp` and `/admin/` are not under `/api/`.
- A view's own JSON 404 is left unchanged. A non-JSON 404 from a real route, such as `Http404` on a download, becomes JSON, which is an improvement.

**`asSentence`.**
- Only the `ApiError.message` gets the period. `result.error` stays raw in `ApiError.data`.
- `isPasswordRefusal` strips the period before comparing.
- `isCsrfFailure` uses `data.csrf_failed`, not the text.
- No other code compares error text, and no e2e exact match on a server message is broken (see the script above). Round 7 e2e was updated.

**UI.**
- **Unsaved-changes alert dialog:** the box is a direct child of the dialog panel, so every sibling is made inert and then restored. Tab is trapped in the capture phase, and Esc means "keep editing".
- **Inbox retry:** the error gets focus, and its Retry button retries that document's OCR and then focuses the row's button.
- **StickerCamera:** the stream is stopped in every case:
  - when a code is read;
  - when the dialog closes or unmounts (the effect cleanup);
  - when `getUserMedia` resolves after unmount (the `stopped` guard).

  `useMessages` returns a stable object, so the effect does not restart on every render. Scanned text goes through `stickerCodeFrom` and `encodeURIComponent`.
- **Agent log:** paging is client-side over the server's last 100 entries, and focus moves to the first new entry.
- **Revoked-reason labels:** they come only from owner-authenticated JSON.
- **Draft owner check:** another user's sign-in clears the draft before the username check.

## Resolution

| Finding | Resolution | Evidence |
| --- | --- | --- |
| M1 | Fixed: 0061 now sets old damaged-PDF failures back to `pending` with `processed_at` empty; `reconcile_pending_documents` queues them for the full first-run path. | `test_the_migration_requeues_old_damaged_pdf_failures_and_can_be_reversed`; 0061 unapplied and re-applied on the local stack |
| M2 | Fixed: the draft keeps only changed fields with the values they replaced (tags as added/removed); a field changed on the server meanwhile keeps the server value and is named in a notice; drafts expire after 24 h. | e2e "a kept draft puts back only what was edited…" |
| L1 | Fixed: an explicit sign-out clears the draft; the sign-in screen no longer names the document and offers "Discard them"; a shared-document draft that cannot reopen says so. | e2e "signing out explicitly leaves no kept draft…" |
| L2 | Fixed: a revoked bundle's ZIP is deleted at once (password change and account off). | `test_revoked_bundles_lose_their_zip_at_once` |
| L3 | Fixed: preview cache name includes the page source (`v{n}-{source}-{page}.png`). | `test_previews_of_a_salvaged_pdf_come_from_the_searchable_pdf_not_an_old_cache` |
| L4 | Fixed: "Mark as checked" shows only for the owner; others see "The owner marks it as checked." | judge-round8.spec.ts |
| L5 | Fixed: 0061 reverse `back_to_failed`; a failed reprocess clears the warning; warnings count only on `ready` documents. | `test_reprocessing_replaces_a_stale_warning` |
| L6 | Fixed: tests for 405, trailing slash and non-/api paths with the JSON 404; migration test added (calls the migration functions directly). | `test_the_json_404_leaves_other_answers_alone` |
