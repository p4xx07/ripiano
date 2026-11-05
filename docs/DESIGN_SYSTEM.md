# Ripiano interface system

Ripiano follows Condivisa's interaction principles: a small number of clear actions, readable hierarchy, forgiving empty states, and one screen for correcting a document. Its palette is its own: warm paper surfaces, a dark olive sidebar, and green actions. The implementation is live React DOM and CSS.

## Source of truth

- Semantic colors, type, spacing, radii, and shadows live in the `:root` block of [`apps/web/src/style.css`](../apps/web/src/style.css). Component rules use those variables; new colors belong in that block rather than in a page-specific selector. Spacing uses a compact scale from 1 to 56 px, with 6 and 10 px steps for dense controls. Type has named caption, body, label, subtitle, section, and display roles. Corners use five radius roles.
- Shared `Button`, `Field`, and `Modal` components live in [`apps/web/src/ui.tsx`](../apps/web/src/ui.tsx). Use them for standard actions, labelled inputs, and dialogs. `Modal` focuses the first visible action, traps Tab, closes on Escape or backdrop click, makes the page inert, and restores focus to the invoker.
- Every keyboard interactive control uses the same visible focus ring. The `--color-muted`, `--color-faint`, success, warning, and accent text tokens were darkened for readable small text on the corresponding light surfaces.

## Density rules

The Library shows at most two tags on desktop and one on mobile, followed by a count of hidden tags. The document panel shows the full set. Mobile rows keep source, processing state, and primary retrieval actions visible without a long tag stack. A document is saved immediately; tags remain optional.

## Verification

The PWA production build and browser journeys cover desktop and mobile capture, search, tagging, physical filing, agent permissions, optional follow-ups, and dialog focus. Rendered evidence for the main surfaces is in [`qa-artifacts/65d544b/visual`](../qa-artifacts/65d544b/visual). These are browser checks. Installed PWA and Android device validation remain separate release gates in [`QUALITY_JUDGES.md`](QUALITY_JUDGES.md).
