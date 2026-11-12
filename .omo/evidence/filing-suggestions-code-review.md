# Filing suggestions code review

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
