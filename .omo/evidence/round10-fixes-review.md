# Round 10 fixes — independent review

Scope: the uncommitted changes on `codex/initial-implementation` after `255f81d`. That is `git diff HEAD` plus the untracked files `archive/password_rules.py`, `archive/test_round10_fixes.py` and `e2e/judge-round10.spec.ts`. I checked them against judge 2 and judge 3 round 10 reports. I only read the code and ran checks; I did not edit source, commit, or touch Docker. I ran:

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_round10_fixes.py`: 15 passed.
- `npx tsc --noEmit -p .` in `apps/web`: clean.

I did not run Playwright, Docker, a real PostgreSQL outage, a real backup next to a running worker, or a real restore. I read `e2e/judge-round10.spec.ts`, `style.css` and the locale files only in passing. Line numbers are those of the working tree at review time.

No high-severity findings. 3 Medium, 9 Low.

## Medium

### M1. The agent guard only covers the run the agent's own call starts; a scheduled workflow, or the owner's next unrelated edit, still discloses the document because of the agent's tag
`workflows.py:303-310` (`by_agent`), `workflows.py:331-349` (`run_workflow`), `workflows.py:415` (`run_scheduled`), `views.py:776` and `views.py:1244` (owner's bulk and single edits), `mcp_server.py:194-204`.

`by_agent` is true only when `run_for_document` is called from the two MCP write tools. What an agent changes stays on the document (the tag with origin `model`, or a sender/type with origin `model`), and every later run that matches because of it is unguarded:

1. **Scheduled workflows.** `run_scheduled` calls `run_workflow(workflow, document, SCHEDULED)` with no `agent_grant`. `matches()` uses the same tag, sender and type filters. Scenario: Anna has a scheduled workflow "tag *Commercialista*, 0 days after added → share with Luca, email the accountant". An agent limited to "Add or remove tags" adds *Commercialista* to a private document. The agent-started "updated" runs hold back nothing here (the workflow is scheduled, not "updated"), and the next daily pass shares the document, sends the email and calls the webhook. It is a first run for that workflow, so `first_time` is true and all three fire. This is judge 3 M1 with up to a day of delay.
2. **The owner's next edit.** "Updated" workflows may run on every change (`models.py:791`). Scenario: the agent adds *Condividi con Luca*; the run records "skipped sharing (an agent made the change…)". Next week Anna fixes a typo in the title of that document, or runs a bulk tag change over 50 documents that include it. `run_for_document(document, UPDATED)` runs without `agent_grant`, the workflow still matches on the agent's tag, and `_share` shares the document with Luca. Anna never looked at the tag.

Case 2 is not what the documents say. `docs/AGENT_ACCESS.md` says "Nothing is sent later by itself: if you do want that document shared or sent, do it yourself from the document", and D12 says "Held-back actions are not sent later". Neither says that any later edit of the document by the owner completes the held-back share.

Not affected: workflows on "added" (agents cannot upload; there is no MCP tool that creates a document), "Run now" (an explicit choice by the owner), and the same-call chain (workflows run in order with the same `agent_grant`, and workflow changes never start further workflows).

Fix (smallest that closes both): decide from the document, not from the caller. In `_apply`, hold back share, webhook and email when the workflow's own filter is satisfied only by something an agent set and no person confirmed: `filter_tag` matched by a `DocumentTag` with origin `model`, or `filter_correspondent` / `filter_document_type` matched while the document's `*_origin` is `model`. A person re-adding the tag or re-choosing the sender makes the origin `manual` and releases it. Keep `by_agent` as it is for the direct case. If that is more than wanted now: pass a guard into `run_scheduled` the same way, and state in D12 and AGENT_ACCESS.md that the owner's later edit of the document does share it. Add tests for the scheduled run and for an owner edit after an agent-started run.

### M2. A run held back for an agent uses up the workflow's one-time webhook and email for that document, so the owner's own later change never sends them, while sharing does go through
`workflows.py:337` (`first_time`), `workflows.py:307-312`.

`first_time` is "no `WorkflowRun` exists for this workflow and document". The agent-started run is recorded (status `skipped` or `applied`), so every later run has `first_time = False`, and "queued webhook" / "queued email" are never appended again.

Scenario: Anna's workflow is "when updated, tag *Da pagare* → email me, add a follow-up". Her tagging agent, which is what agents are mainly for, adds *Da pagare*. The follow-up is set, the email is held back. Anna later opens the document and changes its date: the workflow runs again, and still no email, for this document, ever. Before this change the agent's tag sent the email. `docs/AGENT_ACCESS.md` says "The same workflow started by your own change … shares and notifies as usual", which is not true for a document an agent touched first.

The result is also uneven: after the owner's later edit the document is shared (M1, case 2) but the notification is not sent.

Any agent with tag permission can therefore silence a notification workflow for the documents it can see. The run history records it, but nothing brings it to the owner's attention.

Fix: do not let a held-back run count as the first. For example compute `first_time` from runs whose detail does not contain `HELD_WEBHOOK` / `HELD_EMAIL`, or store a `notified` flag on the run and test `not WorkflowRun.objects.filter(…, notified=True).exists()`. Decide it together with M1 (the first later run that is allowed to disclose should also be the one that notifies). Surface held-back runs to the owner (Overview / Needs attention), since D12 expects the owner to act by hand. Test: agent run, then owner edit, expects exactly one "queued email".

### M3. After the 20 s client limit the app says "try again", but the server usually finishes the request; every create is then done twice, starting with the note that Save now posts
`apps/web/src/api.ts:366-373`, `383`, `390`; `DocumentPanel.tsx:481-496`; `SharedDocumentPanel.tsx:135-150`; `views.py:1331`.

Aborting `fetch` does not stop the request on the server (gunicorn `--threads 2 --timeout 60` runs it to the end). No create endpoint has an idempotency key; the only one in the codebase is `X-Ripiano-Scan-ID` for scan uploads. The limit is reached when the server is slow rather than gone: NAS disks waking from hibernation, the database busy during OCR or a backup, a `.delay()` waiting for an unreachable queue server, a row lock held by a barcode split.

Scenario (the note): Anna types a note, changes the title and presses Save. The note POST takes 25 s because the disks were asleep. At 20 s the dialog shows "Ripiano can't be reached right now. Your changes are still here; try again." The note was stored. The draft is still in the field (`setNoteDraft("")` only runs after a successful answer), so the second Save posts it again: two identical notes. The same happens through "Save changes" in the unsaved-changes question and in the shared-document dialog.

The same double submit, by route (all outside `SLOW_MUTATIONS`, so 20 s):
- `POST /api/workflows`: two identical workflows. Each then runs, so actions, emails and webhooks happen twice. This is the one with outside effects.
- `POST /api/documents/<id>/shares`: a second public link; the first one stays active and is listed although its link was never shown.
- `POST /api/agents`: two grants; the first token was never shown.
- `POST /api/backups`: two full backups, one after the other.
- `POST /api/share-bundles`, `/api/documents/<id>/links`, `/api/documents/<id>/copies`, `/api/locations`, `/api/saved-views`, `/api/filing-rules`, `/api/custom-fields`: duplicates, or a confusing "already exists" where names are unique (`/api/people`, `/api/tags`, `/api/groups`).

Not affected: `PATCH` and `DELETE` (repeating them is harmless; a repeated document PATCH with the old `base_version` gets a 409 whose merge finds the same values and saves nothing new), and `FormData` uploads (no limit).

Minimal fix for the note, no migration: `document_notes` already holds the document's row lock on POST (`views.py:1313`). Before `DocumentNote.objects.create`, look at this author's newest note on the document; if its body is identical and it is younger than about two minutes, return it instead of creating another. On the client, after a timed-out note POST call `loadNotes(0)` so the stored note is visible before the person retries.

General fix: send a client-generated key (`Idempotency-Key: crypto.randomUUID()`, created once per form submission and reused on retry) on create POSTs, and have the server keep `(user, key) → response` in the cache for a few minutes. Until then, the time-out message for a POST should not say "try again" unconditionally; "check whether it was saved before trying again" is the honest wording, and the affected lists should reload after a time-out.

## Low

### L1. A cancelled run can still write: barcode tags, the ASN and notes, and the archive file
`tasks.py:834-860` (`apply_barcodes` after a refused split), `tasks.py:278-281`.

- `_split` now checks the claim, but when it returns `False` `apply_barcodes` continues: it adds barcode tags (`get_or_create`), sets the ASN (`update(asn=…)`) and writes notes with no claim check. Cancel during the barcode scan of a batch, and the unsplit source gets the tags of every sheet in the batch. The docstring of `cancel_document_processing` says the run can no longer "file anything".
- `_holds_claim` (line 278) and `os.replace` (line 281) are not under the row lock. A Cancel between the two leaves the document "cancelled" with a new archive file. With the new Cancel → Trash → permanent deletion path (possible now that a processing document can be cancelled), a replace that lands after the purge leaves `archive/<id>.pdf` of a deleted document on disk and in every later backup. The window is microseconds.

Fix: return from `apply_barcodes` when the claim is gone, and do the `os.replace` inside the transaction of `_save_result` (after the claim check, under the lock).

### L2. A snapshot can hold files its own database dump does not know, and a restore keeps them for good
`backup.py:223-225` (dump, then copy).

The dump is taken first, so the dump never refers to a file that is missing (good). The other direction is possible: a document that finishes during the copy leaves its `archive/<id>.pdf` in the snapshot while the dump says "processing", and a barcode split that commits during the copy leaves its part files in `originals/` with no rows. After a restore the source is processed again and split again into new parts with new file names (no duplicate documents: checked). The first set of part files stays in the media volume, is copied into every later snapshot (`originals/…` is a valid path), and is not removed by a permanent deletion of the documents, because no row points to it.

Fix: at the end of a restore (or as a maintenance task) remove files under `originals/` and `archive/` that no `Document`/`DocumentVersion` row uses, or write only files the dump can refer to. `docs/BACKUP_RESTORE.md` should mention it until then.

### L3. A media file that disappears during the copy is now skipped silently, whatever it was
`backup.py:170-176`. Before, a vanished file failed the backup (`FileNotFoundError`). Now the snapshot completes without it. I checked every deletion in the code: outside the backup lock only files of uncommitted documents are removed (`ingestion.py:39`, `mail.py:327-331`, `versions.py:136,272-276`, `tasks.py:397,802`), so Ripiano itself cannot cause this. A file removed by something else (a person on the NAS share, a failing disk) in the seconds between listing and copying is no longer reported. Cheap check: after the copy, if any file was skipped, fail unless `Document`/`DocumentVersion` has no row with that path.

### L4. `_remove_split_leftovers` only looks at `Document.original_path`
`tasks.py:395`. A part that was given a new version keeps its first file in `DocumentVersion.original_path`. If the journal of the run that created it is still there (the run was killed after the split committed and its folder waits for the stall detection), the cleanup deletes that file. `purge.py:37` checks both tables; this should too. The window is short and needs a version upload within minutes of a worker crash.

### L5. Password rules: no upper length limit, and the new person's name is not compared
`password_rules.py:26-38`, `72-75`; `people_views.py:107-108`.

- `_longest_run` is a Python loop over every start position for 12 sequences. A 2 MB "password" made of `abc…z` repeated (the body limit is 2.5 MB) keeps a gunicorn worker busy for longer than its 60 s limit. It needs a signed-in person who knows their current password, an admin, or the setup key, so it is a nuisance among family accounts, not an outside attack. Refuse more than, say, 256 characters before running any validator.
- People → add person validates against `User(username=…)` only, so `first_name` from the same request is not part of the similarity check ("Annamaria-Rossi" for Annamaria Rossi passes). Set `candidate.first_name` before the check.

Consistency otherwise holds (see "checked and fine").

### L6. Every `OperationalError` is reported as "can't reach its database"
`cache_headers.py:16-18`. `OperationalError` also covers a deadlock, a lock or statement timeout, a full disk and "too many connections". Those now answer 503 with `Retry-After: 5` and the "try again in a moment" sentence. For a full disk that advice is wrong and hides the cause from the person (the log still has it). Narrowing to connection failures (`connection.is_usable()` is false, or SQLSTATE class 08 / 57P) would keep the 500 sentence for the rest.

Related: outside `/api/` the DEBUG error page is unchanged (`/admin/`, `/healthz`, `/livez`). The quickstart runs with `RIPIANO_DEBUG=1` and nginx forwards those three paths.

### L7. Web: small gaps around the new Save flow
- `DocumentPanel.tsx:1207`: "Add note" stays enabled while Save is posting the same draft (`busy` is true, `notesBusy` is not). A click there posts the note a second time.
- `DocumentPanel.tsx:481-520`: the note is stored before the details. When the details are then refused (ASN already in use, a clash that needs a choice), the dialog shows the error and "Note added" together; the comment only describes the other direction. Acceptable, but the person should not be told "nothing was saved" anywhere.
- `App.tsx:2029`: a retried document that is not in the current list (another filter, another page) keeps its entry in `retriedOcr` and is announced whenever it next appears, possibly much later.
- `api.ts:376`: `isTimeout` is exported and never used.

### L8. Documentation left behind
- `docs/USER_GUIDE.md:453` still ends with "files left behind by a stopped run are removed after two hours"; `docs/BACKUP_RESTORE.md` and the code now say minutes.
- `docs/USER_GUIDE.md:452` says Cancel discards "whatever the worker was doing". With one worker (`--concurrency=1`) the worker stays on the cancelled file until its OCR step ends (up to 55 minutes), so a Retry or the next upload waits behind it. The docstring says so; the guide should.
- `job_views.py:160-165` says the cancelled run's temporary files "are removed within a minute". `reconcile_pending_documents` (which calls `remove_stale_work_dirs`) is not routed to the maintenance queue (`settings.py` routes, `celery.py:29-32`), so in the default stack it waits in the same one-at-a-time queue as the OCR it would clean up after. The folder is in practice removed when that run ends, by its own `finally`. Nothing is lost and backups skip the folder either way; the sentence is wrong, or the task should be routed to `maintenance` (the stall detection would then also keep running during a long OCR).

### L9. Test gaps
- No test for M1 (scheduled run, owner edit after an agent-started run) or M2.
- No test that a Cancel between the claim check and the save discards the result, or that a cancelled run adds no barcode tags (L1).
- The mid-copy test replaces the file by writing in place; nothing tests a file that keeps changing (`COPY_ATTEMPTS` exhausted → "Media changed during backup").
- No test for a create POST that times out on the client and succeeds on the server (M3).
- The restore test patches `_requeue_interrupted_processing`; the path "requeue fails after `pg_restore`" (logged, left to the scheduler) is not covered.

## Checked and fine

- **Half-written files in a snapshot.** Originals arrive by `os.replace` from a temporary file (`storage.py:118`), the archive PDF by `os.replace` from the work folder, so a reader sees a whole old file or a whole new one. `_copy_file` hashes the source, copies, hashes the copy, and repeats on a mismatch; three mismatches fail the backup. The hard-link path is verified the same way. The work folders, where files are written in place, are never read.
- **Dump and media order.** `pg_dump` runs first, the media listing and copy after it, under the backup lock that permanent deletion and the browse export also take. Every file a dumped row points to exists at copy time. A document that finishes during the copy is "processing" in the dump with its original in the snapshot.
- **Restore.** `_requeue_interrupted_processing` runs after `pg_restore` on a fresh connection, removes all claims and sets "processing" to "pending" without counting an interruption; the reconciler queues pending documents every minute. If it fails, the restored claims are old and the stall detection requeues. A source that was mid-split is split once (the split and `is_split_source` commit together); a source already split in the dump is not split again. No duplicate documents.
- **Legacy `work-*` / `tmp????????` skip.** Only the first path component is tested, with `fullmatch`. Real media lives only under `originals/` and `archive/` (`_valid_relative`), so no stored document can match. Any other unknown top-level file still fails the backup and still blocks a restore (the test covers both).
- **Symlinks.** A symlinked file or directory under `originals/` or `archive/` still fails the backup; `os.walk` does not follow them. Symlinks inside the skipped folders are not read.
- **Claim token as a path.** The token is `uuid.uuid4()` made in `process_document`; nothing from a request reaches the folder name. The cleanup takes names from the directory listing, parses them as UUIDs, skips symlinks, and treats a non-UUID name as legacy (removed only when older than two hours). Journal lines are resolved and must lie under `originals/`.
- **Work-folder cleanup races.** A run commits its claim before it creates its folder, and the cleanup lists folders before it reads claims, so a live run's folder is never removed. A split holds the source's row lock and checks the claim under it; Cancel, Retry and the requeue take the same lock before they remove the claim, so the cleanup cannot delete the parts of a split that is about to commit. (When it runs is another matter: see L8.)
- **Cancel against a run that is finishing.** `_save_result` and Cancel both take the row lock. If the run saves first, Cancel answers 409; if Cancel is first, the run finds its claim gone, saves nothing, files nothing and starts no workflow. The heartbeat thread stops on its own.
- **MCP write tools.** Both `change_document_tags` and `set_document_filing` pass the grant to `run_for_document`. A workflow that only discloses is recorded as `skipped`; the Italian run details are present.
- **Password check in one place.** Setup, People (create and reset) and the own change all call `password_problem`. The validators are in `AUTH_PASSWORD_VALIDATORS`, so Django's `changepassword` and `createsuperuser` commands and the admin's password form use the same rules; no management command of this project sets a password. All six messages and the two help texts have Italian versions. The own change checks the current password first; People is admin-only and validates the password before it looks the username up; setup answers "Setup is complete" or "Invalid setup key" first. None of them tells an outsider whether a username exists.
- **JSON 500/503 on `/api/`.** The middleware does not catch exceptions; it replaces Django's finished 500 response, so every `atomic` block has already rolled back. Only a non-JSON 500 is replaced: 4xx answers and a view's own JSON 500 pass through. The message has no exception text; the traceback goes to the log. The language middleware sits outside it and translates the sentence.
- **JSON 503 on `/mcp`.** The transport is stateless with JSON responses, so the tool call runs in the request's context and the answer has not started when the flag is set. Only a database error raised out of a `db_call` sets it; 401 and other answers pass through. A token check that fails because the database is away answers 503, not 401, so clients keep their credentials. The tools are safe to repeat.
- **nginx.** `proxy_read_timeout 75s` was already there; new are the 5 s connect limit and the 75 s send limit, both between two operations and not for a whole transfer. Request bodies are buffered by nginx (26 MB cap) before they are sent on. Originals, archive PDFs, version downloads and share bundles are streamed files and start at once; the ZIP export has to fit in gunicorn's 60 s as before. There is no backup download route. `/mcp` answers in one piece. With a single upstream nginx does not repeat a request.
- **Client time limit, the rest.** Uploads (`FormData`) and GETs have no limit. The slow list covers mail, sources, semantic settings, the filing model, bulk actions, merge, export, email, pages, split and versions with 75 s. A caller's own `AbortSignal` is still honoured and is told apart from the time limit. The CSRF retry starts a new request with its own timer.
- **Unsaved-changes question with three buttons.** The focus trap cycles over every button in the box; Esc and the backdrop still mean "keep editing". "Save changes" closes the question first, runs the form's own validation, saves, and only then goes where the person was heading; a refusal, a clash or a missing title keeps the dialog open and drops the pending navigation.
- **Focus changes.** After sharing or removing access, focus goes to the person list (or the summary when nobody is left to choose). Controls stay focusable while a request runs, and `run` ignores a second activation.

## Resolution

| Finding | Resolution |
|---|---|
| M1 | API: fixed. The hold is decided from the document (`workflows.matched_by_agent`): sharing, webhook and email are held back in any run (scheduled, owner edit, bulk) while the workflow's tag/sender/type condition is met by a value with origin `model`. A held-back run files with origin `model` too (chains). Released by an explicit add of the tag, choosing the sender/type, or Run now (`confirmed=True`); a save that merely lists the unchanged tags no longer turns an agent's tag into a manual one (`views.py`). Scheduled held runs are re-examined daily and completed in place. D12 and AGENT_ACCESS.md rewritten. Tests in `test_round10_review.py` (owner edits + bulk, scheduled, sender + Run now, chain). Not done: surfacing held-back runs under Needs attention (API exposes `held_back` on runs). |
| M2 | API: fixed. New `WorkflowRun.held_back` (migration 0064); the one-time webhook/email is due until a run that was not held back exists, the note stays once. Test: agent run, then two owner edits, exactly one "queued email". |
| M3 | API: fixed generically (`archive/idempotency.py`, table `IdempotencyRecord`, migration 0064): any signed-in POST under `/api/` with `Idempotency-Key` (1–64 printable ASCII characters). Same person + key + path within 10 minutes replays the first 2xx JSON answer (`Idempotent-Replay: true`); a second request waits up to 15 s for a running first one, then 409; non-2xx answers keep nothing; same key on another path 422; never across people; stored answers encrypted. Tests in `test_round10_review.py`; eight simultaneous POSTs checked on a real stack. Web: fixed. `api.ts` sends an `Idempotency-Key` on every JSON POST except sign-in, setup and account routes. The key is kept per action (same address and content) while the outcome is unknown (time limit, network error, 502–504) and reused on retry; a server answer or changed input gives a new key. After a note POST with no answer the notes are reloaded (owner and shared dialogs). Tests in `e2e/judge-round10.spec.ts` (written, not run by the web agent). |
| L1 | Fixed. `apply_barcodes` stops when the claim is gone (checked after the scan and again under the row lock before tags/ASN); the archive `os.replace` runs inside `_save_result`, after the claim check, under the lock. Test added. |
| L2 | Fixed. After `pg_restore`, the restore removes copied files that no `Document`, `DocumentVersion` or pending `PurgeJob` row refers to (skipped when the database has no documents; a failure is logged, not fatal). BACKUP_RESTORE.md says so. Test added. |
| L3 | Fixed. A file that vanishes mid-copy fails the backup when a document or version uses it; only unreferenced files are skipped. Tests for this and for `COPY_ATTEMPTS` exhausted. |
| L4 | Fixed. `_remove_split_leftovers` uses `backup.media_path_in_use` (Document original/archive and DocumentVersion). Test added. |
| L5 | Fixed. Passwords over 128 characters are refused before any validator runs (also inside the validator for Django's own forms); People → add compares the new person's name. Tests added. |
| L6 | Fixed for `/api/` and `/mcp`: 503 only for `InterfaceError` or an `OperationalError` whose driver error has no SQLSTATE or class 08 / 57P; deadlock, lock timeout, full disk, too many connections keep the JSON 500. Test added. Not changed: the DEBUG error page outside `/api/` (`/admin/`, `/healthz`, `/livez`). |
| L7 | Fixed (web). "Add note" is pending while Save runs and `addNote` returns early; when the note is stored and the details are refused or clash, the message says "Your note was added. The other changes are not saved yet." and the cleared draft is not posted again; `retriedOcr` forgets documents no longer in the list; `isTimeout` removed. |
| L8 | Fixed. USER_GUIDE (Cancel keeps the worker busy; leftovers timing) and the `job_views` docstring corrected; `reconcile_pending_documents` routed to the `maintenance` queue (no new process; it now waits behind a running backup instead of behind OCR). Checked on a real stack with the OCR worker stopped. |
| L9 | API tests added for M1, M2, M3, L1–L6, the failed-requeue restore path and the routing (`archive/test_round10_review.py`, 16 tests). Not added: a test of a Cancel landing exactly between the claim check and the save (the publish-under-lock test covers the outcome). |

## Judge 1 findings (web)

Source: `.omo/evidence/judge-1-round-10-report.md`. Web only; nothing under `services/api/` was changed for these. Tests are in `apps/web/e2e/judge-round10.spec.ts` and run in both the desktop and the mobile project.

| Finding | What changed | File | Test name |
|---|---|---|---|
| H2 | Every chosen file is written to the on-device queue, with its scan ID, before the request is sent, and removed only when the server has answered (accepted, or refused the file itself). A reload or closed tab mid-request leaves it in the queue; it is sent again with the same `X-Ripiano-Scan-ID`, which the server already uses to recognise a file it has (uploads are `FormData`, so they carry no `Idempotency-Key`; the scan ID is their key). Files of the running upload are not counted as "waiting" and are skipped by the queue's retry, so they are not sent twice at once. After a reload the "waiting to upload" notice is shown at once, before the first retry has had time to fail. Leaving or reloading while an upload runs asks first (`beforeunload`). | `apps/web/src/App.tsx`, `apps/web/src/uploadQueue.ts` | "an upload cut off by a reload stays on the device, is announced as waiting, and is sent once with the same scan ID"; "an upload the server confirms leaves nothing in the device queue, and one it refuses is reported, not kept" |
| M2 | Inbox explanations (failed OCR, damaged PDF, retry notes, exact copy) wrap onto as many lines as they need instead of being cut to one line. | `apps/web/src/style.css` (`.exception-row .document-info p`) | "Inbox explanations are shown whole, on as many lines as they need" |
| M3 | "Add a sender", "Add a type" and "Create a tag": a name that is already in the loaded list (capitals and outer spaces ignored) chooses the existing one without asking the server. If the server answers 409 for a name the list did not have, the list is loaded again and the existing one is chosen. Either way it is announced ("… already exists, so it is chosen. Save changes to keep it on this document."), so Save no longer stores the document without it. If the existing one cannot be found, the refusal stays on screen with the name still in the field, as before. | `apps/web/src/DocumentPanel.tsx`, `apps/web/src/locales/DocumentPanel.ts` | "typing an existing name into Add a type or Create a tag chooses the existing one, and Save keeps it"; "when the server says the name already exists, the list is loaded again and the existing type or tag is chosen"; "Italian: an existing type typed again is chosen and announced" |
| H2 review M-1 | The send loop of an upload checks before each file that the person who chose the files is still the one signed in. If not (signed out, session ended, someone else signed in), nothing more is sent: the file stays kept for the chooser and goes out after their next sign-in here; a file that could not be stored on the device is reported as not sent. The "waiting" banner, the retry and the list refresh at the end of the upload are skipped when the person changed. | `apps/web/src/App.tsx`, `apps/web/src/locales/AppLibrary.ts` (`uploadSignedOut`) | "after someone else signs in mid-upload, the remaining files are not sent and stay kept for the person who chose them" |
| H2 review L-3 | Storing a file on the device gives up after 3 s (and on a blocked database) and the upload goes ahead without the protection. The entry ID is made and marked "being sent" before the entry is written, so the queue's retry cannot pick it up in between. The keep phase shows "Preparing 1 of 3…". | `apps/web/src/uploadQueue.ts`, `apps/web/src/App.tsx`, `apps/web/src/locales/AppLibrary.ts` (`keepingProgress`) | none (no test simulates a storage that never answers) |
| H2 review L-4 | Sign out counts the files kept on the device, including those of an upload still running, and asks "keep or discard" for that number. | `apps/web/src/App.tsx` | same test as M-1 (the question shows 3 files during the upload) |

Not changed: the Lows (L1–L8). None was attempted in this slice; L1–L3 and L7 are search and ingest behaviour on the API side by their description, the others were not examined.

Known limits of the H2 fix: a second open tab of the same person can send a file that the first tab is still sending (the server answers with the same document, by scan ID; no second copy). A browser that cannot store the file (private window, full storage) uploads as before, without the protection. Checked with simulated server states in the browser tests, not by stopping the real API container.


## Judge 1 findings (API)

Source: `.omo/evidence/judge-1-round-10-report.md`. API only; nothing under `apps/web/` was changed. Tests are in `services/api/archive/test_round10_judge1.py` (6 tests).

| Finding | What changed | File | Test name |
|---|---|---|---|
| M1 | Root cause: the old rule dropped a title only when it was exactly the document's own file name. A part of a split scan is titled after the scan (`name (2/2)`) while its file is `name-2.pdf`, so the rule never applied. Now the comparison is by word: title words that are also in a file name behind the document do not count. The names used are the document's own, those of its earlier versions (a replaced file keeps the old name as its title), and that of the scan it was split from (the part's own file name is cut to 80 characters). The same words still count when the document text has them. This applies to suggestions from similar documents, to training of the learned model, and to what the model is asked for suggestions and for automatic filing. The codes printed under control barcodes (the separator code, and the ASN prefix followed by digits) are no longer content words. | `archive/classification.py` (`file_name_words`, `_evidence`, `_terms`), `archive/learning.py` (`features`, `_examples`, `predict`), `archive/auto_filing.py` | `test_parts_of_one_scan_are_not_suggested_each_others_filing_because_of_the_scan_file_name`, `test_file_name_words_are_ignored_in_a_title_wherever_the_name_came_from`, `test_codes_printed_under_control_barcodes_are_not_content_words`, `test_the_learned_model_is_not_trained_or_asked_with_file_name_words` |
| L2 | A search that is only an archive number (`900011`, or `ASN00900011` as printed) also matches the owner's document with that number. Not for "Shared with me", where archive numbers are not searchable. | `archive/views.py` | `test_a_plain_archive_number_finds_its_document` |
| L3 | Sticker and location lookups accept the code without its `R-` / `L-` prefix or hyphen. | `archive/physical_views.py` (`_code_filter`) | `test_a_sticker_code_typed_without_its_prefix_is_found` |

Checked: with the file-name exclusion switched off, the first M1 test fails with the judge's exact output ("shared: separator, barcode, desktop, batch"). The fixture's two parts share only "separator" and "test" in their text, which is below the three shared words a suggestion needs.

Not changed, with reasons:

- L1 (misspelled word found only in document text): the existing correction uses titles, tags, senders and types. Correcting from the words of all document texts needs a decision on cost on the NAS (a word index or trigram search over the text).
- L2, second half (the empty-result tips do not mention `asn:`), L4, L5, L6, L8: web.
- L3, pasted link: the web client already extracts the code from a pasted link (`stickerCodeFrom` in the working tree). A location code typed without `L-` in "Find a sticker" still goes to the sticker lookup, because the client chooses the endpoint by the prefix; the API accepts it only on the location endpoint.
- L7 (three "exact copy" rows for a batch uploaded twice): whether the unsplit scan or its parts should be listed is a product decision.
- "Similar documents" (`archive/similar.py`) still compares title words including file-name words. It was not part of the finding and does not suggest filing.

Cost: suggestions for one document make two more queries (the scan it was split from; earlier versions of all examples in one query), so the query limit in `test_filing_suggestions_skip_existing_tags_cleared_types_and_foreign_or_trashed_examples` went from 9 to 11. Training makes one more query. No new dependency, no migration.

Limits: a model trained before this change keeps file-name words until it learns again (nightly, or "Learn now"). Pages split by hand in the document panel have no link to their source, so only the part's own file name is known for them. A title word that a person wrote and that also happens to be in the file name counts only if the text has it.

Verification: `RIPIANO_DEBUG=1 .venv/bin/pytest -q`: 437 passed, 17 skipped (SQLite). `makemigrations --check --dry-run`: no changes. Not run: PostgreSQL (the archive-number match was not exercised on the full-text search path), Docker, browser tests.

## Independent review of the judge 1 fixes

A second reviewer read the judge 1 fixes (web H2, M2, M3; API M1, L2, L3) without editing anything. No High findings, one Medium, six Low.

| Finding | Resolution |
| --- | --- |
| M-1: a multi-file upload kept sending after the person signed out, so the rest could land in the next person's account and the first person's kept copy was deleted | Fixed. The send loop checks the signed-in person before each file; see the row in "Judge 1 findings (web)". Test: "after someone else signs in mid-upload, the remaining files are not sent and stay kept for the person who chose them". |
| L-1: a document matched only by its bare archive number ranks last under relevance | Not fixed. The judge's case (a number that appears nowhere else) works; ordering among text matches is left for a later change. Not run on PostgreSQL full-text by a unit test. |
| L-2: suggestions for a near-empty document loaded all examples before returning nothing | Fixed. `filing_suggestions` returns after one query when the document has fewer than two content words. Test: `test_a_document_with_almost_no_words_gets_no_suggestions_without_loading_examples`. |
| L-3: every file was stored on the device before the first request, with no progress text and no time limit | Fixed (3 s limit, "Preparing n of N" progress). The time limit and the blocked-database path have no test. |
| L-4: signing out during an upload skipped the keep-or-discard question | Fixed; covered by the M-1 test for "Keep", not for "Discard". |
| L-5: a custom separator code made of ordinary words removes those words from every document's content words | Not fixed. The default code is unaffected. |
| L-6: the prefix-less sticker lookup assumes generated 8-character codes | Not fixed. Generated codes cannot collide; hand-set shorter codes do not exist today. |
