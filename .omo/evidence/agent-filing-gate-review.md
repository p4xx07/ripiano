# Agent filing MCP — final gate review

## Recommendation

**APPROVE**, scoped to the uncommitted MCP sender/document-type filing permission. This is not a whole-app parity or 9.5 approval.

## Blockers

None.

## Original intent

Allow multiple named agents, including local models, to receive different permissions and document filters. For this slice, an explicitly authorized agent should be able to file an allowed document by choosing an existing sender or document type, while remaining unable to read OCR text or alter tags unless separately granted. Human and input-rule choices must remain protected, and activity must remain auditable.

## Desired outcome

- A distinct `documents:filing` grant exposes only the sender/type tools.
- Filing choices and target documents remain owner scoped; an optional tag filter still constrains writes.
- Exactly one existing sender or document type is set per call.
- Manual and source-origin choices cannot be overwritten by an agent.
- Agent choices are identifiable as model-origin and survive phrase-rule reclassification.
- Tool use is audited without document text.
- The permission and its data exposure are clear in documentation and desktop/mobile UI.

## User outcome review

The scoped outcome is met. `list_tools` exposes the two filing tools only when the grant contains `documents:filing`. The write path validates the chosen taxonomy item against the grant owner, resolves the target through the grant's owner and optional tag filter, and repeats that document lookup under a row lock. A foreign option, out-of-filter document, conflicting two-field input, or protected manual/source field produces an error and no mutation. Successful writes set `model` origin; phrase rules now preserve it, while the existing human edit path changes it to `manual`.

The owner UI presents sender/type filing as a separate unchecked permission and the connected-agent card displays it. The document form explains model-origin values as “Set by an agent.” `docs/AGENT_ACCESS.md` now accurately discloses that sender/type and tag taxonomy names remain account-wide when their scopes are granted, even when document access is tag filtered. The README lists the added scope without claiming full agent parity. Desktop and 390px mobile evidence is readable and masks the one-time token.

## Artifacts checked

- Current uncommitted product, test, migration, and documentation diff, including `README.md` and `docs/AGENT_ACCESS.md`.
- `.omo/evidence/agent-filing-code-review.md`
- `.omo/evidence/agent-filing-clone-fidelity.md`
- `apps/web/test-results/agents-create-a-limited-agent-and-revoke-its-access-desktop/agents.png`
- `apps/web/test-results/agents-create-a-limited-agent-and-revoke-its-access-mobile/agents.png`

## Independently reproduced evidence

- `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_agents.py -q`: **3 passed**.
- Django system check: **passed**.
- Migration drift check: **No changes detected**.
- PWA production build: **passed**.
- `git diff --check`: **passed**.
- Inspected the executor's full-suite result (**170 passed, 6 skipped**), desktop/mobile browser result (**2 passed**), and live local MCP tool-list/write/readback report as supporting evidence. The synthetic QA accounts were reported and then confirmed removed by the executor.

## Authorization and adversarial review

- Tool discovery and execution both require `documents:filing`; a tag-only grant is denied and audited.
- Owner scoping applies independently to document, correspondent, and document-type IDs.
- The optional tag filter is reapplied after acquiring the document row lock, so a document that leaves the grant cannot be written through a stale pre-lock lookup.
- The schema and runtime both enforce exactly one field. Invalid IDs, both fields, invalid offsets, out-of-filter documents, and foreign-owner choices are covered.
- Manual and source origins are covered separately. Agent/model origin is covered against phrase-rule replacement and subsequent human correction.
- Successful, denied, and failed calls travel through `_call` and create audit outcomes without OCR content.
- Search metadata adds sender/type only; OCR remains behind `documents:text`.
- Account-wide taxonomy disclosure for tag-filtered grants is explicit in `docs/AGENT_ACCESS.md` and matches the implementation.

## Direct anti-slop and programming pass

The named `remove-ai-slops` and `programming` skill files were unavailable. Their supplied criteria were applied directly, and the code-review report explicitly records the same perspective.

The added tests exercise observable authorization, persisted origins, concurrency-sensitive filter rechecking, audit results, and pagination. They are not deletion-only, tautological, prompt-sensitive, or simple mirrors of constants. The production code adds only the permission contract, boundary validation, owner-scoped queries, locking, and origin state required by the feature. No unnecessary extraction, parsing layer, generic abstraction, or untyped escape hatch was introduced.

## Exact evidence gaps

- No browser assertion opens a document after an MCP filing write to verify the “Set by an agent” hint. This is a non-blocking coverage note because persisted origin, API serialization type, and the live hint branch were directly inspected.
- The live MCP proof occurred before the final option-pagination/schema refinement. The final focused tests reproduce runtime validation and pagination, and the tool schema was directly inspected; this is not a blocker.
