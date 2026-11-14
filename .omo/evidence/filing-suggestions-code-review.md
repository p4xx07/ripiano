# Filing suggestions code review

## 2026-11-13 incremental one-tap acceptance review

**Verdict:** `CLEAR` / **APPROVE**, scoped to the uncommitted one-tap acceptance change.

### Scope inspected

- `services/api/archive/views.py`: owner-scoped `add_tag_id` PATCH input, tag-limit enforcement, override clearing, idempotent manual tag creation, and updated-workflow triggering.
- `apps/web/src/DocumentPanel.tsx`: immediate persistence for tag, sender, and type suggestions while preserving unsaved fields in the open form.
- `apps/web/e2e/filing-suggestions.spec.ts`, `services/api/archive/test_classification.py`, and the disabled-state CSS.

### Findings

None. The earlier LOW coverage follow-up is resolved: the browser journey now creates a manually filed sender and type, proves both appear as suggestions from the same source document, accepts each in turn, verifies its immediate API/UI persistence, and confirms the edited draft title remains unsaved until the normal Save action.

No CRITICAL, HIGH, or MEDIUM finding. The row lock on `Document` serializes the add-tag capacity check with normal document PATCH and bulk-tag writers. The endpoint validates tag ownership, rejects mixed replacement/add semantics, stays idempotent, removes only the matching override, and returns fresh document data after workflow processing. The panel reconciliation retains unsaved tag, sender/type, and scalar drafts instead of overwriting them with the immediate-save response.

### Test and skill-perspective check

- Independently ran `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_classification.py -q` from `services/api`: **15 passed**.
- Independently ran `npm run build` from `apps/web`: **passed**.
- `git diff --check`: **passed**.
- The executor’s reported full suite (**168 passed, 6 skipped**) and the expanded desktop/mobile browser test (**2 passed**) were inspected as supporting evidence; they were not treated as substitutes for the focused checks above.
- `remove-ai-slops` and `programming` skill files were not present in the advertised local skill roots, so their review criteria were applied directly. The added tests are behavior-focused, exercise owner isolation and draft preservation, and do not merely mirror implementation constants. The production change adds only the API boundary needed for atomic tag addition; no needless parsing, data extraction, abstraction, or untyped escape hatch was found.

### Blockers

None.

---

Independent read-only code judge verdict, transcribed from its completed agent report: **APPROVE**, no critical or high findings. Scope: `GET /api/documents/<id>/filing-suggestions` (`archive/classification.py`, `views.py`, `urls.py`, tests), and the document-panel UI, types, styles, and browser journey.

## Evidence independently checked

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_classification.py`: 11 passed.
- `manage.py check`: no issues. `npx tsc --noEmit`: clean. Django 5.2.19.
- Compiled the candidate queryset for SQLite and PostgreSQL. The slice-then-annotate chain is one valid statement; PostgreSQL's DISTINCT + ORDER BY rule is satisfied; the slice is kept.
- Five fixed queries, with no N+1. Owner isolation holds in the view (404 for foreign or trashed documents) and for candidates and tag links. The code writes nothing.
- Setting or clearing a sender or type marks its origin as manual, so explicit choices suppress suggestions correctly.

## Findings and resolution

| Severity | Finding | Resolution |
| --- | --- | --- |
| MEDIUM | The join plus `DISTINCT` over tag links grows with archive size, not with the 300-row cap. | Replaced with an `Exists` filter and removed `.distinct()`. |
| LOW | There is no stopword list, so filler words could count as evidence. | Added a small English/Italian stopword set and a test. |
| LOW | Coverage gaps: existing tag, cleared document type, foreign or trashed sender, query bound. | Added a test covering all four, with at most 8 queries. |
| LOW | The e2e assertion `sourceId != targetId` is tautological. | Replaced with an API check that the suggestion's example is the source document. |
| LOW | Fetch errors are swallowed silently. | Accepted: the suggestion box is optional, and failure just hides it. |

## Follow-up after review

Browser screenshots from the reused test account showed sender and type suggestions based only on fixture boilerplate ("ripiano", "judge", "mobile"). Words found in more than max(4, 25%) of the compared examples are now ignored as evidence. A test covers this. After the change, the API suite passed 81 tests with one PostgreSQL-only skip.
