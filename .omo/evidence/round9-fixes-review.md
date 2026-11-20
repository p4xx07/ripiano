# Round 9 fixes — independent review

Scope: the uncommitted changes on `codex/initial-implementation`. That is `git diff HEAD` plus the untracked files `archive/health.py`, `migrations/0062_…`, `test_round9_fixes.py` and `e2e/judge-round9.spec.ts`. I checked them against the judge round 9 reports. I only read the code and ran checks; I did not edit it. Another agent was editing `tasks.py` (maintenance-queue chunking), `classification.py`, e2e cleanup and docs at the same time; I did not review those parts, and line numbers in `tasks.py` may have moved. I ran:

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_round9_fixes.py archive/test_job_controls.py`: 20 passed, 2 skipped (no zbar on this machine, so the split-source requeue test did not run here).
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`: "No changes detected".
- `npx tsc --noEmit -p .` in `apps/web`: clean.

I did not run Playwright, Docker, a real PostgreSQL restart, a real worker kill, or the migration against PostgreSQL.

No high-severity findings.

## Medium

### M1. Stalled-processing recovery trusts the wall clock and the old run's finish is not fenced, so a worker that is alive can be declared gone and later overwrite what the owner or the scheduler decided
`tasks.py` — `processing_stalled` (around line 80), `_Heartbeat._run`, `_process_claimed` final saves (around lines 216 and 230), `requeue_stalled`, `reconcile_pending_documents`; `job_views.py:169-177`; `views.py:1452-1460`.

Two things combine:

1. "Gone" is decided from `timezone.now()` minus a timestamp written by another process. A live worker looks gone whenever its heartbeat is more than 2 minutes old by the wall clock:
   - the host clock jumps forward (a judge saw a 4-hour jump; NTP correcting a wrong RTC after a NAS boot does the same). The scheduler fires its due tasks at once, and the next heartbeat can be up to 30 s away;
   - the database is unreachable for more than 2 minutes while OCR runs (OCR is a subprocess and does not need the database). The heartbeat fails and is only logged. When the database is back, the reconciler may run before the next beat;
   - the heartbeat `UPDATE` waits on the document's row lock. `_split` (`tasks.py:552-578`) holds `select_for_update` on the source while it writes every part, which can be slow for a large batch on NAS disks.
2. Nothing ties the finishing run to its claim. `_process_claimed` saves `status=READY` (or `FAILED`) with `update_fields` from an in-memory copy, whatever the row says now. The heartbeat only filters on `status=PROCESSING`, not on which run owns the document.

Scenarios in the default stack (one worker, concurrency 1):
- The clock jumps while a 20-minute OCR runs. The Library shows the document as interrupted with Retry and Cancel. The owner presses Cancel: it becomes "failed / cancelled". Fifteen minutes later the worker finishes, sets it Ready, files it and runs the "added" workflows (tags, sharing, emails, webhooks) for a document the owner cancelled.
- Each false stall adds 1 to `processing_failures`. Three of them (three database blips during one long OCR) show "Processing stopped unexpectedly several times" while the worker is still on it; it then turns Ready by itself.
- A clock jump backwards leaves the heartbeat in the future. If the worker really dies then, the document is not seen as stalled, and Retry and Cancel stay refused, until the clock catches up.

With a second worker (`--scale worker=2` or a higher `--concurrency`) the requeued message runs at the same time as the old run. Both see `processed_at is None`, so "added" workflows, learned filing and `record_unlock` run twice, and both replace the same archive file.

In the default stack no document or original is lost, and the split is not repeated (see "checked and fine"). That is why this is Medium and not High.

Fix:
- Give each claim a token (a UUID, or `processing_started_at` itself). Make the final saves and the heartbeat conditional: `Document.objects.filter(pk=…, status=PROCESSING, <token>=mine).update(…)`. When zero rows match, skip filing and workflows.
- Do not decide on one wall-clock comparison. Require the heartbeat value to be unchanged on two reconciler passes in a row, or compare ages with the database clock in one query (`now() - processing_heartbeat_at`), which at least removes skew between containers.
- Add tests: a late finish after requeue, a late finish after Cancel, and a heartbeat dated in the future.

### M2. The shared-document editor still saves without `base_version`, so the "two family members with edit access" case from judge 2 M1 still loses updates silently
`apps/web/src/SharedDocumentPanel.tsx:73-87`. The PATCH always sends `title`, `document_date`, `action_status`, `action_due_date`, `action_note`, and `tags` when tags are shared. It sends no `base_version` and no `If-Match`, and has no handling for a 409. The server check is opt-in (`views.py:1074`), so this path is last-write-wins exactly as before.

It is also worse than the owner dialog was, because every field is sent, not only the changed ones.

Scenario: Anna shares "Bolletta gas" with Luca for editing. Luca opens it. Anna renames it and sets a due date. Luca ticks one tag and presses Save. Anna's title and due date are replaced by the values Luca's dialog loaded, and Luca sees "Saved". Because the date is always sent, it is also marked as set by hand (`document_date_origin = MANUAL`).

The same gap exists for single-field PATCHes (`ActionPanel.tsx:52`, `InboxPanel.tsx:84,104`, and `markWarningChecked` / `acceptSuggestion` in `DocumentPanel.tsx:431,750`). Those are safe as they are: each writes one field the person just acted on, and `adopt()` takes in the rest.

Fix: send `base_version: current.edit_version` from `SharedDocumentPanel`, send only changed fields, and on `edit_conflict` show the newer document with the message (the owner dialog's `mergeOnConflict` can be reused). Add a server test for a shared editor's stale save and an e2e for this dialog.

## Low

### L1. Kept drafts now outlive another person's whole session on a shared device
`App.tsx:627-652`, `1489-1533`, `1898-1899`. In round 8 a different person signing in dropped the draft. Now it stays in `sessionStorage["ripiano.keptDraft"]` for up to 24 hours, with the username in clear text, the changed field values and the unsaved note text.

- Luca signs in in the same tab after Anna's session ended. Anna's draft stays readable in devtools for all of Luca's session and after he signs out. Only Anna's own sign-in or sign-out, the Discard button, or closing the tab removes it.
- Expiry is checked only when the list is read or written, not by a timer. A tab left open keeps the text until the next sign-in or reload.
- "Discard" on the sign-in screen (`App.tsx:1997`, `keepDrafts([])`) discards every person's drafts, so anyone at the device can throw away Anna's edits. The sign-in notice does not say whose draft is kept.
- A session ended by a password change or by the account being turned off (D9, D11) also keeps the draft.

This is a trade-off the round 9 judge asked for (L6). Reduce the exposure: store only a marker per person plus the draft encrypted with a key derived on sign-in, or keep the draft in memory only for other people's sessions, or at least clear another person's drafts on an explicit sign-out and shorten the lifetime to an hour or two.

### L2. The always-sent date turns a detected date into a "manual" one during an automatic re-save
`DocumentPanel.tsx:475-477`, `510-517`; `views.py:1101-1103`. `document_date` is in every PATCH. When the date changed on the server but the person did not touch it, the server answers 409 for `document_date`. `mergeOnConflict` then finds no clash, takes the server's date, and the loop sends it again. The save succeeds and sets `document_date_origin = MANUAL`.

Scenario: Anna opens a document from the Library list, in a tab that has been open since before OCR finished, and fixes a typo in the title. Date detection had meanwhile set 2026-03-01. Her save "confirms" a date she never saw, and a later reprocess no longer corrects it.

The loop itself is bounded: at most three PATCHes (`attempt < 2`), then the conflict notice. A clashing field is never re-sent automatically. Fix: send `document_date` only when it differs from `base`, or do not re-send it after a merge unless the person changed it.

### L3. The upload "can't be reached" probe uses `/healthz`, which now answers 503 while only the queue server is down
`App.tsx:1790` treats any status of 500 or more as unreachable. `views.py:372-374` answers 503 when Valkey is down. Uploads still work then (the document waits as pending and is reconciled later), but the progress line says "Ripiano can't be reached; trying again…" for as long as the upload runs. `/livez` would be the right probe, but `nginx.conf` does not forward it. Either forward `/livez`, or treat a 503 that carries JSON as "reachable".

### L4. `/healthz` is public and now does real work and tells more
`apps/web/nginx.conf:30` forwards `/healthz` without sign-in. Each call now runs a query and opens a new Valkey connection (up to 1 s when Valkey does not answer), on an api with 2 workers × 2 threads. The answer tells anyone whether the database or the queue server is down. The exposure is small on a home NAS; consider answering only `{"status": …}` to requests that come through the web container, or a short cache of the result (a few seconds).

Related: `depends_on: api: condition: service_healthy` on `web` and `mcp` now also depends on Valkey. A `docker compose up -d` (an update) while Valkey cannot start leaves `web` not started, so the whole archive is unreachable, where before the interface came up and reading and search worked. `docs/BACKUP_RESTORE.md` should say so.

### L5. Sign-in throttling fails open for any exception, with no fallback
`throttle.py:28-32`, `36-44`. This is acceptable: passwords and two-step codes are still checked, and an attacker cannot switch Valkey off. Two points:
- `except Exception` also hides programming errors (a wrong key type, a serializer error), not only cache outages. Catch `redis.exceptions.RedisError`, `ConnectionError`, `TimeoutError` and `OSError`.
- During an outage there is no limit at all on the four callers (`views.py:418`, `security_views.py:45`, `agent_views.py:56`, `api_tokens.py:123`). A small in-process counter used only when the cache fails (`LocMemCache`, same keys) would keep a bound of about 10 tries per gunicorn worker at no cost in RAM.
- When Valkey accepts no connection but does not refuse it either, each failed sign-in waits through several 2-second timeouts (two reads, then `add` and `incr` for two keys) on one of four request threads.

### L6. `processing_failures` now counts two different things
`requeue_stalled` adds interruptions to the same counter as OCR failures, and the counter is not reset on Retry (`views.py:1456-1460`).
- A document that failed OCR twice and is retried, then meets one worker restart (an update), is marked failed with "stopped unexpectedly several times".
- One interruption followed by one real OCR failure shows "Text recognition failed again, so the file is probably damaged".
- After "interrupted", each Retry gets exactly one more attempt, which is reasonable but not said anywhere.

A separate `processing_interruptions` counter, reset on a person's Retry, would keep both messages true.

### L7. Each interrupted run leaves its work directory, and a rerun repeats notes
- `_process_claimed` uses `tempfile.TemporaryDirectory(dir=media_root)`. A killed worker leaves the directory (input PDF, OCR output, unlocked copy of a protected PDF) in the media root. Nothing removes it. Recovery now retries up to three times by itself, so a file that kills the worker leaves three copies. The reconciler could remove `tmp*` directories older than the task time limit.
- `_split` removes the part files only in its `except` branch. A kill before the commit leaves them in `originals/` with no database row.
- `apply_barcodes` adds its "only the first N pages are checked" note on every first-run attempt, so a requeued scan gets it twice.

### L8. Polling has no back-off and two loops never give up
- `App.tsx:405-410`: a watched backup reloads two lists every 3 s until it ends. Backups may run for hours (`time_limit=6 h`). If the run is no longer among the 20 listed (`views.py:1495`), `watchId` is never cleared and the button stays pending until the panel is reopened.
- `InboxPanel.tsx:183-224`: every retried card is fetched every 3 s, one after the other, with no check that the previous pass has finished, and for as long as the document stays pending (worker stopped, long queue).
- `DocumentPanel.tsx:338-351`: `/api/jobs` every 15 s on top of the existing 2.5 s document poll, also in a hidden tab (the Library and Jobs loops check `document.hidden`; these do not).
- A stalled document is only flagged in the Library and the dialog when it is among the first 25 waiting items of `/api/jobs` (`JOB_LIST_LIMIT`). A `stalled` field on the document itself would remove the extra request.

All timers are cleared on unmount; none of this leaks.

### L9. The MCP health check shares the single database thread with agent calls
`sync_to_async` is thread-sensitive, so every `db_call` runs on one thread. `/healthz` on port 8001 waits behind a slow agent call (a semantic search that waits for the embedding service). Three slow checks in a row show `mcp` as unhealthy although it works. Nothing restarts it, so the effect is a wrong status only. `database_ok` also catches only `DatabaseError`; Django's `InterfaceError` ("connection already closed") is not a subclass, so that case answers 500 instead of 503. Both fail the check, as they should.

### L10. Test gaps
- No test for a late finish after requeue or after Cancel (M1), for a heartbeat in the future, or for a shared editor's stale save (M2).
- `test_a_requeued_split_source_is_not_split_again` is skipped without zbar; it did not run in this review.
- The fail-open test covers `cache.get` raising, not a failure in `add`/`incr` after a successful read.
- No test that `If-Match` with a weak tag (`W/"…"`) and with `*` behave as documented; by reading they do (`views.py:281-289`).

## Checked and fine

- **MCP reconnect.** Every ORM entry point (`GrantVerifier.verify_token`, `_list_allowed`, `_call`, `_database_ok`) goes through `db_call`; no bare `sync_to_async` is left. The cleanup runs on the same thread that owns the connection, so there is no cross-thread close. `CONN_MAX_AGE` is 0, so each call ends with its connection closed: no leak, and a PostgreSQL restart cannot leave a broken connection behind. The `in_atomic_block` guard only matters in tests. The lifespan scope still reaches the MCP app. Port 8001 is not published and nginx forwards only `/mcp`, so `/healthz` there is reachable only inside the stack.
- **Heartbeat thread.** It uses its own thread-local connection and closes it; a failed beat closes the connection so the next one reconnects. OCR, LibreOffice and Ghostscript run as subprocesses, and pypdf is pure Python, so the main thread does not starve the heartbeat. A hard time limit kills the child and the heartbeat with it.
- **ACKS_LATE and the visibility timeout.** After a kill, the unacknowledged message comes back after the 1-hour visibility timeout. By then the reconciler has requeued and the document is ready, so the redelivered task returns at the status check. No double run follows from redelivery alone.
- **Barcode split on redelivery.** `_split` creates the parts and sets `is_split_source` in one transaction under the row lock, and `apply_barcodes` skips a source already split, so a rerun creates no second set of parts. Tags use `get_or_create`; the ASN update is conditional.
- **Originals.** Processing never moves or rewrites the original; the archive file is replaced with `os.replace`. Requeue, Retry and Cancel touch only status fields.
- **Owner Retry / Reprocess / Cancel.** All three re-check `processing_stalled` under `select_for_update`, are limited to the owner, and are refused (409) for a document with a fresh heartbeat.
- **Optimistic concurrency on the server.** The check runs under the row lock, before any write. A token of the wrong length or prefix answers 400. Shared editors get a token over their own fields only, so no hash of ASN or storage path reaches them. The 409 body is built with the caller's access level. A request without a token behaves as before. API responses carry `Cache-Control: private, no-store` and no conditional-GET middleware is installed, so the new `ETag` cannot produce a wrong 304.
- **Owner dialog on a 409.** The re-save loop is bounded, re-sends only fields the person changed and the server did not, and never re-sends a clashing field; those are shown with both values and "use mine". Tags merge as additions and removals on top of the server's list. Other 409s (ASN in use) stay ordinary errors.
- **Throttle.** When the cache works, limits and keys are unchanged. The cache has 2-second timeouts so an outage does not hang sign-in for long.
- **`revoked_reason`.** Set only by the password-change signal and by `_end_access`; an owner's own revoke leaves it empty; it is returned only to the owner.
- **Kept drafts.** A draft is restored only for the same username, is dropped when older than a day, and an explicit sign-out removes that person's own draft. The old single-object format is still read.
- **Migration 0062.** Two additive `AddField` operations (a nullable timestamp and a `CharField` with `default=""`), no data step, automatically reversible by dropping the columns; `makemigrations --check` is clean. Documents that were processing during the update have no heartbeat and a start time, so they are requeued about 2 minutes after the new scheduler starts instead of after an hour.
- **Compose.** The two files have the same healthcheck changes. Compose does not restart an unhealthy container, so a Valkey outage cannot cause a restart loop.

## Resolution

| Finding | Resolution |
|---|---|
| M1 | Fixed. Each run holds a `ProcessingClaim` row (token, `beat_at`, `suspected`; migration 0063, which also drops `processing_heartbeat_at`). The heartbeat updates only that row (`WHERE token = mine`, database `now()`), so it never waits for the document lock that `_split` holds. Final saves go through `_save_result`: under the document row lock, only if the document is still processing and the claim with this token can be deleted; otherwise the result is discarded and no filing, date detection, learned filing or workflow runs. Retry, Cancel and the scheduler's requeue remove the claim. Staleness is judged in SQL with the database clock (fresh = `beat_at` within 2 minutes either side of `now()`, so a future heartbeat is stale). The scheduler requeues only a claim found stale on two passes in a row (first pass sets `suspected`, the next heartbeat clears it; a failed heartbeat retries after 5 s; locked rows are skipped), so a clock jump or a database outage is not counted. Tests in `test_round9_fixes.py`: `test_a_run_that_was_requeued_meanwhile_cannot_finish_over_the_new_attempt`, `test_a_run_cancelled_meanwhile_cannot_mark_the_document_ready`, `test_a_failing_run_that_lost_its_claim_does_not_record_its_failure`, `test_one_late_heartbeat_is_not_a_stopped_worker`, `test_a_heartbeat_dated_in_the_future_is_not_proof_of_life`, `test_the_worker_heartbeat_is_refreshed_while_processing`. Real check on the stack: a 60-page scan, worker killed during OCR at 22:13:05; flagged stalled at about 2 min, requeued and claimed again at 22:16:06, Ready at 22:16:42 with one copy, `processing_interruptions` back to 0. The lock-free heartbeat was not exercised against a real long split. |
| M2 | Fixed. `SharedDocumentPanel.tsx` sends `base_version` and only the changed fields, re-saves clean merges, and shows a clash with both values and **Use my value** (EN + IT). Server test `test_a_shared_editors_stale_save_keeps_the_owners_newer_changes`; e2e `a shared editor's save keeps the owner's newer changes and asks about a detail both changed` (`e2e/people-sharing.spec.ts`, desktop only, uses the second e2e account). |
| L1 | Fixed, with one deviation. Drafts are stored under a SHA-256 fingerprint of the username (no clear-text name), expire after 12 h (a timer enforces it), and are removed on that person's sign-out. **Discard** is offered only to the person whose session just ended in this window and removes only that draft. While a different person is signed in, other people's drafts are taken out of `sessionStorage` and held in memory only; they return to storage when that session ends (a reload during it loses them). They are not deleted outright, to keep judge 2 round 9 L6. e2e: `a kept draft stays for its person when someone else signs in, and nothing about it is shown` (adapted). |
| L2 | Fixed. `document_date` is sent only when the person changed it, also after a merge. e2e: `a save of details this person changed is not refused for a date changed elsewhere, and does not send the date`, `a save refused for a detail both set to the same value is merged and saved without a question`; the server test for M2 checks the date origin stays unset. |
| L3 | Fixed. The web container forwards `/livez`; the upload probe uses it and counts a 503 with JSON as reachable. Test `test_the_web_container_forwards_livez_and_marks_healthz`; checked on the stack (`/livez` through web answers 200). |
| L4 | Fixed. Requests forwarded by the web container carry `X-Ripiano-Forwarded` and get only `{"status": …}`; the checks are reused for 5 s. Test `test_public_healthz_is_cheap_and_does_not_say_which_part_is_down`. The `web`/`mcp` dependency was left as it is: `api` (and every service built on `x-api-base`) already required a healthy broker before round 9, so the start-up behaviour did not change; `docs/BACKUP_RESTORE.md` now says so. |
| L5 | Fixed. Only cache/connection errors (`RedisError`, `ConnectionError`, `TimeoutError`, `OSError`) fail open; failures are then counted in an in-process `LocMemCache` with the same limits, and the shared cache is left alone for 30 s so sign-ins do not wait on repeated timeouts. Tests `test_sign_in_is_still_limited_per_process_while_the_cache_is_down` (covers `add`/`incr` failing after a successful read, and a `TypeError` not being swallowed), `test_sign_in_works_while_the_cache_is_unreachable`. |
| L6 | Fixed. New `Document.processing_interruptions`, counted apart from `processing_failures`, reset on success and on a person's Retry. Tests `test_a_document_that_keeps_killing_its_worker_stops_after_three_tries`, `test_a_processing_document_without_a_heartbeat_is_requeued_within_minutes`. |
| L7 | Fixed. Work directories are named `work-*`; the scheduler's reconcile task removes `work-*` and old-style `tmp????????` directories older than 2 h from the media root. `_split` journals each part it writes in the work directory, and the cleanup deletes journalled files under `originals/` that have no document. Automatic notes are added once per document and text. Test `test_work_directories_and_uncommitted_split_parts_of_killed_runs_are_removed`. |
| L8 | Fixed for the three loops: the backup watcher and the Inbox retry loop run one pass at a time, from 3 s growing to 30 s, pause in a hidden tab, and the backup watcher stops when the run is no longer listed; the dialog's `/api/jobs` poll skips hidden tabs. Skipped: a `stalled` field on the document itself (the 25-item limit of `/api/jobs` remains); it would change the version-1 API contract and needs its own slice. |
| L9 | Fixed. The MCP health check runs on its own thread and connection with a 2.5 s limit, and `database_ok` catches `django.db.Error` (so `InterfaceError` answers 503). Tests `test_mcp_health_check_does_not_wait_behind_agent_calls`, `test_health_checks_report_real_failures`. |
| L10 | Added: the M1, M2, L5 tests above and `test_if_match_accepts_weak_tags_and_ignores_a_star`. Not done: `test_a_requeued_split_source_is_not_split_again` still needs zbar and is skipped on this machine (updated for claims, not run). |
