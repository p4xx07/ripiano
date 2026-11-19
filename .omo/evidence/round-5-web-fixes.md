# Round 5 — web fixes (judge 1 M1–M3, judge 2 M1, web-only lows)

Date: 2026-11-18. Branch `codex/initial-implementation`, not committed. Scope: `apps/web` (App.tsx, style.css,
KeyboardHelp, locales). The API, DocumentPanel.tsx, AgentPanel.tsx and InboxPanel.tsx belong to the concurrent
API agent and were not edited (only one-line string changes in their locale files, see L-naming).

## Changes

| Finding | Fix | Files |
| --- | --- | --- |
| J1 M1 Escape does not leave search | `onKeyDown` on the Library search: Escape focuses the first result's title and marks it active, so `j`/`k`/`Enter` work at once. With no results yet (or none at all) Escape blurs to `#main-content`; the query is kept (a "clear on Escape" branch was dropped because it raced with a search still loading and wiped the query). `/` still focuses search. Shortcut sheet gains an "Esc — leave the search for the first result" row (EN/IT). | `App.tsx`, `KeyboardHelp.tsx`, `locales/KeyboardHelp.ts` |
| J1 M2 sidebar clipped at 1440x900 | Appearance and Language moved out of the scrolling list into a compact, always-visible settings row (label beside select) just above the account row. Navigation compacted (30px rows, 6px padding; 44px still on coarse pointers), smaller brand/label spacing. The scrolling list sits in `.sidebar-scroll-frame`; App.tsx sets `can-scroll-up`/`can-scroll-down` (scroll + resize + ResizeObserver, no re-render) and CSS shows a fade at that edge. Drawer (inert, focus trap, Esc) unchanged and still works. | `App.tsx`, `style.css` |
| J1 M3 transient upload failure waits 60s | Waiting uploads now retry with backoff while `navigator.onLine`: 3 s, 10 s, 30 s, then 60 s (repeating), started both after a failed `sendWaiting` and when `upload()` keeps a file. `offline` cancels the timer; `online` resets the backoff and sends. Banner says "Ripiano couldn't be reached; trying again…" (IT "Ripiano non è raggiungibile; nuovo tentativo a breve…") while retrying online, and the old "when the connection is back" text only when offline. Button renamed "Send now" / "Invia ora", resets backoff and sends at once. `isRetryable`/`isRefusal`, owner check (`signedInAs`) and scan-ID reuse are unchanged; the timer is cleared on sign-out/session change. | `App.tsx`, `locales/AppLibrary.ts` |
| J2 M1 / J1 L2 mobile rows | ≤570px: decorative file icon hidden; title wrapped in `.document-title-text` with a 2-line clamp (`overflow-wrap:anywhere` for long tokens) inside a 44px-min button; metadata clamped to 2 lines; status + icons stacked in a narrow right column (`.document-row-actions`, `display:contents` on desktop so desktop is unchanged). Measured with mocked API: 390px → title width 248px, 2 lines, row 128px (about 6 rows per screen vs 2.5); 320px → 178px, no horizontal overflow; all touch targets ≥44px. | `App.tsx`, `style.css` |
| J2 L2 Italian help | Help text is locale-driven: Italian shows `etichetta:bollette`, `mittente:"Comune"`, `data:2026-04-15`, `titolo: testo: nota: tipo: adesivo: aggiunto:`, plus "Funzionano anche i nomi inglesi…". English unchanged except `added:` listed. | `App.tsx`, `locales/AppLibrary.ts` |
| J2 L3 results not a list | Library results are `<ul role="list" aria-label="Documents|Documenti">` with one `<li>` per `article.document-row`; `.document-list .document-row`, `getByRole("article")` and `data-document-id` selectors still match. Row separators moved to `li:not(:last-child) > .document-row`. | `App.tsx`, `style.css` |
| J2 L4 summary focus ring | `summary` added to the shared 3px focus-visible contract. | `style.css` |
| J1 L3 OCR retry naming | "Retry OCR" / "Riprova l'OCR" everywhere: Library row (title, aria "Retry OCR for <file>"), Inbox (`tryOcrAgain`), document panel (`runOcrAgain`), background jobs (IT), bulk action "Retry OCR for failed documents" / "Riprova l'OCR dei non riusciti". Specs updated: `inbox.spec.ts` ("Try OCR again"), `reprocess.spec.ts` ("Run OCR again"), `round2-navigation.spec.ts` ("Try now" → "Send now"). | `locales/AppLibrary.ts`, `locales/InboxPanel.ts`, `locales/DocumentPanel.ts`, `locales/JobsPanel.ts`, e2e |
| J2 L6 dates | Backup snapshots show date and time (`formatDateTime`), Overview "last backup" and background-jobs timestamps use `formatDateTime` (interface language) instead of `toLocaleString()`. Paper-copy history (`DocumentPanel.tsx:826`) is owned by the API agent and left alone. | `App.tsx`, `OverviewPanel.tsx`, `JobsPanel.tsx` |

Docs: `docs/USER_GUIDE.md` (Esc in search, retry timing and Send now, settings row location).

## Regression tests (written, not run against the shared stack)

`apps/web/e2e/round5-web.spec.ts`: Escape → first result → j/k/Enter (and Escape with no results keeps the
query); sidebar Appearance/Language/Sign out uncovered at 1440x900, 1366x768, 1280x720; scroll fade classes and
`::after` opacity at 1280x520; automatic retry within 10 s after a `connectionreset` with "Send now" shown and the
same scan ID; offline wording kept while offline; phone rows at 390x844 and 320x640 (≤2 title lines, ≤2 meta
lines, title width >50% of viewport, 44px targets, no horizontal scroll); results list/listitem; summary 3px ring;
Italian help field names. `npx playwright test --list` lists 24 tests.

## Verification

- `npx tsc --noEmit -p .` and `npm run build`: pass.
- `npx vite preview --port 4179` with every `/api/*` route mocked in Playwright (scratch script, not in repo), not
  against localhost:18080:
  - Escape: focus moved to the first title (row 0 active), `j` → row 1 with search value unchanged, Enter opened
    the document; with no results Escape moved focus to `main#main-content` and kept "zzz".
  - Sidebar: Appearance/Language/Sign out hit-tested uncovered at 1440x900 (bottoms 787/825/886), 1366x768,
    1280x720 (all nav entries visible for an owner), 1280x520 (`can-scroll-down` set). Phone drawer: main inert,
    fade shown, Esc returns focus to "Toggle menu".
  - Upload retry: banner "1 file is waiting to upload. Ripiano couldn't be reached; trying again…" + "Send now";
    gone after 3.3 s with 2 POSTs.
  - Summary focus ring: 3px solid.
- No dependencies, Docker, or stack changes. Bundle size change negligible (CSS/JS only).

## Not done / notes

- Phone metadata still shows the original file name before the sender; with the 2-line clamp the sender can be cut
  ("Fro…"). Reordering or hiding the file name on phones was left out because several specs read file names in rows.
- `OverviewPanel` month labels still use `toLocaleDateString(undefined, …)`; other panels (Mail, Sources, Share
  links, People) still use `toLocaleString()` and are outside this slice.
- Independent review of this slice is still to be recorded.
