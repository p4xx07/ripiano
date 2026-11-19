# Optional semantic search — independent review (2026-11-17)

Scope: commit `1042024`; settings, optional storage, indexing, nearest-passage search, MCP scope/filter, and tests.

Evidence: full API baseline: `242 passed, 9 skipped`; inspected `semantic.py`, `semantic_views.py`, `test_semantic.py`, and the docs. Settings default to off. Enabling requires pgvector, and indexing/search use the configured Ollama-compatible endpoint. The API limits Library results to the signed-in owner; MCP applies the grant's allowed-document queryset before returning passages.

No high/medium finding in this scoped pass. Current nearest-passage retrieval takes a bounded candidate set before the agent's filter, so a very narrow grant may return fewer relevant results; this is a recall limit, not a disclosure. Main-Library hybrid ranking is open work. NAS performance remains unmeasured on the DS923+.

Final full API verification after the review fixes: `243 passed, 9 skipped` (`RIPIANO_DEBUG=1 .venv/bin/pytest -q`).
