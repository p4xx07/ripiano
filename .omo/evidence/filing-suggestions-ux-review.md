# Filing suggestions UX review

Independent read-only UX judge verdict, transcribed from its completed agent report: **REQUEST CHANGES**, no high findings. Scope: the "Suggested from your documents" box in the document dialog (`DocumentPanel.tsx`, `.filing-suggestions` styles, browser journey). A concurrent suite run had cleared the screenshots, so the judge reviewed the code only. The primary agent recaptured and inspected the screenshots after making the fixes.

## Findings and resolution

| Severity | Finding | Resolution |
| --- | --- | --- |
| MEDIUM | Keyboard focus is lost after a suggestion is accepted, and nothing is announced. | Focus now moves to the changed field (tag checkbox, From or Type select). A polite status region says, for example, "Sender set to X. Save to keep it." The browser journey asserts both. |
| MEDIUM | Long titles with no spaces can overflow on mobile. | Added `min-width: 0; overflow-wrap: anywhere` to the button and its explanation text. |
| MEDIUM | "Add sender/type" clashes with the existing create buttons, and the box sits far from the fields it changes. | Buttons now read "Add tag:", "Set sender:", "Set type:". The box moved above the From field. |
| LOW | The accessible name includes all the explanation text. | Each button has an explicit `aria-label`; the explanation is linked with `aria-describedby`. |
| LOW | The box has no real heading, and icons appear only on tag suggestions. | The box now has an `h3` heading with `aria-labelledby`, and sender and type have Building2/FileText icons. Icons stay inline when labels wrap. |
| LOW | Explanation text is 10px. | Raised to `--type-small` (11px). Labels use `--type-body` like tag choices. |

## Re-check

The final desktop (1440px) and mobile (390px) captures of the journey show one relevant tag suggestion with the source title and shared words, the icon inline, and no overflow. The desktop and mobile journeys both passed on the rebuilt stack.
