# Optional Mac classifier sender/type filing — final gate review

## Recommendation

**APPROVE — scoped score 9.8/10**

## Original intent

Allow the optional scheduled local Mac agent to classify Ripiano documents beyond tags by filling sender and document type through MCP, while keeping document content local by default and preserving separate per-agent permissions and explicit write consent.

## Desired outcome

- A locally hosted Ollama model can choose only existing Ripiano tags, senders, and document types.
- Search, OCR-text, tag-changing, and sender/type-filing remain separately granted MCP capabilities.
- Tag writes and sender/type writes remain independently disabled until explicitly enabled.
- Existing sender/type choices are not overwritten, including when another agent or the learned model fills a field after the worker reads it.
- Unchanged documents are not repeatedly sent to the local model on every scheduled run.
- Operator documentation states privacy boundaries, confidence limitations, prompt limits, and taxonomy limits accurately.

## User outcome review

The scoped outcome is satisfied. The worker discovers its effective capabilities from the granted MCP tool list, requires search plus OCR text, and can operate with tag filing, sender/type filing, or both. `auto_apply` and `auto_apply_filing` default independently to false. A non-loopback model endpoint is rejected unless `RIPIANO_ALLOW_REMOTE_MODEL=1` is explicitly configured, so the default path does not send OCR text to a hosted provider.

Sender/type model output is constrained by an Ollama JSON schema to IDs from the account's existing choices, then revalidated for ID membership, numeric confidence, and an exact OCR-text evidence substring. Only decisions at or above 0.9 self-reported confidence are eligible. Already-filled fields are excluded from the prompt. Every worker write sends `only_if_empty=true`; the MCP server checks the field after locking the document row, preventing stale proposals from replacing intervening MODEL, LEARNED, MANUAL, or SOURCE values.

The local SQLite state stores document IDs and fingerprints, not OCR text. The fingerprint uses the configured model name, title, OCR processing timestamp, current filing fields, and available choices. A completed unchanged run skips the later OCR-text fetch and model call, while OCR reprocessing, title changes, filing changes, taxonomy changes, or a model-name change make the document eligible again.

The documented 200-sender/type limit and 20,000-character MCP fetch / 12,000-character model prompt match the implementation. The self-reported confidence limitation is disclosed.

## Independent evidence

- `RIPIANO_DEBUG=1 ./.venv/bin/pytest -q` in `services/api` — **197 passed, 9 skipped**.
- `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_agents.py -q` — **5 passed**.
- `uv run python -m unittest -q test_classify.py` after the concurrent-agent continuation follow-up — **8 passed**.
- `git diff --check` — passed.
- `python3 -m py_compile agents/local_classifier/classify.py agents/local_classifier/test_classify.py` — passed.
- `omo ulw-loop status --json` was unavailable because the installed OMO runtime target is missing, so this report uses the documented fallback evidence path.

## Checked artifacts

- `agents/local_classifier/classify.py`
- `agents/local_classifier/test_classify.py`
- `agents/local_classifier/README.md`
- `services/api/archive/mcp_server.py`
- `services/api/archive/test_agents.py`
- `services/api/archive/agent_views.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/FEATURE_PARITY.md`
- `.omo/evidence/mac-local-filing-code-review.md`
- `.omo/evidence/mac-filing-clone-fidelity.md`

## Adversarial and permission checks

- Invented sender/type IDs are rejected by both schema and post-response validation.
- Invalid, missing, too-long, or non-verbatim evidence is rejected.
- Low-confidence decisions do not write.
- Sender/type auto-apply without the filing grant fails before document processing.
- A set field is excluded from available choices and cannot be replaced by the worker.
- A stale proposal is rejected atomically if MODEL or LEARNED filing arrives between search and write; existing MCP tests cover MANUAL and SOURCE protection.
- The exact locked `This filing field already has a value` MCP response is counted as an already-filled field and processing continues to later fields and documents. Every other MCP failure remains fatal.
- Agent tag filters and owner-local filing-option lookup remain enforced by the MCP server.
- A remote model URL requires explicit opt-in; the agent token file must be mode 0600.

## Direct programming and slop/overfit review

The referenced code-review report explicitly covers the programming and anti-slop criteria, and the final code resolves its former atomicity blocker. I independently inspected the production diff and tests. The added tests exercise observable behavior: independent consent, exact-evidence and choice validation, omission of already-set fields, persisted no-repeat behavior, typed MCP input, stale-write rejection for both model-origin classes, exact error discrimination, and continuation to a later document after a benign conflict. They are not deletion-only, tautological, or mere mirrors of implementation constants. The SQLite fingerprint table, JSON-schema constraint, `processed_at` response field, locked compare-and-set option, and narrow `allowed_error` branch each support a stated state, trust-boundary, or concurrency requirement; none is unnecessary extraction or parsing. The conflict tests specifically prove that the allowlist is not a general error suppressor: the same response remains fatal without the exact allowlist, a different allowed string remains fatal, and a malformed `{"error": null}` response remains fatal when no allowlist was supplied.

## Blockers

None.

## Exact evidence gaps

- No live Ollama/MCP end-to-end run was recorded for this increment; focused tests use a realistic mocked Ollama response and the real MCP domain logic. This is a nonblocking coverage note because the scope's protocol, permission, validation, and concurrency contracts are reproduced independently, and no real-model accuracy claim is made.
- The model's confidence is explicitly uncalibrated. This limits classification quality but is disclosed and does not violate the scoped optional-worker criteria.
- No live Ollama/MCP end-to-end run was added for the conflict-continuation follow-up. The focused worker test reproduces the MCP error payload and verifies that a second document is still written, while the separate real MCP domain test verifies that the locked server emits that exact error. This remains a nonblocking evidence note.

## Follow-up re-audit

The prior throughput note is resolved. The worker's MCP wrapper accepts an error only when the caller explicitly supplies a non-null exact expected message and the structured error payload matches it. The filing loop uses this only for the locked `only_if_empty` conflict, counts that field as already filled, and continues. Unexpected authorization, transport, validation, owner-scope, malformed-null, or server errors still raise `RuntimeError` and stop the run. The README now describes the continuation behavior accurately.
