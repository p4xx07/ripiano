# Agent filing permission — clone-fidelity review

**Recommendation:** APPROVE, scoped to the uncommitted agent sender/type permission and agent-origin disclosure.

## Evidence inspected

- Product components: `apps/web/src/AgentPanel.tsx` and `apps/web/src/DocumentPanel.tsx`.
- Types: `apps/web/src/api.ts`.
- Shared styles and responsive/focus rules: `apps/web/src/style.css`.
- Browser journey: `apps/web/e2e/agents.spec.ts`.
- Rendered evidence:
  - `apps/web/test-results/agents-create-a-limited-agent-and-revoke-its-access-desktop/agents.png`
  - `apps/web/test-results/agents-create-a-limited-agent-and-revoke-its-access-mobile/agents.png`
- Executor evidence that the browser scenario passed in desktop and mobile, and that API/build checks passed. The review independently inspected the live DOM source and CSS rather than relying only on those claims.

## Findings

### CRITICAL

None. The permission control is a live checkbox nested in a semantic `fieldset` with a `legend` in `apps/web/src/AgentPanel.tsx:280-291`; the agent list is live grant data at `apps/web/src/AgentPanel.tsx:183-227`; and the model-origin explanation is live form help in `apps/web/src/DocumentPanel.tsx:492-505`. No image, screenshot, canvas, or background graphic substitutes for interface.

The neutral green rectangle in the supplied captures is Playwright's explicit mask over the secret one-time token, verified in `apps/web/e2e/agents.spec.ts:42-45`. It is evidence redaction rather than product UI.

### HIGH

None. The new checkbox reuses `agent-scope-choice`, the panel keeps the existing responsive grid/card hierarchy, and model-origin filing uses the existing `Field`/select controls. The desktop and 390px mobile captures show the new permission chip, checkbox, form, token card, agent card, and revoke control as live layout elements.

### MEDIUM

None. Colors, spacing, typography, radii, and focus treatment are token driven: the new permission reuses `scopeNames` in `apps/web/src/AgentPanel.tsx:25-30`, `agent-scope-choice` in `apps/web/src/style.css:2672-2684`, and the global keyboard focus contract in `apps/web/src/style.css:3000-3004`. The existing 1050px and 570px responsive rules preserve a readable mobile flow.

### LOW

- The browser journey verifies creation, rendering, token masking, and revocation of the new permission, but does not open a document with `model` origin to assert the new “Set by an agent” help copy. The source is direct and uses the established `Field` markup; this is a small regression-coverage gap, not a fidelity blocker. See `apps/web/src/DocumentPanel.tsx:492-505`.

## Conclusion

The slice extends the existing green/paper design through real React components and shared token-driven CSS. Native labeled controls expose the permission, cards expose the resulting grant, and durable screenshot evidence redacts the one-time token without changing the UI. No scoped design blocker remains.
