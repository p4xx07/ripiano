# Round 4 — fixes for judge 2 findings (plus judge 3 M1 / M2-UI)

Source reports: `.omo/evidence/judge-2-round-4-report.md`, `.omo/evidence/judge-3-round-4-report.md` (items A and B relayed by the coordinator).
Branch `codex/initial-implementation`, not committed. No dependencies, Docker, or stack restarts. No Playwright run against http://localhost:18080.

## Items

| Item | Status | Change |
| --- | --- | --- |
| J2 M1 Trash focus / confirmation / Undo | Fixed | `DocumentPanel.tsx`: "Confirm move" gets focus when the confirm step appears; Cancel returns focus to "Move to Trash". `onTrashed(document)` now passes the document. `App.tsx`: a polite live region (`.trash-undo-region`, `aria-live="polite"`, no `role=status` so existing strict `getByRole("status")` specs are unaffected) says "Moved “title” to Trash." with **Undo** (`POST /api/documents/<id>/restore`) and Dismiss. After the dialog closes and the list reloads, focus goes to the row now in the trashed row's place (or the screen `h1` when the list is empty or another screen opened it). After Undo, focus goes to the restored row (or the `h1`). Failed Undo says to restore from Trash. `ui.tsx` `Button` now accepts `ref` (React 19 prop). |
| J2 M2 drawer focus trap | Fixed | `App.tsx`: while the narrow-screen drawer is open, `main` and the skip link are `inert`, and Tab / Shift+Tab cycle inside `#app-sidebar`. Esc / close / backdrop focus the menu button only after the drawer has closed (otherwise the button is still inert). |
| J2 M3 damaged file message | Fixed | `storage.py`: when no reader accepts the contents, a `.pdf` name gives "This file could not be read as a PDF. It may be damaged, or it is not really a PDF." and `.png/.jpg/.jpeg` give the image equivalent; other names keep the "Use PDF, JPEG, PNG…" message. Office/email already had specific messages. Italian in `messages_it.py`. |
| J2 M4 offline reload | Fixed | `App.tsx`: on a successful session check the username (only) is stored in `localStorage["ripiano.lastSignedIn"]`; cleared when the session is unauthenticated (sign-out, session ended). If `/api/session` fails with status 0 or 502–504, an offline screen shows "You're offline", who last signed in on this device, how many files wait in that person's upload queue (IndexedDB count only, no names or contents), and Try again; it retries on `online` and every 15 s, then opens the app normally. The sign-in form is not shown. No document data is cached. |
| J2 L1 lists | Fixed | Agent activity feed is `<ul>/<li>` with `<time>`; paper-copy history is an `<ol>` (`aria-label` "History of paper copy CODE") with `<time>`. |
| J2 L2 320 px overflow | Fixed | `style.css` `@media (max-width: 400px)`: `.page-heading` wraps, `.button` may wrap its label (`white-space: normal; max-width: 100%`), form controls in page content can shrink. Mock-measured at 320 px (en + it): `/backups` 337→320, `/paper` 328→320, `/agents` 320 (incl. new-token card and revoke confirm). |
| J2 L3 Agents touch targets | Fixed | `@media (pointer: coarse)`: Agents permission rows and semantic-mode choices are ≥ 44 px tall with a 24 px control (measured 44–63 px rows, 24 px inputs). |
| J2 L4 filename search for email documents | Not done | Not in scope of this pass. |
| J2 L5 Inbox duplicate discard | Not done | Not in scope of this pass. |
| J2 L6 wording / ASN name | Fixed | English now says "marked missing" everywhere (badge, Library card, Paper archive, status); Italian says "segnalata come mancante / ritrovata" everywhere, including the server history notes ("Marked missing"/"Marked found" translations in `messages_it.py`). The ASN input is named "Archive number (ASN)" via `aria-labelledby` and its hint is `aria-describedby`. |
| J2 L7 MCP errors English | Left as is | MCP tool errors stay English on purpose: agents, not people, read them. |
| J3 M1 (A) image decompression bomb | Fixed | `storage.py`: explicit cap `MAX_IMAGE_PIXELS = 50_000_000` (≈150 MB RGB; an A4 page at 600 dpi is ~35 MP), also set as `PIL.Image.MAX_IMAGE_PIXELS` so Pillow refuses >100 MP anywhere in the process. Uploads over the cap — including Pillow's warning range — return 400 "This image is too large to process (over 50 megapixels). Scan at a lower resolution or upload a PDF." (Italian translated). Size is read from the header before `verify()`; `DecompressionBombError`/`Warning` are caught. `barcodes.py` already caps rendered pages at 40 MP, so no existing path is affected. |
| J3 M2 (B, UI part) password to create an agent | Done | `AgentPanel.tsx`: "Your password (to create an agent token)" / "La tua password (per creare un token dell'agente)" field (`type=password`, `autocomplete=current-password`), sent as `password` in `POST /api/agents`, cleared after success; Create is disabled until filled. Specs that create agents (`agents.spec.ts`, `round2-navigation.spec.ts`) fill it from `RIPIANO_E2E_PASSWORD`. |

## Tests

- New pytest: `services/api/archive/test_round4_upload_errors.py` (10 tests: damaged PDF/PNG/JPG/JPEG vs unsupported names; a real PNG named `.pdf` still accepted; 225 MP and 64 MP PNG headers refused; API returns 400 with Italian/English text).
- New Playwright spec (written, not run against the shared stack): `apps/web/e2e/judge-round4-j2.spec.ts` (6 tests × desktop/mobile): Trash focus + live message + Undo; drawer Tab containment and `inert`; damaged PDF message; offline reload screen with queued count and reconnect; 320 px Italian reflow for Agents/Paper/Backups plus 44 px agent choices and password field; ASN accessible name/description.
- Updated specs: `agents.spec.ts`, `round2-navigation.spec.ts` (agent password); `archive.spec.ts`, `physical-missing.spec.ts` ("Reported missing" → "Marked missing", badge checked by `.copy-missing-label`); `test_round2_language.py` (Italian history note).
- Mocked browser verification (Vite dev server on port 4391 with routed `/api`, scripts in the session scratchpad `r4j2/`): Trash flow desktop + mobile in Italian (focus: Confirm → Cancel returns → next row after confirm → restored row after Undo); drawer Tab/Shift+Tab 45 presses all inside the drawer, `main.inert` true/false, Esc and close button return focus to the menu button, menu navigation still focuses the new screen's `h1`; offline reload in en/it shows 2 waiting files, no sign-in form, reconnects on `online`; 320 px measurements above.

## Verification

- `cd apps/web && npx tsc --noEmit -p . && npm run build` — passes.
- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q` — 327 passed, 14 skipped (whole tree, including other agents' concurrent changes).

## NAS impact

None noticeable: no new dependencies or images. The 50 MP image cap lowers worst-case memory per OCR job.
