# Round 6 fixes — independent review

Scope: the uncommitted diff on `codex/initial-implementation`, plus the new untracked files: `test_round6_fixes.py`, `judge-round6.spec.ts`, and the `*-it.webmanifest` files. The review checks correctness and security. Every finding below was verified by reading the code. The PDF checks were also run against generated files.

Checks run:
- `pytest -q archive/test_round6_fixes.py archive/test_round5_fixes.py archive/test_trash.py`: 24 passed.
- `npx tsc --noEmit`: clean.
- Playwright and docker were not run, as instructed.

## Verdict

No high-severity issue was found. The agent guard on workflows is sound for the agent-visibility model. Agent visibility is decided only by `filter_tag` (see `mcp_server._documents`), and the guarded set is the same set the MCP tool refuses. Workflow actions touch only the edited document. Workflows do not recurse: `run_for_document` is called once per change, and `_apply` never calls it. The bulk and MCP runs happen after their `transaction.atomic()` blocks commit.

The findings are one medium gateway regression, two medium client problems with the unsaved-changes work, and several lows.

## Findings

### M1 — Italian PWA manifests are behind Authelia on the Pi gateway
- **Where:** `deploy/gateway/traefik/dynamic/routes.yml:40` (not changed), together with `apps/web/src/i18n.ts:43-49` and `apps/web/src/theme.ts:24-26`.
- **Problem:** The `ripiano-direct-public` router lets only `/manifest.webmanifest`, `/manifest-dark.webmanifest` and `/manifest-amoled.webmanifest` bypass forward-auth. The comment there says browsers fetch manifests without cookies. The new `/manifest-it.webmanifest`, `/manifest-dark-it.webmanifest` and `/manifest-amoled-it.webmanifest` go through the `ripiano` router with the `authelia` middleware.
- **Failure scenario:** An Italian user opens Ripiano through the gateway. `<link rel="manifest">` now points at `-it.webmanifest`. The browser's credential-less fetch is redirected to the Authelia login page (HTML). The manifest fails to parse, so "Install app" or "Add to Home screen" stops working, or installs without a name or icons. English users are unaffected. This is the same problem the route comment was written to prevent.
- **Fix:** Add the three `-it` paths to the router. A simpler option is a single `PathRegexp(`^/manifest(-[a-z]+)*\.webmanifest$`)`.

### M2 — Accepting a suggestion can trigger workflows, and the panel then nags falsely and Save reverts the workflow's changes
- **Where:** `apps/web/src/DocumentPanel.tsx:515-534` (`acceptSuggestion`), `:547-559` (`dirty`), `:297-303` (`save`). The server side is `services/api/archive/views.py:1113-1118`.
- **Problem:** The suggestion PATCH sends `correspondent_id`, `document_type_id` or `add_tag_id`. Because the owner made the change, the server runs "updated" workflows (`run_for_document`). Those workflows can change the title (template), storage path, `action_status` and `action_note`. `acceptSuggestion` then calls `setCurrent(updated)` but re-syncs only tags, sender and type. It does not use the new `adopt()`, which exists for exactly this case.
- **Failure scenario:** The owner has a workflow "Acme follow-up" (updated, filter sender = Acme, `set_needs_action`). They open a document and click the suggestion "Set sender Acme" without editing anything else.
  - `current.action_status` becomes `open` while the draft stays `none`, so `dirty` is true. Closing the panel shows "Unsaved changes", although the user changed nothing.
  - If they press Save, `save()` always sends `action_status: "none"`, the stale `title` and the stale `storage_path_id`. That clears the follow-up the workflow just opened and reverts the title or storage path.
- **Fix:** Replace the hand-written sync in `acceptSuggestion` with `adopt(updated)`. `adopt()` already merges the tags the same way.

### M3 — The unsaved-changes guard is bypassed by in-panel navigation and by browser Back
- **Where:**
  - `apps/web/src/DocumentPanel.tsx:605`, `:611` and the `DocumentLinks` `onOpenDocument` call (`onOpenDuplicate`).
  - `:775` (`onOpenTags`) and `:968` (`onOpenLocations`).
  - `apps/web/src/App.tsx:796-801` (popstate handler), `:2486-2497`.
- **Problem:** Only the close button, Esc and the backdrop go through `requestClose`. These other routes skip it:
  - "Exact copy of …", "Part of a split scan" and linked documents call `onOpenDuplicate`, which calls `setSelectedDocument(other)`. The panel is `key={selectedDocument.id}`, so it remounts and the drafts are gone.
  - "Manage locations" and the first-tag "Create tag" link call `setSelectedDocument(null)` directly.
  - Browser or Android Back runs the popstate handler, which calls `setSelectedDocument(null)`.
- **Failure scenario:** A user edits the title and tags, then clicks "Manage locations" to add a shelf before choosing it. The panel closes and the edits are lost, with no prompt. The same happens on the phone when the user presses Back.
- **Fix:** Route these actions through the same confirm step. One option is for `requestClose` to accept a continuation. For popstate, at least re-push the entry while `dirty`.

### L1 — Agent calls that change nothing still run every "updated" workflow
- **Where:** `services/api/archive/mcp_server.py:236-281` and `:311`.
- **Problem:** `change_document_tags` accepts `add: [], remove: []`, and `set_document_filing` accepts the value already set. Both still call `_run_updated_workflows`. "updated" runs have no uniqueness constraint (`models.py:759`, `condition=~Q(trigger="updated")`).
- **Failure scenario:** An agent loops a no-op call. Each call adds `WorkflowRun` and `DocumentEvent` rows, which grows the database on the NAS. Each call also re-applies `_share`. If the owner had removed a person's access that an "updated" workflow grants, the agent's no-op call shares the document with that person again. TagOverride protects tags against this; nothing protects sharing.
- **Fix:** Run the workflows only when the history snapshot actually changed, or when `add - suppressed` or `remove` is non-empty, or when the filing value differs.

### L2 — Bulk edits run every workflow synchronously in the request, even when nothing changed
- **Where:** `services/api/archive/views.py:666-672`, `:736`, `:779`, `:854`; `services/api/archive/workflows.py:342-346`.
- **Problem:** Up to 100 documents times W workflows run in the HTTP request. Each run does `refresh_from_db`, `select_for_update`, `exists`, `WorkflowRun.create`, a history snapshot and record, and `_apply`. The `Workflow` query and its two prefetches are also re-run for every document, because `run_for_document` is called per document. Unlike the single-document PATCH (`views.py:1116`), bulk paths do not check whether anything changed. Bulk-adding a tag the documents already have still runs all workflows on all of them.
- **Failure scenario:** 100 documents with about 10 "updated" workflows means thousands of queries in one request on the Synology. That risks a gunicorn or proxy timeout after the bulk change has already committed. The user sees an error for a change that succeeded. AGENTS.md asks that load like this be reported to the owner.
- **Fix:** Fetch the workflows once. Pass only the documents that actually changed. Consider a Celery task for large batches.

### L3 — Damaged-PDF check: unexpected pypdf exceptions turn successful OCR into a generic failure, and the comment about encrypted PDFs is wrong
- **Where:** `services/api/archive/tasks.py:42-53` and `:129-147`.
- **What works:** No false positives on valid files. I ran `pdf_is_damaged` on generated files: a clean 3-page PDF, trailing garbage after `%%EOF`, a wrong `startxref`, owner-password-only encryption, and an embedded file attachment. All returned False. pypdf in non-strict mode rebuilds the xref; the docstring says it "does not rebuild broken files", which is inaccurate but harmless. ocrmypdf keeps the page count, and barcode splitting (`_split`) does not change the input file.
- **Problem 1:** Only `PyPdfError`, `OSError`, `ValueError`, `KeyError`, `TypeError` and `AttributeError` are caught. Other parser errors raised by malformed PDFs, such as `IndexError`, `RecursionError`, `zlib.error` or `struct.error`, propagate into `process_document`'s outer `except`. That branch marks the document FAILED with the generic message, and the OCR output is never moved into place, because `os.replace` runs after the check. Before this change such a document became READY.
- **Problem 2:** The inline comment says "A password-protected original was checked through its unlocked copy." No such check exists. When `unlocked_by` is set, `damaged` is always False, so a truncated encrypted PDF still goes READY silently.
- **Fix:** Catch `Exception` inside `pdf_is_damaged` and treat it as damaged. Either check the unlocked copy or correct the comment.

### L4 — A damaged PDF stays FAILED permanently and skips the rest of the pipeline
- **Where:** `services/api/archive/tasks.py:138-145`.
- **Problem:** The early `return` comes before `processed_at` is set. So `first_run` stays True forever. `apply_rules`, date and sender detection, learned filing, "added" workflows and semantic indexing never run for the readable pages. Retry OCR re-runs into the same state, and there is no way for the owner to accept the file as it is.
- **Failure scenario:** An "added" workflow that shares new documents with a spouse, or tags them, never applies to a slightly damaged bank statement, even after the owner has looked at it. If barcodes are on, every retry is still treated as a first run for splitting purposes. `_split` refuses a second split, so the damage is limited.
- **Fix:** Set the status and error, then continue with the normal filing steps, or set `processed_at`. Alternatively, provide an "Accept as is" action.

### L5 — The "follow server for untouched fields" fix misses auto-filing that finishes after READY
- **Where:** `apps/web/src/DocumentPanel.tsx:185-198` (the poll stops at ready or failed), `:297-303` (`save` always sends `title`, `document_date`, `action_status`, `action_due_date` and `action_note`); `services/api/archive/tasks.py:147-186`.
- **Problem:** `process_document` saves READY first, then runs rules, date detection, learned filing and "added" workflows. The poll adopts the READY snapshot and stops.
- **Failure scenario:** On a slow NAS, the poll sees READY before `apply_document_details` sets the date. The panel keeps `date = ""`. When the user later saves, `document_date: null` is sent and overwrites the detected date. This race existed before the change, but the new comment claims it is fixed.
- **Fix:** Send only fields that differ from `current`, the way `save` already does for sender, type, storage path and ASN. Or poll once more after READY.

### L6 — CSRF failure view also answers non-API pages in JSON
- **Where:** `services/api/ripiano/settings.py:97-98`, `services/api/archive/security_views.py:17-19`.
- **Problem:** `CSRF_FAILURE_VIEW` is global. `/admin/` is mounted (`ripiano/urls.py:145`), so an admin form post with an expired token now gets a raw `{"error": …}` JSON body instead of Django's page. This is cosmetic.
- **Fix:** If the path does not start with `/api/`, fall back to `django.views.csrf.csrf_failure`.

## Checked and fine

- **Agent-triggered workflows:**
  - Revoked grants are excluded from the guard and expired ones are kept, which is the conservative choice.
  - The agent's own filter tag is not guarded. Removing it can only narrow its own view, and adding it to a document the agent can already see is a no-op.
  - Sharing (`_share`) goes to people or groups and does not affect any agent's view. `_documents` filters on `owner=grant.owner`.
  - Error returns inside `set_document_filing`'s `atomic` block skip the workflow run correctly.
- **`_existing_scan`:**
  - `original_sha256` is the hash of the raw upload bytes (`storage.save_original`), so a byte-identical retry still gets 200, and older versions' hashes are accepted.
  - Re-reading `upload.chunks()` after `ingest_document`, in the IntegrityError path, works because `File.chunks()` seeks back to 0.
  - The web queue treats 409 as a refusal (`uploadQueue.isRefusal`). Android uses one UUID per stored file, so it cannot hit the "different file" case.
- **File-name search:** `original_name__icontains` is added to both the full-text and plain branches and stays scoped to the same queryset. There is no new data exposure.
- **`download_name`:** Stored extensions are `.pdf`, `.jpg`, `.png`, and the office, eml and msg extensions. `.jpeg` and `.jpg` are treated as equal. A name without an extension gets the detected one. It is applied consistently to the original, share-link and version downloads.
- **Cache-Control:** It is now on every `/api/` response without its own header. Share downloads (`no-store`) and previews (`private, max-age`) keep their own policy.
- **Agent events `.only(...)` with `select_related`:** Tests pass. The document title shown is always the owner's own document (`_call` filters on `owner=grant.owner`).
- **`Button pending`:** Clicks are blocked with `preventDefault` before `onClick`. That also cancels implicit (Enter) form submission, which fires a click on the default button. Every handler wired to a pending button or an `aria-disabled` raw button also has its own `if (busy) return` (or `notesBusy`), so double submission is blocked twice. The styling covers `.button`, suggestion, copy and note buttons.
- **Paper-copy move:** It sends exactly what the select shows. The "already there" case makes no request. The choice is cleared after a successful move.
- **`adopt()`:** It uses a ref and functional setters only, so the stale closure in the polling interval is safe. The tag merge keeps the user's additions and removals.
- **Manifests:** The `-it` files match the English ones apart from the name and description fields. `theme.ts` and `i18n.ts` reach the same `href` whichever runs first. See M1 for the gateway problem.

## Resolution (before commit)

| Finding | Outcome |
|---|---|
| M1 Italian manifests behind Authelia | Fixed: `deploy/gateway/traefik/dynamic/routes.yml` matches `^/manifest(-dark\|-amoled)?(-it)?\.webmanifest$`. |
| M2 accepting a suggestion: false prompt, Save undoes workflow | Fixed: `acceptSuggestion` uses `adopt()`; the accepted sender/type is then set explicitly. |
| M3 other exits lose edits | Fixed: linked/duplicate/split/similar documents, "Manage locations" and the tag link go through the same ask-first step; Back returns to the document and asks (`documentLeaveGuard`, e2e `Back with unsaved edits…`). |
| L1 no-op agent calls run workflows | Fixed: workflows run only when `history.record` saw a change (agent and bulk paths). Test `test_changes_that_change_nothing_run_no_workflows`. |
| L2 bulk load | Mitigated: workflows loaded once per request, skipped when the owner has none, only for documents that changed. Still synchronous per request (≤100 documents). |
| L3 unexpected parser errors / wrong comment | Fixed: unexpected errors log and keep the OCR result; comment corrected. |
| L4 damaged PDFs stay failed | Open: needs an "accept as is" action (product decision). |
| L5 late auto-filing vs Save | Open (low). |
| L6 JSON CSRF on admin | Fixed: JSON only for `/api/` and `/mcp`. |
