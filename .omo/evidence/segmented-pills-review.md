# Short choices as pills: review (2026-11-25)

## Scope

Owner request: fixed choices with 2–4 short options become one-click pills instead of selects. New `Segmented` component (`apps/web/src/ui.tsx`): native radios under pill labels in a named `role="radiogroup"`, arrow-key navigation, visible focus ring, check mark on the selected pill, 36px with a mouse and 44px on touch, smaller text (owner follow-up). Pills are separate chips that wrap; the sidebar uses a single-row track, with theme as four icons (accessible names and tooltips kept) and language as Auto / English / Italiano. 20 selects converted (theme, language, Library paper and yes/no filters, custom-field value and type, access level, task state in owner and shared document, email attachment version, mail security / import / after-import / match field, share-link duration, OCR language, workflow yes/no and sharing). Kept as selects: options from user data, long labels (S3 address style, workflow triggers and date fields), five-option match modes and token/bundle choices, the dense custom-field manage row. No new dependency, no API change.

## Independent review (Opus 5.5)

No High findings.

- **Medium, fixed:** sidebar pills stayed 32px on touch screens (a later rule overrode the touch size). A touch-size rule for the sidebar was added, with a phone test that measures every theme and language pill.
- **Low, fixed:** the hint was read twice (visible text and `aria-describedby`); it is now hidden from screen readers like `Field`'s hint.
- **Low, fixed:** Enter on a pill inside a form could submit it; Enter is now ignored on pills, as on the old selects.
- **Low, fixed:** the sidebar settings block grew taller; in the compact sidebar the visible labels are hidden (group names kept as `aria-label`).
- **Low, fixed:** sidebar language labels could break mid-word at large text sizes; they no longer wrap inside a pill.
- **Low, open:** the custom-field yes/no label no longer focuses a control on click; its group name is still correct through `aria-labelledby`.

## Verification

- `tsc --noEmit` and `npm run build`: pass.
- Full browser suite on a throwaway stack: 413 passed, 23 failed, 50 skipped. 21 failures are the pre-existing set recorded in `location-path-server-neutral-review.md`; the two new ones were outdated tests (old select in `judge-round10`, 40px expectation in `segmented.spec.ts`) and pass after the update.
- After the review fixes, the affected specs (`segmented`, `appearance`, `navigation-a11y`, `round5-web`, `round2-navigation`, `actions`, `custom-fields`, `people-sharing`, `share-links`, `archive`, `judge-round10`): 104 passed, 0 failed.
- Screenshots checked at 1280×800 (EN, IT, filters open) and 360×760 phone menu (IT).
