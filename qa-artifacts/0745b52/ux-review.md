# Ripiano interim clone and design-system fidelity review — `0745b52`

## Scope and evidence inspected

- Target commit: `0745b52` in `/private/tmp/ripiano-plan-20261104`.
- Live-DOM source: `apps/web/src/App.tsx`, `DocumentPanel.tsx`, `TagPanel.tsx`, `PhysicalPanel.tsx`, `AgentPanel.tsx`, and `style.css`.
- Rendered synthetic-stack evidence: `apps/web/test-results/archive-capture-find-tag-and-locate-a-paper-copy-desktop/archive.png` and `apps/web/test-results/archive-capture-find-tag-and-locate-a-paper-copy-mobile/archive.png`.
- Reference principles: Condivisa's reused controls and semantic visual tokens in `/Users/debotta/dbrepos/condivisa/src/ui.tsx:18` and `/Users/debotta/dbrepos/condivisa/src/index.css:12`.

## What is verified

- The application is live React DOM. The screen is composed from DOM buttons, inputs, dialog markup, and Lucide icons; no screenshot/raster image or CSS background stands in for the UI.
- Ripiano has a distinct olive-green/sidebar and warm-paper palette. It does not visually copy Condivisa's teal system.
- The desktop layout is coherent: persistent navigation, constrained content column, search, document rows, and a document detail panel have clear hierarchy.

## Findings

### CRITICAL

None. There is no evidence of pasted screenshot or raster-image substitution.

### HIGH

1. **The CSS is not a token-driven design system.** `apps/web/src/style.css:1-14` defines only raw base values, then the rest of the 1,600-line file repeatedly hardcodes colors, radii, gaps, font sizes, and shadows. Examples include raw dark/sidebar values at `37-123`, button values at `236-259`, search/focus values at `326-352`, modal values at `511-599`, and an additional repeated detail-panel set at `1121-1189`. There are no semantic color, spacing, type, radius, or elevation variables for Ripiano. This makes palette, contrast, density, and component consistency expensive to change and fails the requested rigorous design-system criterion. Condivisa demonstrates the intended baseline through semantic token definitions in `src/index.css:12-91`.

2. **Core controls are styled classes, not reused component primitives.** The six Ripiano TSX files all emit native `button`, form field, alert, header, and dialog markup independently. Search found no shared `Button`, `Modal`, `Field`, `SectionTitle`, or equivalent component in `apps/web/src`. For example, the Add modal is hand-built in `App.tsx:858-923`, while the document detail dialog is hand-built in `DocumentPanel.tsx:159-357`; their close behavior, focus behavior, spacing, and styles are separately implemented. Condivisa centralizes these primitives in `src/ui.tsx:18-48`. This is a structural design-system gap, not merely code cleanup.

### MEDIUM

1. **The mobile library loses scanability with realistic many-tag documents.** In the inspected mobile screenshot, every generated tag remains visible and turns each document row into a very tall column; the Ready/view/download controls sit partway down the tag stack rather than alongside the document title. The render follows `App.tsx:736-782`, which maps every tag, combined with the unconstrained wrapping rule at `style.css:1233-1250` and mobile row styling at `803-819`. A document archive needs a capped tag summary or a progressive “+N” disclosure in the list; full tag detail belongs in the document panel. This directly increases the friction the product is intended to remove.

2. **Dialogs declare `aria-modal` but do not manage focus.** The Add dialog in `App.tsx:858-923` and detail dialog in `DocumentPanel.tsx:159-357` have dialog semantics, but neither moves focus into the dialog, traps Tab, nor restores focus to the invoker. `DocumentPanel.tsx:45-50` only handles Escape. Keyboard users can tab into the obscured page behind the backdrop, violating the expected modal interaction. This also produces different interaction behavior across the two independently built dialogs.

3. **There is no consistent keyboard focus treatment for interactive controls.** The file styles focus for a few inputs (`style.css:338-345`, `678-681`, `1084-1088`) but has no `:focus-visible` rule for the many button, link, select, navigation, row-action, or icon-only controls. The mobile menu, document action buttons, and modal close control are examples in `App.tsx:542-548`, `785-811`, and `871-877`. Their hover treatments are mouse-only. A visible focus ring must be defined as a shared control contract.

### LOW

1. **Rendered-evidence scope is narrow.** The supplied screenshots show a populated Library page only. Tags, physical filing, agents, backups, an empty library, auth, error states, and both dialogs were not visually inspected in a captured run. This is insufficient evidence for a final interface-fidelity gate even once the structural issues are fixed.

## Recommendation

**REQUEST_CHANGES.** The product has a real, original live interface and a promising desktop composition, but it does not yet meet the required rigorous token-driven/reused-primitive standard. Replace the raw CSS approach with Ripiano-owned semantic tokens and common interactive primitives, then fix mobile tag summarization and modal/focus behavior before a UX judge can approve it. This remains an interim review only; it does not assign a 9.5 score because the release hard gates are incomplete.
