# Round 2: independent review of the web changes (apps/web)

Date: 2026-11-18. Reviewer: independent agent; no repository file was edited except this report.

## Scope

Uncommitted changes under `apps/web` on `codex/initial-implementation` (base f2b9416): `git diff -- apps/web` (18 files) plus the new files `public/boot.js`, `src/DocumentPreview.tsx`, `src/locales/DocumentPreview.ts`, `e2e/round2-navigation.spec.ts`, `e2e/round2-judge1.spec.ts`.
Read for context: `src/ui.tsx` (Modal), `vite.config.ts`, `apps/android/.../MainActivity.java`, the scan-ID branch of `services/api/archive/views.py` (601-619), and the server's 401 responses.

This is a static review. I did not run Playwright, did not touch Docker, and did not serve the build through nginx, so **the CSP was checked by reading the built output, not in a browser**.

## Commands

| Command (in `apps/web`) | Result |
| --- | --- |
| `npx tsc --noEmit -p .` | exit 0 |
| `npm run build` | passed; JS 693.35 kB (gzip 194.10 kB), CSS 88.00 kB; precache 8 entries, including `boot.js` and `registerSW.js` |
| `dist/index.html` inspected | no inline `<script>`; `boot.js`, the module bundle, and `registerSW.js` are all external same-origin files |

## Findings

### High

None.

### Medium

**M1. Signing out from the Library leaves `replaceNextUrl` set, so the first navigation after the next sign-in replaces the entry instead of adding one.** `src/App.tsx:1388` (flag set), `:717`/`:723` (flag read and cleared only when the sync effect runs).
- `signOut()` sets `replaceNextUrl.current = true`, then `setSelectedDocument(null)` and `setView("documents")`. When the person is already on the Library with no dialog open, neither state changes, the history effect (`[view, selectedDocument, historyTick]`) does not run, and the flag stays true.
- Scenario: on `/`, sign out, sign in, tap Inbox. The address becomes `/inbox` by `replaceState`. Back does not return to the Library: in a browser it leaves the app for the previous page, and in the Android app `canGoBack()` is false, so the activity closes. This is the judge's H1 again for the most common sign-out position.
- Fix: clear the flag when nothing will change (for example only set it when `view !== "documents" || selectedDocument`), or do the `replaceState` directly in `signOut`.

**M2. A 401 that turns out to be a false alarm leaves the app half signed out.** `src/App.tsx:1152-1165`.
- The listener sets `signedInAs.current = null` first. If the `/api/session` re-read says `authenticated: true` for the same person ("still signed in after all: carry on", line 1162), nothing sets it back: the effect that assigns it (`:1287`) depends on `session.authenticated` and `session.username`, which did not change.
- Consequences until the page is reloaded: `sendWaiting()` stops at `signedInAs.current !== owner` on every run, so queued uploads are never sent; and every later, real 401 is ignored (`if (!signedInAs.current) return`), so the app shows an empty archive again instead of the sign-in screen. The open document dialog, the Add sheet, and the shortcut help were also already closed, discarding any edits.
- Scenario: two tabs. Tab B signs out and signs in again as the same person. Tab A's 5-second list poll gets a 401 in between; its `/api/session` re-read lands after B's sign-in and returns authenticated. The same happens when a request sent before a sign-out answers 401 after the next sign-in in one tab.
- Fix: in the authenticated branch restore `signedInAs.current = value.username`, and close the dialogs only once the session is known to have ended.

**M3. After a failed search while offline, the "showing the documents loaded at HH:MM" notice can appear above an empty list.** `src/App.tsx:1124-1134`.
- The error branch clears `documents` but leaves `listLoadedRef.current` true and `lastLoadedView.current` at the key of the last successful load.
- Scenario: Library loaded, connection drops, type a search (it fails, the list is cleared and the error is shown, as intended), then clear the search box. The reload has the same key as the last successful load, so the code takes the "keep the list" branch: it sets `staleSince` and clears `listError`, but the list it claims to keep is already empty. The person sees the offline notice saying documents are shown, no documents, and counts of "–".
- Fix: set `listLoadedRef.current = false` (or clear `lastLoadedView`) in the branch that empties the list.

### Low

- **L1. Back closes the document dialog and discards unsaved edits without asking.** `src/App.tsx:743-744`; `DocumentPanel.tsx` has no dirty tracking. Not a regression: Esc, the close button, and a click on the backdrop already do the same, and before this change the Android Back button closed the whole app. But Back is now the natural way to close the dialog on a phone, and an edge swipe while typing a note loses it.
- **L2. Back does not close the Add sheet or the shortcut help; it changes the screen underneath them.** `restore()` at `src/App.tsx:727` only handles the document dialog. On Android, Back with the Add sheet open goes to the previous screen (or closes the app) and the sheet stays open.
- **L3. Reloading with the document dialog open adds a duplicate screen entry.** `src/App.tsx:717`: on first sync the `?document=` entry is replaced by the screen and the dialog is pushed again, so `[/inbox, /inbox?document=A]` becomes `[/inbox, /inbox, /inbox?document=A]`; one Back press after closing does nothing visible.
- **L4. Forward to a document that no longer exists (or belongs to the previous person on this device) shows "document unavailable" and steps back every time.** `src/App.tsx:749-756`. No loop and no data leak (the server decides), but the forward entry is never removed. If this happens on the sign-in screen, the error text is still set after signing in.
- **L5. After a 401, the multi-file upload loop keeps posting the remaining files.** `src/App.tsx:1311-1333`: 401 is not retryable, so each file is reported as failed rather than queued, and each one gets its own 401. Queued files (`sendWaiting`) are kept correctly.
- **L6. Queue entries saved before this change get a new scan ID on every retry.** `src/App.tsx:1268` (`item.scanId ?? newScanId()` is not written back). Only affects files already queued at upgrade; new entries keep one ID per file, and IDs are created per file inside the loop (`:1315`), so two files never share one.
- **L7. A queued file that always gets a 5xx/403/429 blocks the queue behind it forever.** `src/App.tsx:1273`; unchanged behavior, noted because the request asked. Refusals (400/409/413/415) are removed and reported.
- **L8. The open phone drawer does not trap focus.** `src/App.tsx:1467`, `:1530`: `main` is not inert while the drawer is open, so Tab moves from the last link to controls hidden behind the scrim. When Back closes the drawer (`restore()` calls `setMenuOpen(false)` without `closeMenu()`), focus was inside the now-inert sidebar and falls to `body`.
- **L9. Possible stuck "Loading the preview…" when the page image comes from cache.** `src/DocumentPreview.tsx:22`: the effect resets the state to "loading" after `src` changes; if the cached image's `load` event is handled first, the image stays at opacity 0. I could not reproduce this statically; deriving the state from `src` (store the loaded `src` instead of a flag) removes the doubt.
- **L10. A non-owner opening `/people` or `/backups` renders that panel for one frame before the fallback.** `src/App.tsx:1172-1178`: the panel mounts and fires its requests (the server refuses them), then the Library replaces it.

## Checked and found sound

- **History:** close with the button or Esc steps back over the app's own entry; dialog to Tags/Locations replaces the dialog entry; opening a duplicate from the dialog replaces in place; a document opened together with a screen change (`:1604`) ends with `[/paper, /]` after closing; `/?document=<id>` deep links reduce to the screen first, wait for sign-in, and open once (`openedInitialDocument`), so the next person on the device does not get it; unknown paths and owner-only paths are replaced by `/`. I found no back/forward loop.
- **401:** `/api/session` and `/api/setup` are excluded, and those are the only places the server answers 401 for a wrong password or code (`views.py:306-314`); every other 401 is "Sign in required". The re-read of `/api/session` cannot re-trigger the listener. Requests in flight after a deliberate sign-out are ignored (`signedInAs` is cleared first).
- **Upload queue:** one ID per file from the first attempt, stored in IndexedDB with the entry and resent on retry; the server looks it up per owner with `source=web`.
- **CSP:** the build has no inline script; the app uses no iframes, `blob:` or `data:` documents, `window.open`, `javascript:` URLs, workers other than the service worker, or cross-origin fetches. The 2FA QR is inline SVG via `dangerouslySetInnerHTML` (allowed; `style-src` has `'unsafe-inline'`). OAuth for mail and sources uses `location.assign`, which `form-action` does not restrict. The headers sit only in `location /`, so label pages and PDFs under `/api/` are unaffected. `MainActivity.java` uses `evaluateJavascript` (not subject to CSP), `addWebMessageListener`, and `loadUrl(origin + "/")`; no `javascript:` URL or injected `<script>`. `onBackPressed` uses `canGoBack()`, which now follows the pushed entries.
- **Inert:** `narrowLayout` follows `matchMedia("(max-width: 800px)")` changes, so widening the window removes `inert` and `aria-hidden`; React 19 handles the `inert` prop.
- **Preview:** no request is made for a document the viewer does not own (`access !== "owner"`) or for a non-PDF still being processed; a failed image shows the placeholder.
- **i18n:** every new string I found is in the `locales/*` files in English and Italian; no hard-coded English in the new JSX.

## Verdict

**Approve with fixes.** No high finding. M1 should be fixed before the judges re-test, because it reintroduces "Back leaves the app" after the most common sign-out; M2 and M3 are one-line fixes each. The low items can wait. The CSP still needs one check in a browser against the nginx image, since nothing in this review or in the dev-server e2e suite exercises it.

## Resolution (main session, 2026-11-18)

- **M1 fixed:** `signOut` sets the replace flag only when the screen or dialog will actually change; regression test "after signing out and in again from the Library, Back still stays in the app" (`e2e/round2-navigation.spec.ts`).
- **M2 fixed:** on a 401 the app first asks the server whether the session really ended; a false alarm restores the signed-in state and closes nothing, a real end closes dialogs and shows the notice.
- **M3 fixed:** a failed search that empties the list also forgets the "last loaded list", so the offline notice never appears above an empty list; a stale list is kept only when the same search, filters, and sort are being reloaded.
- **CSP checked in the running nginx image:** headers present on `/`, `boot.js` and deep links served; the full browser suite (144 passed) runs against that image with the policy active.
- **Low, not changed:** Back does not close the Add sheet or shortcut help; the open phone menu does not trap focus (it is closed by Esc, the backdrop, or choosing a screen); queued uploads created before scan IDs existed get a new ID per retry.
