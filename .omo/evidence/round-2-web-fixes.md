# Round 2: web app fixes (apps/web)

Sources: `.omo/evidence/judge-2-round-2-report.md`, plus judge 3 items H2, M1, and M4 (UI) from the coordinator (`judge-3-round-2-report.md`).
Scope: `apps/web` only. No dependencies were added, Docker was not touched, and the stack was not rebuilt or restarted.

Regression spec: `apps/web/e2e/round2-navigation.spec.ts` (9 tests × desktop and mobile). It uses the real server with `RIPIANO_E2E_USERNAME`/`PASSWORD` and English labels.
Checks run: `npx tsc --noEmit -p .` passed, `npm run build` passed, and `playwright --list` parses the spec.
I did **not** run the spec against the shared stack: it runs the previous build and the judges are using it.
I did verify the behavior locally against `vite preview` of the new build, with every `/api` call mocked through `page.route`. That throwaway harness was deleted afterwards. It covered:
- history Back and Forward, the document dialog, the `?document=` link, and sign-out to `/`
- the drawer: inert, `aria-expanded`, Esc, and focus
- upload announcement, the shortcut help, the backup trigger and error text, and the agent token focus
- the 44px password field on mobile (desktop stays 24px)
- the 401 redirect to sign-in, and a wrong password staying on the form
- the scan ID reused on retry

## High

**H1 Back leaves the app: fixed.** `App.tsx`
- Each screen now has its own path: `/` (All documents), `/inbox`, `/actions`, `/tags`, `/paper`, `/backups`, `/agents`, `/trash`, `/email`, `/sources`, `/workflows`, `/security`, `/overview`, `/shared`, `/people`.
- The routing uses the History API; there is no router dependency.
  - nginx `try_files … /index.html` and the workbox `navigateFallback` already serve every one of these paths, so nginx needs no change.
  - `index.html` and `boot.js` use absolute asset paths.
- One effect keeps the address in sync with `view` and the open document:
  - a screen change pushes an entry; choosing the screen you are already on pushes nothing;
  - the first sync and sign-out replace the entry instead.
- Opening a document pushes `?document=<id>` with `{ripianoDialog: true}`, so Back closes the dialog.
  - Closing the dialog with its button or Esc calls `history.back()` on that entry, so no dead entry is left behind.
  - Going from the dialog to another screen (Tags, Locations) replaces the dialog entry.
- A `popstate` handler restores the screen and moves focus to its heading.
  - For an entry with `?document=`, it fetches the document and reopens it, so Forward works.
- Initial load follows the URL. An existing `/?document=<id>` link reduces the address to the screen, then opens the dialog as a new entry, so Back closes it.
- Owner-only screens (`/people`, `/backups`) fall back to the Library for other users.
- In an installed PWA, back from the first screen leaves the app as usual.

**H2 Closed mobile drawer is focusable: fixed.** `App.tsx`
- At widths of 800px or less (the drawer breakpoint, tracked with `matchMedia`), the closed `<aside id="app-sidebar">` gets `inert` and `aria-hidden="true"`. Its close button is inside it, so it is unreachable too.
- The menu button has `aria-expanded` and `aria-controls="app-sidebar"`; its label "Toggle menu" is unchanged because existing specs use it.
- Opening the menu focuses the current screen's link.
- Esc, or the close button, closes the menu and returns focus to the menu button.
- Picking the screen that is already open closes the menu without losing focus.

## Medium

**M1 Focus lost after creating or revoking an agent token: fixed.** `AgentPanel.tsx`
- The one-time token card is now `role="region"`, labelled "Copy this token now", with `tabIndex=-1`. After a token is created, the card is scrolled to the centre and focused.
- A polite status announces "Token for “X” created. Copy it now…".
- After a revoke, focus moves to the agent's card (now marked Revoked) and "Access for “X” revoked." is announced.
- Cancelling the revoke confirmation returns focus to that agent's Revoke button.

**M2 Upload completion is not announced: fixed.** `App.tsx`
- A persistent `aria-live="polite"` region says "Added N documents." / "Aggiunti N documenti.", with a **Show** button (accessible name "Show the new document(s)") and a dismiss button.
- On narrow screens the first new document row is scrolled into view and its title is focused automatically.
- This region is not `role=status`, so existing specs that call `getByRole("status")` unscoped are not affected.

**M5 English and raw strings leak through: fixed in the web app.**
- Backup trigger: the API stores `schedule`, `manual`, and `retry` (`archive/models.py:192`, `tasks.py:199`, `views.py:1249`, `job_views.py:45`). `locales/AppBackups.ts` now maps them in both languages: scheduled/pianificato, manual/manuale, retry/nuovo tentativo.
- Backup and NAS-copy errors: the server message is shown as it is. Legacy raw strings (`[Errno …`, `Traceback`, `XxxError:`) are replaced with a localized generic message (`readableJobError` in `App.tsx`).
- The source-connected notice is now `m.sourceConnected(name)` in English and Italian.
- Label pages (L2):
  - `i18n.ts` now sets the `django_language` cookie to the interface language. Django's `get_language_from_request` reads that cookie before Accept-Language, so printable labels opened from a plain link follow the app language.
  - `boot.js` sets `<html lang>` before the app loads (the coordinator moved this script out of `index.html`).
- These remain on the server side: "No type", "Initial placement", and "Subject" in snippets.

**M6 Touch targets under 44px: fixed.**
- `style.css` has a new `@media (pointer: coarse)` block that gives these controls a 44px minimum:
  - tag delete and cancel (`.tag-icon-button`), share (`.share-object-button`), and "Move" (`.tag-move-button`);
  - "Add matching phrase" (`.add-rule`);
  - the Sources console links and the "API reference" link (`.source-note a`, `.page-heading p a`);
  - password fields on Security, People, and Password;
  - the color input;
  - agent Revoke and confirm buttons;
  - the upload notice dismiss button.
- Desktop (fine pointer) is unchanged.

**M7 Shortcut help names differ from the menu: fixed.** `locales/KeyboardHelp.ts`, `KeyboardHelp.tsx`
- Each "go to" row is a full localized string that uses the menu's names: "Go to All documents", "Vai a “Tutti i documenti”", "Vai a “Da fare”", "Vai alla “Panoramica”", "Vai ai “Flussi di lavoro”", "Vai alle “Sorgenti”", and so on.
- Enter is "Invio" in Italian. The section names are "In “Tutti i documenti”" and "Cerca nei documenti".
- `docs/USER_GUIDE.md` now says "L All documents".

## Low (apps/web only)
- **L2:** see M5 (cookie and early `lang`).
- **L4:** Inbox "Keep both" and "Try OCR again" buttons now have `aria-describedby` pointing to their document's title. The accessible name is unchanged, so existing specs still match.
- **L5:**
  - The Add sheet's eyebrow and heading get `padding-right: 48px`, so the close button no longer covers the text.
  - The "/" search hint is hidden on coarse pointers.
- **L6:** Saving and closing the document dialog now announces "Saved “title”." / "“title” salvato." through an app-level polite live region. `DocumentPanel`'s `onSaved` received an optional `closing` flag for this.
- **Not done:**
  - L3 (337px at 320px width): it needs measuring against real data.
  - L1, L7, L8 are server-side.
  - M3 (document preview in the edit dialog) and M4 (Italian stemming) are not small web-only fixes; M4 is server-side.

## Judge 3 items (from the coordinator)

**H2 Stable scan ID for web uploads: done.**
- `uploadQueue.newScanId()` builds a UUID v4 from `crypto.getRandomValues`, because `crypto.randomUUID` needs a secure context and a NAS on plain http does not have one. The format matches the server's `str(UUID(...))` check in `views.py`.
- Every live upload sends `X-Ripiano-Scan-ID`.
- When a live attempt fails and the file is queued, the same ID is stored with the entry (`PendingUpload.scanId`) and sent again on retry. Older queued entries get a new ID when they are sent.
- **Server note:** today `views.py` stores a scan-ID upload as `source=android`, so the Library would label web uploads "Scanned with Android". The API must accept the header for web uploads without changing the source; that change belongs to whoever owns `services/api`.

**M1 401 returns to sign-in: done.**
- `api.ts` adds `onSessionEnded(listener)`. It fires on any 401 except `/api/session` and `/api/setup`, where 401 means a wrong password or 2FA code. Wrong-password errors elsewhere (Security, People) come back as 400.
- `App.tsx` listens once per signed-in user:
  - it closes dialogs, the drawer, and the Add sheet;
  - it re-reads `/api/session` and shows the sign-in screen with "You were signed out. Sign in again to continue." / "Sei stato disconnesso. Accedi di nuovo per continuare." (`role=status`);
  - it keeps the current address, so signing in returns to the same screen.

**M4 (UI) Agents for every signed-in person: done.**
- Agents is in the navigation for everyone and has been removed from the owner-only views.
- Semantic search settings (instance-wide) are shown only to the admin (`session.owner`).
- The Agents intro no longer says "sign in as the owner".

## Files changed
- `apps/web/src/App.tsx`, `AgentPanel.tsx`, `DocumentPanel.tsx`, `InboxPanel.tsx`, `KeyboardHelp.tsx`, `api.ts`, `i18n.ts`, `uploadQueue.ts`, `style.css`
- `apps/web/src/locales/App.ts`, `AppBackups.ts`, `AppLibrary.ts`, `AgentPanel.ts`, `KeyboardHelp.ts`
- `apps/web/e2e/round2-navigation.spec.ts` (new)
- `docs/USER_GUIDE.md` (navigation, accessibility, and shortcut names)
- My early-`lang` edit to `index.html` now lives in the coordinator's `public/boot.js`. `nginx.conf` was not touched by me.

## Weight on the NAS
None: client-side code and CSS only. The JS bundle grew by a few kB.
