# Exception-only Inbox evidence

Base checkpoint: `99dce70`. The Inbox lists failed OCR and unreviewed exact copies; other uploads stay in the Library. A copy review records a timestamp and removes only the Inbox exception. Both originals remain saved. Retry returns a failed OCR document to processing.

## Verification

- `RIPIANO_DEBUG=1 uv run pytest -q`: 26 passed. The Inbox API test covers normal, duplicate, failed, foreign-owner, reviewed, reopened, and retried states.
- `npm run build`: passed. `makemigrations --check --dry-run` and Django system check passed; migration `0011` adds the review timestamp.
- Local Compose rebuild: API and web healthy. Full Playwright run: 16 passed across desktop and mobile, including a real duplicate upload/keep-both journey and a simulated failed-OCR retry UI journey.
- Rendered [desktop](inbox/desktop/inbox.png) and [mobile](inbox/mobile/inbox.png) Inbox captures were inspected after the navigation transition settled. The primary controls are visible and the mobile rows wrap without horizontal clipping.

The account contains synthetic QA documents, so many exact-copy exceptions appear in the captures. This does not claim a calibrated fuzzy-duplicate detector, Android hardware capture, installed PWA behavior, or full Paperless parity.
