# Round 5 fixes — independent review

Date: 2026-11-18. Branch `codex/initial-implementation`, uncommitted working tree on top of `95e6f6d`.
Reviewer did not edit repository files (only this report), did not touch Docker, and did not run Playwright
against http://localhost:18080.

## Scope

`git diff` (39 files) plus new files: `services/api/archive/cache_headers.py`, `archive/test_round5_fixes.py`,
`archive/migrations/0059_suggestion_dismissal.py`, `apps/web/e2e/round5-web.spec.ts`,
`apps/web/e2e/judge-round5-api.spec.ts`. Read against the judge reports and the two fix notes
(`round-5-api-fixes.md`, `round-5-web-fixes.md`).

Areas checked: suggestion dismissal (authorization, TagOverride reuse, learned/auto-filing exclusion, history,
portable export), agent removal with `?forget=1`, MCP `change_document_tags` name resolution and the
other-agent filter-tag guard, denied-call audit, deactivation (`_end_access`), `PrivateApiCacheMiddleware`,
email snippets, copy history `by`, Inbox "trash this copy" / "resolve all exact copies", upload retry
backoff, Escape in search, sidebar/phone-row CSS, results list, AgentPanel focus handling, API v1 contract.

## Commands and results

| Command | Result |
| --- | --- |
| `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` | 338 passed, 14 skipped (56 s) |
| `cd apps/web && npx tsc --noEmit -p . && npm run build` | pass; PWA precache 8 entries (795 KiB) |
| `git diff --stat -- services/api/archive/api_contract_v1.json` | unchanged; `test_api_contract.py` green (additive only: new route, `forget` query param, `by` field) |
| Throw-away pytest probe (copied into `archive/`, run, deleted) | editor-recipient: dismiss 404, `/trash` 404, `bulk-trash` 404; signed-in `/api/documents/<id>` → `Cache-Control: private, no-store`; non-`/api/` path → no header; MCP names on SQLite: `città`/` Città ` resolve to tag "Città", `CITTÀ` and NFD `Città` → "Tag not found"; a tag whose name is a UUID string → "Tag not found" |

## Verified as correct (no finding)

- **Dismiss authorization**: `dismiss_filing_suggestion` filters `owner=request.user, trashed_at__isnull=True` with
  `select_for_update`, and the label must be the requester's own (views.py:1129-1133). Editor recipients and
  strangers get 404; history field `dismissed_suggestion` is in `OWNER_ONLY_FIELDS`. Learned suggestions
  (classification.py:132) and auto filing (auto_filing.py:96) skip dismissed senders/types. New model is picked
  up by `portable.py` (`get_models()` minus `SKIPPED`).
- **Inbox bulk trash authorization**: `bulk_document_trash` is owner-only (views.py:850-852); a recipient cannot
  trash an owner's document. An original is never trashed by "resolve all": every listed copy points to a
  strictly older document (ingestion.py:41-46), the list only includes copies whose original is not in Trash
  (views.py:500), so the end of every chain is an unlisted, untrashed document that is kept.
- **Agent removal**: owner-scoped (`AgentGrant.objects.filter(pk=…, owner=request.user)`), active grants refused
  with 409, personal API tokens cannot reach `/api/agents` (`api_tokens.BLOCKED_PREFIXES`). Document history keeps
  the agent's name (`actor_label`, no FK to the grant), so only read/denied audit rows disappear.
- **MCP tag names**: resolution happens before the guard, so a name of another agent's filter tag is still
  refused; `add`/`remove` with the same tag in different case is refused as conflicting; owner-only lookup.
- **Deactivation**: default DB session backend (no `SESSION_ENGINE` set), so deleting `Session` rows ends every
  browser session; `ModelBackend` already rejects inactive users meanwhile, and reactivation needs a new sign-in.
  Tokens/grants revoked inside the same transaction.
- **Cache-Control middleware**: only `/api/`, only authenticated (session or token — `ApiTokenMiddleware` sets
  `request.user` before the response passes back out), never overrides an explicit header (share link/bundle
  `no-store`, page preview `private, max-age=3600` kept). The service worker has no runtime caching and denies
  `/api/` navigation fallback, so nothing else changes. Downloads had no validators before, so no extra NAS load.
- **Upload retry**: one timer ref, cleared at the start of every `sendWaiting`, on `offline`, and in the session
  effect cleanup; `sendingWaiting` still prevents overlapping sends; no reschedule after sign-out
  (`signedInAs.current === owner`). The 60 s interval and the backoff timer cannot double-send; server-side
  scan-ID dedupe is unchanged.
- **Escape**: handled on the search input only; dialogs make `#root` inert and the drawer makes `main` inert,
  so it cannot collide with them; the global shortcut handler ignores inputs; IME composition is skipped.
- **CSS at desktop**: `.document-row:last-child { border: 0 }` now matches every row inside its `<li>`, but the
  new `.library-list > li:not(:last-child) > .document-row` rule has higher specificity and restores separators;
  `display: contents` wrappers break no existing child-combinator selectors.

## Findings

### High

None.

### Medium

1. **New e2e "resolve all exact copies" test trashes other specs' documents on a shared account**
   (apps/web/e2e/judge-round5-api.spec.ts:70-87, with :52-68). Every upload uses the same bytes
   (`e2e/fixtures/judge.png`, used by 40 spec files), so after the first upload ever, every judge.png document in
   the account is an "exact copy". With `workers: 2` and desktop + mobile projects, "Keep originals, trash
   copies" moves to Trash every settled judge.png copy in the account — including the `-first`/`-copy` documents
   that a parallel test (or the mobile run of the copy test) is about to click — and `bulk-trash` is
   all-or-nothing per chunk, so a copy trashed concurrently by the other project returns 409 "already in Trash"
   and fails this test too. Expected result: flaky failures in unrelated specs and in these two tests. Fix: give
   each test unique bytes (e.g. append a nonce to the PNG, as other fixtures do for text files) and run the
   resolve-all test against a dedicated account or serially; and do not run it on the stack where another suite
   is running.

### Low

1. **"Resolve all" partial failure is silent about what happened** (apps/web/src/InboxPanel.tsx:118-123). Chunks
   are sent sequentially; if chunk 2 fails (a copy trashed or reviewed in another tab, a document started
   reprocessing), chunk 1 is already in Trash but the user only sees an error. Also a copy that left the Inbox
   meanwhile ("Keep both" in another tab) is still trashed, because the server does not re-check it is an open
   copy. Recoverable from Trash; consider a server-side `only_open_copies` check or reporting the trashed count.
2. **MCP tag names: case folding is ASCII-only on SQLite and no Unicode normalization** (archive/mcp_server.py:230).
   `name__iexact` on SQLite does not fold `À`; NFD vs NFC names never match. On PostgreSQL `UPPER()` folds
   accented letters, so behaviour differs between test and production. Ambiguity is still refused, so this only
   produces "Tag not found", never a wrong tag. A tag whose name parses as a UUID is treated as an ID.
3. **AgentPanel: removing the last revoked/expired agent loses focus** (apps/web/src/AgentPanel.tsx:167, :88-96).
   Focus target `{kind: "inactive"}` points to the `<summary>` that disappears with the group; the effect returns
   without clearing `focusTarget`, focus falls to `<body>`, and the stale target later steals focus when a new
   revoke creates the group again. Fall back to the "Connected agents" heading and clear the target.
4. **Removing an agent deletes its read audit without re-authentication** (archive/agent_views.py:104-110).
   Design choice (privacy-friendlier, documented in AGENT_ACCESS.md); note that creating an agent requires the
   password but erasing what a revoked agent read does not, so a hijacked session can remove that trail. Owner
   should confirm this trade-off; a password prompt on Remove would close it.
5. **Sender/type dismissals have no undo** (archive/views.py:1141). A misclicked "Not right" on a sender or type
   hides that suggestion and blocks learned auto filing for the document permanently; unlike tags (cleared by
   adding the tag by hand), choosing the sender manually does not clear the `SuggestionDismissal`.
6. **Deactivation leaves the person's public share links and bundles working** (archive/people_views.py:133-147;
   share_views.py:93 does not check `owner.is_active`). The success message says "what they shared stay as they
   are", so this matches the text, but an admin turning an account off for security reasons may expect public
   links to end too. Owner decision.
7. **Escape with stale results** (apps/web/src/App.tsx:1653-1664). While a new query's results are still
   loading, `documents` holds the previous results, so Escape focuses and activates the first row of the old list
   and Enter opens it. Minor.
8. **Summary focus ring not fully uniform** (apps/web/src/style.css, `.agent-inactive > summary:focus-visible`).
   Same specificity as the shared contract and later in the file, so the agents' summary uses `accent-strong` with
   a 2px offset instead of `--color-focus` with 3px — contrary to the J2 L4 "one contract" intent.
9. **Email snippet heuristic** (archive/views.py:175-195). For an email without a Subject row, a "Subject:" line
   inside the body (forwarded message) within the first 3000 characters is taken as the header end, so the
   snippet search starts there; it falls back to the full text, so a snippet is still returned. Cosmetic.

## Verdict

**Pass with follow-ups.** No high findings; the authorization paths asked about (recipient dismissal/trash,
original vs copy in "resolve all", cross-user agent removal, active-agent removal, tag-name guard, session
ending on the DB backend, Cache-Control scope/overrides, retry timer leaks, API v1 contract) hold. Fix the
e2e fixture/isolation problem (medium 1) before running `judge-round5-api.spec.ts` in the shared suite; the low
items can go to the follow-up list, with lows 4 and 6 needing an owner decision. NAS impact: none noticeable.

## Resolution (main session, 2026-11-18)

- **Medium fixed:** the Inbox specs no longer upload the shared `judge.png`; each test builds its own small PNG, so it never creates exact copies of other specs' files. The "Resolve all exact copies" test intercepts the bulk-trash request, asserts the app sends this test's copy and not its original, and forwards only that copy, so it cannot trash other tests' documents on the shared account. The barcode specs now also free archive numbers held by documents an earlier run moved to Trash.
- **Found while running the suite (real bug, fixed):** the Library cleared the keyboard selection (`j`/`k`) on every list refresh, which happens every few seconds while a document is processing. The selection now stays on the same document across refreshes and clears only if that document leaves the list or the screen changes.
- **Low, not changed now:** "Resolve all" partial failures are not itemised; MCP tag-name matching is case-insensitive for ASCII only on SQLite (PostgreSQL folds accents too) and does not normalise Unicode; focus after removing the last revoked agent; deleting an agent's log needs no password (owner decision); dismissed sender/type cannot be undone; deactivating an account leaves its public share links working (owner decision); Escape during the very first load can select a row that is replaced; agents summary focus ring; a "Subject:" line inside a forwarded message body can lead an email snippet.
