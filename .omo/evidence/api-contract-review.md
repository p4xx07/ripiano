# API v1 contract — independent review (2026-11-17)

Scope: commit `6f5913e`; recorded scenario, schema generator, compatibility rules, API documentation.

Evidence: full API baseline before fixes: `242 passed, 9 skipped`. New type tests failed before the fix; `test_api_contract.py` after the fix: `3 passed`. The recorded scenario and OpenAPI publication remained green.

Finding **MEDIUM, fixed**: `breaking_changes` accepted a response field that gained an additional type, or became null, whenever the old type still appeared somewhere in the scenario. A client expecting the original type could break. It now rejects newly observed types and missing promised non-null types; a field previously observed only as null may acquire a concrete type. Regression cases cover all three paths. README now describes this compatibility rule.

Limit: the contract covers the 40 recorded operations and shapes observed by its scenario, not every optional field or error response. That is consistent with the stated v1 contract, but R4 still needs wider route/behavior checks.

Final full API verification after the review fixes: `243 passed, 9 skipped` (`RIPIANO_DEBUG=1 .venv/bin/pytest -q`).
