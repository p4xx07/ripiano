# Round-4 fixes: independent review

Date: 2026-11-18. Reviewer: independent agent (read-only except this file).
Branch: `codex/initial-implementation`, uncommitted changes on top of `b57e14e`.

## Scope

`git diff` (39 files, +1060/-102) plus the new files:
`archive/spelling.py`, `archive/migrations/0058_workflow_assignment_actions.py`,
`archive/test_workflow_assignments.py`, `archive/test_round4_upload_errors.py`,
`apps/web/e2e/judge-round4-j2.spec.ts`, `apps/web/e2e/workflow-assignments.spec.ts`.
Focus: workflows.py / workflow_views.py / storage_paths.py / history.py (assignment actions),
agent_views.py / api_tokens.py (password + revocation), storage.py (pixel cap), App.tsx /
DocumentPanel.tsx / AgentPanel.tsx / ui.tsx (Trash undo, drawer, offline screen),
search_syntax.py / spelling.py / views.py (dates, suggestion), api_contract_v1.json.
Docker and the Playwright suite at :18080 were not touched; e2e specs were read, not run.

## Commands and results

| Command | Result |
| --- | --- |
| `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q -x` | 328 passed, 14 skipped (53.8 s) |
| `cd apps/web && npx tsc --noEmit -p .` | clean |
| `cd apps/web && npm run build` | built; PWA precache 8 entries (782 KiB) |
| `git diff archive/api_contract_v1.json` | additions only (`document_date_origin`, `title_template`, `set_storage_path_id`, `set_custom_fields`, `share_with`); nothing removed or retyped |

## Findings

### High

None found.

### Medium

**M1. Password-hash upgrades now silently revoke every agent grant.**
`services/api/archive/api_tokens.py:44-54` (pre_save hook, connected in `apps.py:14`) revokes
when the stored hash string changes. Django's `AbstractBaseUser.check_password` (Django 5.2.19,
`base_user.py:106-110`) rehashes on login when the hasher's parameters changed (e.g. the PBKDF2
iteration bump of every Django major release) and saves `password`. That counts as a "password change".
What goes wrong: after the next Django upgrade, each person's first sign-in (or the
`check_password` call that the new agent-creation check makes, `agent_views.py:62`) revokes all their agent
grants, including the token the local classifier Mac worker uses, with no notice. The ApiToken part of this
was already there; this change extends it to agent grants, which are long-lived and run unattended.
Fix: Django sets `instance._password = None` in that setter, and it is non-None after a real
`set_password()`. Revoke only when `getattr(instance, "_password", None) is not None` (or compare
`check_password`-independent intent), and add a test that simulates a hasher upgrade.
Admin resets (`people_views.py:175`) and `manage.py changepassword` go through `set_password` and still
revoke, which is the right behaviour. `reset_two_factor` does not touch the password, so it does not revoke.

**M2. Untracked scratch files with live-looking tokens sit in `apps/web/`.**
`apps/web/toks.json` holds two `rpa_…` agent tokens ("cloud", "local"). `lib.mjs`, `t1.mjs`, `tag.txt`, and
`sticker.txt` are judge scratch scripts that read passwords from the environment. None of them is gitignored.
What goes wrong: a `git add -A` while committing this slice publishes the tokens and stray scripts. Delete
them, or move them under `qa-artifacts/…` with the tokens revoked, before committing.

### Low

**L1. Renaming a custom field forgets a manual choice.** `workflows.py:132-147` (`set_by_person`) keys
custom-field choices by the field name in the history (`history.diff` records names). If the owner sets a value
by hand and later renames the field, an `updated` or scheduled workflow then overwrites the hand-set value.
Title and storage path are not affected. Rare; document it or also match on current field IDs.

**L2. The upload title is not treated as a manual choice.** A title typed in the upload form is stored at
creation (a `CREATED` event, not `UPDATED`), so an `added` workflow with a title template replaces it.
That matches Paperless's behaviour, but the docs say "a title a person chose by hand is never overwritten".
Clarify the wording or treat a non-default upload title as manual.

**L3. Hand-choice lookup cost.** `set_by_person` loads every `USER`/`UPDATED` event's JSON for the document
once per workflow run. History stays small per document, and `run_scheduled` is capped at 500 documents, so
the cost is bounded. Note only. No privilege issues were found in the assignment actions:
- storage path and custom fields are checked against the owner at save (`_owned`) and again at run (`owner_id=workflow.owner_id`);
- the share rules match `people_views.document_access`: an active person, not the owner, any group, a 200-grant cap;
- grants are re-checked against `is_active` at run time;
- `updated` workflows run only on the owner's own edits (`views.py:1056`), so an edit-level recipient cannot trigger a re-share;
- `/api/workflows` is blocked for API tokens (`api_tokens.py:24`);
- `access` history entries are hidden from recipients (`OWNER_ONLY_FIELDS`).

**L4. Images over 100 MP that are already stored can no longer be OCR'd.** `storage.py:24` sets
`Image.MAX_IMAGE_PIXELS = 50_000_000` for every process. Pillow raises an error above 2× that (100 MP) and only
warns between 50 and 100 MP. New uploads above 50 MP are refused anyway. An image document above 100 MP stored
before this change now fails on Retry OCR (`tasks.py:76`) with the generic message. Things that are not affected:
- ocrmypdf and Ghostscript run in subprocesses, outside this limit;
- barcode pages are capped at 40 MP (`barcodes.py:16`);
- PDF pages are not decoded by Pillow in-process;
- the app has no other Pillow users.
Also, `warnings.catch_warnings()` in `save_original` is not thread-safe. That only matters if gunicorn runs threads.

**L5. Offline screen and the username kept in localStorage.** `App.tsx` `rememberSignedIn` clears the key on
sign-out and on a 401 (session becomes unauthenticated). A person who closes the browser without signing out
leaves their username, and the count of their queued uploads, visible on the offline screen to the next person on
that device. That person already has the IndexedDB queue and the session cookie, so the extra exposure is small.
Other checks:
- `inert` comes from `narrowLayout && menuOpen`, so it clears when the window is resized wider;
- the Tab trap is registered only while the drawer is open on a narrow layout and bails out when a dialog is open;
- Undo after the document was permanently deleted gets a 404 from `/restore` and shows the "failed" state, so it is handled.

**L6. Bare-date search clauses skip the free-text path.** `search_syntax.py:136-139` turns `2026-10-14` into an
`or(any, date)` clause, which runs `icontains` over `extracted_text` instead of the full-text and semantic words
path. That is correct, and negation and OR chains nest fine: `-2026-10-14` stays `-any`, and a nested `or` is
handled recursively by `clause_filter`. The cost is a sequential scan on large archives, and `free_query` becomes
empty for a date-only query (so it gets no spelling suggestion, which is fine).

**L7. Spelling suggestion cost.** `spelling.py` loads up to 5000 titles plus 3×2000 names, then runs `difflib`
over up to 20000 words for each of at most 6 tokens. It runs only on empty, uncursored, non-shared first pages,
and uses only `owner=request.user` data, so it cannot leak words from other people's documents. Expect roughly
0.1–0.5 s on the NAS for a no-result search on a large archive. Consider caching the vocabulary per user for a
few minutes if search-as-you-type hits it often.

## Verdict

**Approve with fixes.** No high-severity bugs. Fix M1 (scope the revocation to real password changes) before the
next Django upgrade. Remove or relocate the untracked token and scratch files (M2) before committing. The low
items are optional or need documentation only. The API v1 contract only gains fields. Backend tests and the
web type-check and build pass.

## Resolution (main session, 2026-11-18)

- **M1 fixed:** `revoke_tokens_on_password_change` acts only when a password was set (`instance._password` is not None), so Django's hash upgrade on sign-in no longer revokes API tokens or agent grants; a new password still revokes both. Regression test `test_a_password_rehash_keeps_agents_but_a_new_password_revokes_them` fails on the previous code and passes now.
- **M2 fixed:** the judge's scratch files (`apps/web/toks.json`, `lib.mjs`, `t1.mjs`, `tag.txt`, `sticker.txt`) were moved out of the repository, and every still-active agent grant of the judge accounts on the local stack was revoked (6 grants).
- **Low, not changed now:** a renamed custom field forgets a manual value for workflow purposes; an "added" workflow title template replaces a title typed at upload; Retry OCR on an image over 100 MP stored before the cap now fails with the size message; spelling suggestion and bare-date cost on very large archives.
