# Agent filing MCP code review

## 2026-11-13 scoped review

**Verdict:** `CLEAR` / **APPROVE**, limited to the uncommitted MCP sender/type filing permission.

## Scope inspected

- `services/api/archive/mcp_server.py`: tool exposure, grant scope enforcement, owner/tag-filter scoping, option pagination, field validation, write locking, origin handling, and audit path.
- `services/api/archive/agent_views.py`, `models.py`, and migration `0036`: public grant scope validation and durable `model` filing origin.
- `services/api/archive/classification.py`: phrase-rule precedence after an agent filing decision.
- `services/api/archive/test_agents.py`: unauthorized access, resource filtering, ownership, conflicting inputs, user/input protection, model precedence, pagination, and audit coverage.
- PWA permission copy/types, browser scenario, and accompanying architecture/parity documentation.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Correctness and security notes

- Tool discovery is scope-gated in `mcp_server.py`; a grant without `documents:filing` cannot list filing options or set either field. The new tool is separately selectable in the owner UI and accepted by the grant API only as an explicit scope.
- The write path first validates the target sender/type belongs to the grant owner, then re-queries the document through the owner and optional tag filter while holding a document row lock. A grant cannot write another owner’s metadata or an out-of-filter document, and a changed tag filter is rechecked inside the transaction.
- The tool requires exactly one filing field both in its MCP JSON schema and at runtime. Inputs with a foreign UUID, two choices, an invalid offset, or a protected field fail without a mutation.
- Human (`manual`) and input/workflow (`source`) decisions are protected from the agent. Agent values use the durable `model` origin; classification phrase rules now preserve that origin, while normal human edits still convert it to `manual`.
- `search_documents` adds preloaded sender/type metadata without adding OCR access. This remains consistent with the existing tool description that permits filing metadata, while OCR text still requires `documents:text`.
- The 200-item option pages have stable model ordering and a single offset correctly carries the longer of the sender/type sequences. No item is skipped when a client accumulates the pages.
- Audit entries remain produced by `_call` for successful, denied, and failed tool calls. No document OCR content enters the audit row.

## Independent verification

- `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_agents.py -q`: **3 passed**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py check`: **passed**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`: **No changes detected**.
- `npm run build` in `apps/web`: **passed**.
- `git diff --check`: **passed**.
- The executor's full API report (**170 passed, 6 skipped**) and desktop/mobile Agent-panel journey (**2 passed**) were inspected as supporting evidence. The focused API and build checks above were reproduced independently.

## Skill-perspective review

The requested `remove-ai-slops` and `programming` skill files were not available in the listed local skill roots: the direct filesystem search returned no matching `SKILL.md`. Their stated criteria were applied directly. The tests exercise permission boundaries, actual persisted origin behavior, and page behavior; they are not deletion-only, tautological, or implementation-constant assertions. The added production logic is restricted to the explicit MCP contract, validation at the external boundary, and the necessary model-origin precedence. No brittle prompt test, untyped escape hatch, needless abstraction, or unnecessary parsing/normalization was found.

## Blockers

None.
