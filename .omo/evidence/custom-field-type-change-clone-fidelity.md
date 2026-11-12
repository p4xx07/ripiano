# Custom-field type-change clone / design-system review

## Recommendation

**APPROVE**

## Evidence inspected

- Live React implementation: `apps/web/src/CustomFieldsPanel.tsx`.
- Shared dialog and button primitives: `apps/web/src/ui.tsx` and shared CSS rules in `apps/web/src/style.css`.
- Type-change additions: `apps/web/src/style.css:2016-2057`.
- Real browser journey: `apps/web/e2e/custom-field-type-change.spec.ts`.
- Rendered desktop and mobile evidence:
  `qa-artifacts/20261112-custom-type/{desktop,mobile}/{blocked,complete}.png`.

The change is rendered by the existing `CustomFieldsPanel`, `Button`, and portal-backed `Modal` components. It does not use a screenshot, canvas, background image, or other raster substitute for interface content. The screenshots agree with the source: the dialog, blocker text, disabled confirmation, type selector, and completion state are live DOM controls.

## Visual and system review

- The edit stays inside the existing Custom details hierarchy. The management disclosure leads to an inline type selector, then to the same shared confirmation-dialog layer used elsewhere in the app.
- Colors, typography, radii, spacing, focus treatment, dialog scrim, and destructive blocker treatment use existing semantic variables and shared primitives. The desktop and 390px mobile captures retain readable wrapping, a visible close control, and a distinct Cancel route.
- The preview gives the user the relevant decision context: affected-value count, examples of normalization, invalid values, affected saved searches, and an enabled confirmation only when the change can proceed.

## Findings

### LOW — New selector width is a one-off layout constraint

`apps/web/src/style.css:2022-2029` adds `min-width: 8rem` for the inline type selector. The value is limited to a practical control width and does not create a competing color, typography, or spacing system. It would be better as a semantic control-width token if this compact selector layout is reused elsewhere.

## Blockers

None.
