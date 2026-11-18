# Round 5 — API slice fixes

Base: `95e6f6d` on `codex/initial-implementation` (uncommitted working tree). Sources: judge-1/2/3 round-5 reports.
Not done here: App.tsx, KeyboardHelp, App/AppLibrary locales (another agent); J3 L4 offline retry loop (App.tsx, skipped by instruction).
Nothing was run against the shared stack at http://localhost:18080; Docker was not touched.

## Items

| # | Finding | Fix |
| --- | --- | --- |
| 1 | J2 M2 — "Not right" only hid a suggestion for the browser session | New `POST /api/documents/<id>/filing-suggestions/dismiss` `{kind: tag\|correspondent\|document_type (aliases sender, type), id}`, owner-only (the same scope as `GET …/filing-suggestions`, which editors never see). A tag dismissal creates a `TagOverride` (same as a manual removal: rules, workflows, agents, learned auto-filing already respect it; adding the tag by hand later clears it). Refused with 409 if the tag is already on the document. Sender/type dismissals are stored in the new `SuggestionDismissal` model (migration `0059_suggestion_dismissal`; cascades with document/label; included automatically in portable export). `filing_suggestions`, `_add_learned`, and `auto_filing` skip dismissed senders/types for that document. A new dismissal writes a history event with change `{"field": "dismissed_suggestion", "kind", "name"}` (owner-only field). The learned model is positive-examples-only Naive Bayes with no notion of negative examples, so a dismissal is not fed to training (documented in USER_GUIDE). Frontend: sessionStorage removed; DocumentPanel calls the endpoint, hides the item optimistically, rolls back on error, refreshes the history list. |
| 2 | J1 L4 / J2 L8 — revoked agents pile up | `DELETE /api/agents/<id>?forget=1` removes a revoked or expired grant (409 for an active one) **together with its AgentAudit rows** (privacy-friendlier; document history entries the agent made remain, by name). Plain DELETE still only revokes. AgentPanel: revoked and expired agents are in a closed `<details>` "Revoked or expired (N)", each with Remove + confirm; after revoking, focus goes to that group's summary. |
| 3 | J1 L5 — email snippets start with header text | `_search_snippet`: for `message/rfc822` / Outlook documents, the snippet is taken from the body after the rendered From/To/Date/Subject(/Attachments) block; if the hit is only in the subject, it starts at the subject value. Other documents unchanged. |
| 4 | J1 L7 / J2 L1 — Inbox exact copy only offers "Keep both" | InboxPanel: "Move this copy to Trash" per copy (existing `POST /api/documents/<id>/trash`), and "Resolve all exact copies" with an inline confirm ("Keep originals, trash copies"), which collects every unreviewed exact copy across all Inbox pages and uses `POST /api/documents/bulk-trash` in chunks of 100. Only copies whose original is outside Trash are listed (API already hides `duplicate_of` when the original is trashed), so an original is never trashed by this. The copy note now wraps on phones (CSS in the appended round-5 block). |
| 5 | J2 L5 — "nessuno" for a feminine field | `noValue(field)` in DocumentHistory locales: Italian "nessuna" for data / etichette / versione, "—" for custom fields (unknown gender), "nessuno" otherwise. |
| 6 | J1 L6 / J2 L6 — copy history has date only | Copy history JSON adds `by` (Movement.moved_by username; additive). DocumentPanel shows `formatDateTime` (app language) and "by <user>" / "da <user>". |
| 7 | J1 L8 — MCP tags by ID only | `change_document_tags` accepts a tag ID or an exact, case-insensitive name of the owner's tags; a name matching several tags is refused ("Several tags have this name; use the tag ID from list_tags"). Resolution happens before the existing other-agent filter-tag guard, so the guard applies to names too. Tool schema/description updated. |
| J3 M2 | Turning an account off then on revived tokens/agents | `people_views._end_access`: on deactivation, revoke every ApiToken and AgentGrant of the person and delete their sessions. Test: REST token 401, MCP verify None, old browser session 401 after off→on. |
| J3 M1 | Password messages omit agents | PasswordPanel and PeoplePanel success messages mention agents; both forms show a warning before submit ("Changing your password signs out your other devices and disconnects your API tokens and agents"), linked with `aria-describedby`. Turned-off message says tokens/agents are revoked and not restored. EN + IT. |
| J3 L1 | Denied agent call did not name the document | `_call` denied branch records the owner's document when `document_id` is given (unknown/foreign IDs record none). |
| J3 L2 | No Cache-Control on authenticated API answers | `archive.cache_headers.PrivateApiCacheMiddleware` (outermost after SecurityMiddleware): `Cache-Control: private, no-store` on authenticated `/api/` responses without their own header; share-link/bundle `no-store` and page previews' `private, max-age=3600` are kept. |

## API contract / language

- Only additive changes: new route, new optional query parameter `forget`, new `by` field in copy history, new model. `archive/test_api_contract.py` green without regenerating the contract.
- New messages with Italian entries in `archive/messages_it.py`: "Choose a tag, sender, or document type suggestion", "Invalid suggestion ID", "Suggestion not found", "This tag is already on the document. Remove it instead.", "Revoke this agent before removing it", "Several tags have this name; use the tag ID from list_tags". `test_api_language` green.

## NAS impact

None noticeable: one small table, one middleware doing a header check, no new dependencies or images.

## Verification (local, SQLite test settings)

- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` → 338 passed, 14 skipped (zbar / PostgreSQL-only, as before); new file `archive/test_round5_fixes.py` has 9 tests.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` → No changes detected.
- `cd apps/web && npx tsc --noEmit -p . && npm run build` → OK.
- Playwright: new `apps/web/e2e/judge-round5-api.spec.ts` (5 tests × desktop/mobile) written and listed with `npx playwright test --list`; **not run** (shared stack in use). Updated `round2-judge1.spec.ts` (dismiss is now "Reject suggestion …" and persisted server-side) and `round2-navigation.spec.ts` (focus after revoke goes to the "Revoked or expired" summary).

## Files

- API: `archive/models.py`, `archive/migrations/0059_suggestion_dismissal.py`, `archive/views.py`, `archive/classification.py`, `archive/auto_filing.py`, `archive/history.py`, `archive/agent_views.py`, `archive/physical_views.py`, `archive/mcp_server.py`, `archive/people_views.py`, `archive/cache_headers.py` (new), `archive/messages_it.py`, `ripiano/urls.py`, `ripiano/settings.py`, `archive/test_round5_fixes.py` (new).
- Web: `DocumentPanel.tsx`, `AgentPanel.tsx`, `InboxPanel.tsx`, `DocumentHistory.tsx`, `PasswordPanel.tsx`, `PeoplePanel.tsx` and their locale files; `style.css` (one appended commented block at the end).
- E2E: `judge-round5-api.spec.ts` (new), `round2-judge1.spec.ts`, `round2-navigation.spec.ts`.
- Docs: `docs/USER_GUIDE.md`, `docs/AGENT_ACCESS.md`.
