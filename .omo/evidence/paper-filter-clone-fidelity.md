# Paper-copy filter: clone / design-system fidelity review

## Recommendation

**APPROVE** — scoped score: **9.7 / 10**.

## Evidence inspected

- Uncommitted diff for `apps/web/src/App.tsx`, `apps/web/src/SavedSearchBar.tsx`, `apps/web/src/api.ts`, and the API/test changes.
- [Desktop filter screenshot](../../apps/web/test-results/archive-capture-find-tag-and-locate-a-paper-copy-desktop/paper-filter.png).
- [Mobile filter screenshot](../../apps/web/test-results/archive-capture-find-tag-and-locate-a-paper-copy-mobile/paper-filter.png).
- [Desktop missing-copy screenshot](../../apps/web/test-results/archive-capture-find-tag-and-locate-a-paper-copy-desktop/missing-paper-copy.png).
- [Mobile missing-copy screenshot](../../apps/web/test-results/archive-capture-find-tag-and-locate-a-paper-copy-mobile/missing-paper-copy.png).
- [Shared live field primitive](../../apps/web/src/ui.tsx#L12) and [the existing Library filter grid](../../apps/web/src/style.css#L633).
- Existing design token definitions in `apps/web/src/style.css:1-83`, plus the shared label/control and focus styling at `apps/web/src/style.css:1805-1836`.

## Findings

### CRITICAL

None. The filter is live React DOM: `Field` wraps a native `<select>` in [App.tsx:1258](../../apps/web/src/App.tsx#L1258). No screenshot, raster asset, or CSS background image is used as a substitute for the control.

### HIGH

None. The corrected [PaperCopySummary](../../apps/web/src/App.tsx#L128) partitions located and missing copies. It renders a location only for a copy that is not missing, and renders a distinct text warning for missing copies. The desktop and mobile evidence show the old shelf is absent after marking the only copy missing. The end-to-end test asserts both conditions at [archive.spec.ts:129-139](../../apps/web/e2e/archive.spec.ts#L129).

### MEDIUM

None. The selected value and its scope are legible in the desktop evidence; the explanatory hint makes the deliberately inclusive missing-copy behavior explicit. The mobile grid promotes the first three controls, including Paper copy, to full width at `<=570px` ([style.css:1251-1258](../../apps/web/src/style.css#L1251)), preserving a usable touch target.

### LOW

None.

## Design assessment

The control stays within the established warm-paper / olive-green system, its spacing comes from the shared token set, and its selected state is visually consistent with Tag, From, and Document type. The native select is correctly associated with its label through the shared label wrapper, while the missing-copy note is available inline. The screenshots show a normal rendered page hierarchy and responsive layout, rather than a visual mock-up. The missing-copy state uses the existing warning token and text plus an icon, and retains truthful location information when another copy is still present.

## Blockers

None.

---

## Follow-up: Reported missing filter

**Recommendation: APPROVE — scoped score: 9.8 / 10.**

### Evidence inspected

- Incremental UI/API/test diff after commit `79fd21f`.
- [Paper-copy select](../../apps/web/src/App.tsx#L1275), using the shared native-label `Field` primitive.
- [Desktop](../../apps/web/test-results/archive-capture-find-tag-and-locate-a-paper-copy-desktop/missing-paper-copy.png) and [mobile](../../apps/web/test-results/archive-capture-find-tag-and-locate-a-paper-copy-mobile/missing-paper-copy.png) missing-copy row evidence.
- [Browser journey assertions](../../apps/web/e2e/archive.spec.ts#L129) covering marking a copy missing, removal of the stale location, and selection of the `Reported missing` filter.

### Findings

#### CRITICAL / HIGH / MEDIUM / LOW

None.

`Reported missing` is direct, user-facing language and its placement under `Paper copy` makes its scope clear. The revised hint, “Registered copies include those reported missing,” accurately resolves the potentially confusing relationship between `Has a paper copy`, `Digital only`, and missing copies. It remains a native, label-associated select that reuses existing responsive filter layout and tokens, so it remains keyboard and mobile compatible. The warning row continues to communicate a missing copy without falsely presenting its previous shelf as current.

### Blockers

None.
