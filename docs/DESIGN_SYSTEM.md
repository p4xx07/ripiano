# Ripiano interface system

Ripiano follows Condivisa's interaction principles: a small number of clear actions, readable hierarchy, forgiving empty states, and one screen for correcting a document. Its palette is its own: warm paper surfaces, a dark olive sidebar, and green actions. The implementation is live React DOM and CSS.

## Source of truth

- Semantic colors, type, spacing, radii, and shadows live in the `:root` block of [`apps/web/src/style.css`](../apps/web/src/style.css). Component rules use those variables; new colors belong in that block rather than in a page-specific selector.
- Shared `Button`, `Field`, and `Modal` components live in [`apps/web/src/ui.tsx`](../apps/web/src/ui.tsx). Use them for standard actions, labelled inputs, and dialogs. `Modal` moves focus inside, traps Tab, closes on Escape or backdrop click, makes the page inert, and restores focus to the invoker.
- Every keyboard interactive control uses the same visible focus ring. The `--color-muted`, `--color-faint`, success, warning, and accent text tokens were darkened for readable small text on the corresponding light surfaces.

## Density rules

The Library shows at most two tags on desktop and one on mobile, followed by a count of hidden tags. The document panel shows the full set. Mobile rows keep source, processing state, and primary retrieval actions visible without a long tag stack. A document is saved immediately; tags remain optional.

## Verification

The PWA production build and six Playwright journeys cover desktop and mobile capture, search, tagging, physical filing, agent permissions, and dialog focus. These are browser checks. Installed PWA and Android device validation remain separate release gates in [`QUALITY_JUDGES.md`](QUALITY_JUDGES.md).
