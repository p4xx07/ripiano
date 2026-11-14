# Mac local classifier sender/type filing code review

## Scope reviewed

Uncommitted extension of `agents/local_classifier` allowing an optional local Ollama worker to suggest and apply existing correspondents and document types through MCP, behind a separate `auto_apply_filing` setting.

## Independent verification

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_agents.py -q` — **5 passed**.
- `uv run python -m unittest -q test_classify.py` — **6 passed**.
- `git diff --check` — passed.
- Inspected the worker's live MCP contract, locked filing setter, state persistence, and existing agent permission tests.

## Findings

### CRITICAL

None.

### HIGH

None. The prior stale-read blocker is resolved: `only_if_empty` is typed in the MCP schema and checked while the document row is locked (`services/api/archive/mcp_server.py:220-238`), and the worker sends it on every sender/type write (`agents/local_classifier/classify.py:239-250`). The new regression covers both intervening `MODEL` and `LEARNED` values.

### MEDIUM

None.

### LOW

None. The 200-sender/type operational ceiling is now stated in `agents/local_classifier/README.md`.

## Skill-perspective check

`remove-ai-slops` and `programming` skill files were not available in the listed skill roots, so their review criteria were applied directly. The tests exercise consent, choice validation, stale-write protection, and state reuse rather than merely repeating implementation constants. The fingerprint/state table, JSON schema, response validation, and `processed_at` metadata are justified by the remote-model/MCP boundary. I found no deletion-only tests, tautological tests, untyped escapes, needless abstraction, or unnecessary production parsing.

## Incremental conflict-handling re-review

The post-`5b8dfb9` change handles only the atomic `only_if_empty` conflict as nonfatal. `call()` requires an explicit expected error string and exact match before accepting an MCP error; malformed and other errors still raise. The worker records the conflict, continues with later documents, and stores its fingerprint so it does not repeat a resolved concurrent-fill conflict.

Fresh verification: `uv run python -m unittest -q test_classify.py` — **8 passed**; `git diff --check` — passed. The new tests cover explicit error matching, malformed null error rejection, and continuing from one concurrent-fill conflict to a later document. This is behavior-focused coverage, with no new overfit or scope concern.

## Assessment

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- Scoped score: **9.5/10**
- `blockers`: None.
