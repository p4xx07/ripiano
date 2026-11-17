# Object sharing — independent review (2026-11-17)

Scope: commit `3b7e170`; `object_access.py`, `object_access_views.py`, shared document update path in `views.py`, tests, README, and parity row. Reviewed as a separate pass after the commit.

Evidence: full API baseline before fixes: `242 passed, 9 skipped`; new permission test failed before the fix (HTTP 200 where 403 was required); `test_object_access.py` after the fix: `5 passed`. Web type check/build passed.

Finding **HIGH, fixed**: a recipient with document edit access and only other shared sender/type objects could clear or replace the document's existing unshared sender/type. The endpoint checked only the incoming object ID, not the current private value. The update now rejects changes to an unshared current value. The regression covers clear and replace attempts. README and parity wording now state the boundary.

No additional high/medium finding in the inspected grant creation, revocation, owner checks, and tag update path. Real multi-user browser validation remains part of the R4 gate.

Final full API verification after the review fixes: `243 passed, 9 skipped` (`RIPIANO_DEBUG=1 .venv/bin/pytest -q`).
