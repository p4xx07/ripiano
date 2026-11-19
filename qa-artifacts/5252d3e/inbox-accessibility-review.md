# Inbox judge follow-up

Base commit: `5252d3e`.

The code judge cleared the exception-only Inbox for owner isolation, signed pagination, duplicate review, retry, and test coverage. The UX judge requested a focus and announcement fix after a resolved row disappears, plus rendered evidence for failed OCR on desktop and mobile.

The Inbox now moves focus to the first remaining exception title, or to the empty-state heading, after a successful Keep both or Try OCR again action. A persistent polite status region announces what happened. The browser tests activate both actions with Enter and assert the destination focus and announcement.

## Verification

- `npm run build`: passed.
- Rebuilt local Compose web stack: API and web healthy.
- Full Playwright suite: 16 passed across desktop and mobile. Four Inbox journeys include keyboard activation/focus and live-region assertions.
- Inspected rendered exact-copy and failed-OCR screenshots for [desktop](inbox/desktop/failed-ocr.png) and [mobile](inbox/mobile/failed-ocr.png). The failed-OCR error and retry action are visible on both sizes without horizontal clipping.
- The previous commit's two GitHub Verify and publish runs completed successfully. This follow-up still requires its own CI run after push.

The failed-OCR screenshot uses a mocked failed document response to isolate presentation; the API retry transition is separately covered by a database test. Installed PWA and Android hardware capture remain outside this evidence.
