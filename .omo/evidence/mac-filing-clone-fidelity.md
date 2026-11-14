# Optional Mac local classifier sender/type filing — clone fidelity review

## Scope reviewed

Uncommitted extension of Ripiano's optional Mac local Ollama worker. It adds sender and document-type decisions alongside the existing tag path, with separate MCP grant scopes and separate write settings. This is a documentation and local-worker surface; no PWA component or rendered visual was changed.

## Evidence inspected

- Live worker control flow and schema validation in `agents/local_classifier/classify.py:105-259`.
- Live MCP grant labels and enforcement in `services/api/archive/agent_views.py:13-18` and `services/api/archive/mcp_server.py:17-61, 216-242`.
- Operator setup and privacy/consent copy in `agents/local_classifier/README.md:3-29`.
- Product and parity wording in `README.md:150-160`, `docs/ARCHITECTURE.md`, and `docs/FEATURE_PARITY.md:26`.
- Design-system source of truth in `docs/DESIGN_SYSTEM.md`; it does not apply to this non-visual incremental surface.
- Fresh focused worker verification: `uv run python -m unittest -q test_classify.py` — 6 passed. The exercised output confirms a sender/type dry run, a separately enabled filing write, and a later stateful no-op.
- Final stale-read guard in `services/api/archive/test_agents.py`: an agent proposal based on an empty field is rejected if a human or input rule filled it before the write.

## Findings

### CRITICAL

None. The change adds no image, canvas, screenshot, `background-image`, or page-specific visual substitute. The existing agent setup remains a live permission model rather than a visual mock.

### HIGH

None. The new scope maps to the same existing MCP `documents:filing` capability that exposes only existing choices and rejects replacement of human or input-rule values. The worker requires both list/set tools before it can offer or apply sender/type values, and its `auto_apply_filing` setting is independent from tag writes. Its `only_if_empty` request is enforced inside the locked MCP write, so a field filled after the worker’s search remains intact.

### MEDIUM

None. The setup copy gives a direct mapping from Ripiano's visible grant labels to the two independent worker write controls, keeps both disabled in the supplied configuration, and states the local-only default and remote-model opt-in.

### LOW

None. The operator copy now distinguishes the 20,000 OCR characters fetched over MCP from the at-most 12,000 sent to the local model.

## Assessment

`recommendation`: **APPROVE**

Scoped UX/product score: **9.7/10**. The worker is deliberately console and configuration driven, so a new React component or visual artifact would not be appropriate. Its documentation exposes the meaningful permissions and consent boundary in the same terms used by the live agent-grant surface, and the final locked only-if-empty guard matches the promise that it will not overwrite an already filled field.

`blockers`: None.
