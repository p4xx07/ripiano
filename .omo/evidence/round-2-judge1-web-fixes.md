# Round 2: judge 1 web fixes (apps/web)

Source: `.omo/evidence/judge-1-round-2-report.md` (candidate f2b9416), items H1 (remainder), M1, M2, M3, and L3.
This work builds on the uncommitted round-2 web fixes (`round-2-web-fixes.md`): URL routing, the inert drawer with Esc, upload announcements, and 401 handling. None of those were changed.
Scope: `apps/web` and docs only. I added no dependencies, did not touch Docker or nginx, did not edit `services/api`, and made no commits.

## Checks
- `npx tsc --noEmit -p .` passes.
- `npm run build` passes.
- `playwright test --list e2e/round2-judge1.spec.ts` parses: 5 tests × desktop and mobile.
- I did **not** run the new spec against the shared stack.
- I did check the new build locally: `vite preview` with every `/api` call mocked through `context.route`, using a throwaway script in the session scratchpad.
  - Viewports: 390x844 and 375x667 (mobile, touch) and 1440x900.
  - It covered:
    - first-row position
    - the Add button's position
    - closing the drawer by tapping the backdrop
    - the Filters reveal
    - the preview beside the form (desktop) and above it (mobile)
    - expanding the preview
    - the placeholder when the PNG fails
    - dismissing a suggestion
    - creating a tag inline (Enter creates it; focus moves to the new checkbox)
    - the offline notice, with all 8 rows kept, then recovery
  - There were no page errors.

## H1 remainder: tap outside closes the phone menu. Done.
- `App.tsx`: when the drawer is open at 800px or narrower, a `.sidebar-backdrop` scrim is drawn behind it (`aria-hidden`, z-index 7, under the sidebar's 8).
- Tapping the scrim calls `closeMenu()`, which closes the drawer and returns focus to the menu button.
- The tap does not reach anything underneath.
- Esc, focusing the drawer, and inert while closed are unchanged.

## M1: document preview while filing. Done.
- New component: `DocumentPreview.tsx`, with strings in `locales/DocumentPreview.ts`. It reuses `/api/documents/<id>/pages/1.png?v=<version>`, the same URL as PagesPanel.
  - The server renders the page at 48 dpi with Ghostscript once per version and caches it (`private, max-age=3600`).
  - The endpoint works on a PDF original at any time, and on images, Office files, and email once the searchable PDF exists (`page_source` in `versions.py`). It is owner-only.
- Calm placeholder states:
  - A non-PDF that is still pending or processing: "The preview appears when processing finishes." No request is made.
  - Not owner, or the image fails (409/404/503): "No preview for this document."
  - While the image loads, a fixed-size frame shows "Loading the preview…", so the layout does not shift. The image has `width`/`height` set, `loading="lazy"`, and `decoding="async"`.
- Desktop (1100px or wider): the dialog widens to 940px and shows the preview as a sticky left column beside the form, with an "Open full size" link to the searchable PDF.
- Narrower screens: a 140px strip above the fields shows the top of the page (letterhead and date), with "Show larger"/"Show smaller" (`aria-expanded`) and "Open full size".
- Close still receives focus first; the spec checks this.
- **Library thumbnails: not done, on purpose.** The first view of a 50-row list would start up to 50 Ghostscript renders on the NAS. That is the CPU load AGENTS.md asks us to avoid. Thumbnails would need a pre-rendered thumbnail made by the worker at OCR time, which is a server change.

## M2: phone Library first screen. Done.
At 570px or narrower:
- The Library eyebrow, the intro, the three count cards, and the "Search document text…" line are hidden.
- One line of counts is shown under "Your documents": "8 documents · 2 being processed". It stays visible during a search.
- Sort and Filters share the row under the search box.
- Saved searches and "More precise search" appear only when **Filters** is open. On phones, `SavedSearchBar` renders below the toolbar. Existing specs open Filters before "Save this search", so they are unaffected.
- **Add** is now a primary 44px button in the top bar on the Library. The old secondary `.mobile-add` under Filters is removed. The accessible name is still "Add", so the e2e helpers that use `getByRole("button", {name: "Add", exact: true})` keep working.
- "Private & yours" is hidden in the top bar on that screen to make room, and the breadcrumb truncates.
- Measured with mock data: the first row starts at y≈358 at both 390x844 and 375x667 (it was ≈810 at 390x844). The desktop layout is unchanged.
- The spec checks the first row is above `height - 60` at both sizes and that Add sits within the 70px top bar.

## M3: offline Library. Done.
- `loadDocuments` treats a network failure (status 0) or 502–504 as "unreachable".
  - If a list was already loaded, it keeps the documents, the counts, and the cursor.
  - It shows a `role=status` notice: "You're offline or Ripiano can't be reached. Showing the documents loaded at HH:MM; searching and changes need a connection.", with **Retry**.
- Coming back online (`online` event), Retry, or Refresh reloads the list, and the notice disappears.
- Other errors, or no list loaded yet:
  - the existing error with Retry is shown;
  - the counts show "–" instead of "0" (`countsKnown`);
  - the empty "fresh shelf" state is not shown until a load has succeeded.
- The kept list is cleared when the signed-in username changes, so a list is never carried over to another person.
- The list is kept in memory only. It does not survive an offline reload (the session check fails then anyway).
- New helper: `formatTime` in `api.ts`.

## L3: tag creation and dismissing a suggestion. Done.
- **Create a tag** in the document dialog posts `{name}` to `/api/tags`, adds the tag to the picker, ticks it, focuses its checkbox, and announces "…Save changes to keep it…". Enter in the name field creates the tag and does not submit the form.
- Each learned suggestion now has a × button: "Dismiss suggestion “Add tag: X”".
  - **The API cannot store a dismissal** (`filing-suggestions` is GET-only, and nothing in `learning_views.py` does it).
  - So the dismissal is kept per document, suggestion kind, and item in `sessionStorage` (`ripiano.dismissedSuggestions`), wrapped in try/catch, with an in-memory fallback.
  - It lasts for this browser session only; `USER_GUIDE.md` says so. A persistent "reject" belongs to `services/api`.
- The accept buttons' accessible names are unchanged, so `filing-suggestions.spec.ts` still matches.

## Regression spec
`apps/web/e2e/round2-judge1.spec.ts`:
- tapping outside closes the phone menu (mobile);
- first row and Add on the first screen at 390x844 and 375x667, with saved searches behind Filters (mobile);
- the preview image loads with the page URL. On desktop it sits beside the form; on mobile it is above the fields and expands. The "Open full size" link is checked, and so is the placeholder. The placeholder check bumps `version_number` in the list response, because the cached image would otherwise hide the forced 409;
- offline (`context.setOffline`): the rows are kept, the notice shows, the counts are not "0", and the list recovers;
- creating a tag inline and saving it (verified through the API), and dismissing a mocked suggestion so it stays hidden when the dialog is reopened.

## Files changed
- New: `apps/web/src/DocumentPreview.tsx`, `apps/web/src/locales/DocumentPreview.ts`, `apps/web/e2e/round2-judge1.spec.ts`
- Edited: `apps/web/src/App.tsx`, `DocumentPanel.tsx`, `api.ts` (`formatTime`), `style.css` (appended block), `locales/AppLibrary.ts`, `locales/DocumentPanel.ts`
- Docs: `docs/USER_GUIDE.md` (phone menu, phone Library, offline, preview, inline tag, dismissal), `docs/FEATURE_PARITY.md` (preview row)

## Weight on the NAS
- Opening a document dialog requests one page PNG. Each page is rendered once per version and then cached, the same cost as opening Pages & versions.
- There are no Library thumbnails, so there is no list-wide rendering.
- The JS bundle grew by a few kB.

## Still open
- An independent review of this slice still needs to be recorded.
- Run `round2-judge1.spec.ts` against a rebuilt stack.
