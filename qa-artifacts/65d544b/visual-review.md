# Design review evidence after the follow-up checkpoint

This is a browser review of the token and focus changes made after `65d544b`. It is not installed-device certification. The account contains only synthetic test documents and grants.

## Captures

The [desktop](visual/desktop) and [mobile](visual/mobile) folders each contain rendered screenshots of the library, add dialog, empty search, simulated search error, document detail, action list, tags, paper archive, agents, and backups. Mobile is Chromium at 390 × 844; desktop is Chromium at 1440 × 900. The screenshots are viewport captures after data and drawer transitions settled.

## Findings and changes

- Repeated spacing, font sizes, and radii now use the scale in `apps/web/src/style.css`; an audit found zero raw `px` values in `gap`, `padding`, `margin`, `border-radius`, and `font-size` declarations outside `:root`.
- Dialog entry focuses the first visible action. The close control has an explicit ring on focus, including pointer-opened dialogs. Keyboard trapping, Escape, and focus restoration are covered by `dialog-focus.spec.ts`.
- Mobile action rows place **Done** below the title, date, and note. The title can wrap rather than being cut off by the button.
- A failed document search shows the error and Retry, without the misleading “Nothing found” empty result. The failure screenshot uses a synthetic HTTP 503 from the browser harness.
- The settled mobile screenshots show the navigation drawer closed, and the library after its document request. Earlier captures taken during the drawer transition were discarded.

## Verification

- `npm run build`: passed.
- Local Compose web/API rebuild: passed; API healthy.
- `npm run test:e2e` against the local synthetic stack: 10 passed across desktop and mobile, including the visual capture journey.
- Visual inspection: mobile and desktop library, add dialog, action list, detail panel, search error, tags, agents, and paper archive were opened from the captures. No clipping or obstructed primary controls observed in those viewport captures.

This evidence does not cover iOS installed PWA behavior, physical Android scanner hardware, Synology storage ACLs, or the remaining Paperless feature parity gates.
