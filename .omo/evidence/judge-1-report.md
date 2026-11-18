# Judge 1 report: Ripiano quality gate

- **Candidate SHA:** 901d491828b1eb9df5d674a23e6115c0dd7bc3be (branch `codex/initial-implementation`)
- **Date:** 2026-11-18, 09:15–09:40 Europe/Rome
- **Judge:** judge1 (Admin account on the shared stack at http://localhost:18080). The account started empty.
- **Emphasis:** a first-time owner on desktop, then the key journeys again in mobile emulation. All five dimensions are scored.
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Google Chrome 157.0.8103.79 (channel `chrome`, headless).
  - Desktop viewport: 1440x900.
  - Mobile emulation: 390x844, `isMobile`, `hasTouch`, deviceScaleFactor 3, iPhone 13 user agent.
  - Italian was checked with context locale `it-IT` and the in-app language switch.
- **Artifacts:** `qa-artifacts/20261118-judge-1/` holds 42 screenshots (`d*` = desktop, `m*` = mobile) and `judge1-scripts.mjs.txt`, which concatenates every script that was run. Agent tokens are masked in screenshots, and no token or password is written to disk inside the repo.

## Commands run

Each script was run with `node sNN.mjs` from the scratch folder. The scripts import `@playwright/test` from `apps/web/node_modules` by absolute path. Their full source is in `judge1-scripts.mjs.txt`.

| Script | What it did |
| --- | --- |
| s01–s02 | Sign in, empty-archive first impression, sidebar measurements |
| s03–s05 | Multi-file upload of 12 fixtures through Add document → Browse files, then poll `/api/documents` until processing finished |
| s06–s07, s11 | Document dialog; search by OCR phrase, sender, tag, type, date, ASN, and field syntax |
| s08 | Tour of Inbox, Tags & filing, Paper archive, Overview, Agents, Backups, Sources |
| s09–s10 | Create tags with matching phrases; set date, sender, and type in the document dialog |
| s12–s13 | Locations, sticker creation, printed label, move with history, sticker lookup and `/?sticker=` deep link (the address the QR code opens) |
| s14–s17 | Two MCP agents with different scopes and tag filters; `initialize`, `tools/list`, and `tools/call` over `POST /mcp` with Node `fetch`; revocation; audit list |
| s18 | Upload interrupted with `route.abort("connectionreset")`; mismatched extension; duplicate upload |
| s19–s20 | Inbox duplicate review, Back up now (completed in 20 s), searchable-PDF preview link |
| s21 | Keyboard-only: sign-in, skip link, `/`, `j`/`k`/Enter, focus trap, `?`, `n`, `g`+letter |
| s22–s24 | Mobile: camera input (`capture=environment`), search, dialog, drawer navigation, sticker lookup, horizontal-overflow and touch-target checks, drawer reachability |
| s25 | Italian sweep of every screen and the document dialog; Italian API error message |
| s26 | SHA-256 of stored originals against the fixtures; Run OCR again, then re-check the bytes |
| s27–s30 | CSRF probes, anonymous API access, Trash and Restore through the UI |
| s31–s33 | Learn now, similar documents, removal of an automatic tag surviving a reprocess |

## Fixtures used

These are from `apps/web/e2e/fixtures/`:

`judge.png`, `three-pages.pdf`, `office-letter.docx`, `office-sheet.xlsx`, `office-slides.pptx`, `office-open.odt`, `office-legacy.doc`, `email-notice.eml`, `outlook-notice.msg`, `tag-barcode-desktop.pdf`, `asn-batch-desktop.pdf`, `barcode-batch-desktop.pdf`.

`judge.png` was also re-uploaded under three other names: `j1-dup-judge.png`, `j1-mismatch.pdf` (PNG bytes with a `.pdf` name), and `j1-camera-scan.png` (through the mobile camera input). `three-pages.pdf` was used for the interrupted upload as `j1-interrupted-three-pages.pdf`.

I did not use: `asn-batch-mobile.pdf`, `barcode-batch-mobile.pdf`, `tag-barcode-mobile.pdf`.

## Scores

| Dimension | Weight | Score | Evidence (what I exercised) | Not exercisable here |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | **7.0** | See below the table. | Telegram file, watched folder (no host access allowed), real camera, learned suggestions (the corpus is too small) |
| Retrieval and physical filing | 20% | **7.5** | See below the table. | Physical printer, real QR scan with a phone camera |
| UX and accessibility | 20% | **6.0** | See below the table. | Installed iOS/Android PWA, Android native client, real screen readers (VoiceOver/TalkBack) |
| Reliability and recovery | 20% | **6.5** | See below the table. | Worker or service interruption and restart (containers must not be touched), restore to an empty stack, permissions after restore |
| Privacy and agent control | 15% | **8.0** | See below the table. | A real cloud MCP client; semantic search (off, no pgvector) |

**Weighted mean: 0.25×7.0 + 0.20×7.5 + 0.20×6.0 + 0.20×6.5 + 0.15×8.0 = 6.95 / 10**

### Capture and filing friction (7.0)

What worked:
- Twelve mixed-format files were uploaded in one action. All reached Ready in under about 60 s, and the PDFs were split by barcode and ASN (ASN 900001, 900011, 900012).
- There was no mandatory TODO screen. The Inbox shows only exact copies (`d31`).
- Tag phrase rules applied retroactively to existing documents.
- Manual date, sender, and type were set in one dialog, including inline creation of a new sender or type.
- Removing an automatic tag survived a Run OCR again.
- The mobile camera input works (emulated): `j1-camera-scan` was flagged as an exact copy.

What lowered the score:
- No document date is ever detected, not even from the email `Date:` header.
- The email sender is not filed as a sender (finding H2).
- An interrupted upload shows a raw "Failed to fetch" with no retry (M1).

### Retrieval and physical filing (7.5)

What worked:
- Searches found: OCR phrase `9473` (judge.png), `lampone`, `mirtillo`, `from:Amministrazione`, `tag:Tasse`, `type:Avviso`, `date:2026-11-10`, and `asn:900011`, each with snippets.
- Locations nest (shelf, then box).
- A sticker was created, its label printed, and the copy moved, with history kept.
- Sticker lookup is case-insensitive, and the `/?sticker=` deep link opens the result.

What lowered the score:
- The label clips the location line (M3).
- The "Inside" field keeps the last parent, which nested a top-level location by mistake. There is no UI to rename, move, or delete a location (M2).
- There is no in-app QR scanner in the PWA.
- `correspondent:` silently returns 0 results.

### UX and accessibility (6.0)

What worked:
- Desktop and mobile layouts have no horizontal overflow.
- Focus rings are visible (3 px), and the skip link works.
- `/`, `n`, `?`, and `j`/`k`/Enter work, and the dialog focus trap holds.
- The Italian interface is nearly complete, and API errors are translated ("Usa AAAA-MM-GG dopo date:").

What lowered the score:
- Sign-out and the language picker are unreachable at 1440x900 and 390x844 (H1).
- The sign-out button's accessible name is "J judge1 Admin" (M4).
- Several mobile touch targets are under 44 px (M5).
- After a search on mobile, results start below the fold.
- Some mixed-locale and untranslated strings remain (L).
- There is no in-app document preview; it opens a PDF tab.

### Reliability and recovery (6.5)

What worked:
- The stored originals of 5 fixtures match the fixture SHA-256 byte for byte. They still match after Run OCR again.
- Back up now completed in 20 s, and the snapshot is listed.
- Trash and Restore work.
- Bytes with a mismatched extension were handled by content and flagged as an exact copy.

What lowered the score:
- An interrupted upload leaves no retry path (M1).
- A failed backup row shows a raw `[Errno 13] Permission denied: '/backup/staging'` (L).

### Privacy and agent control (8.0)

What worked:
- Agent A has search, OCR text, and tags. Its `tools/list` returns 5 tools.
- Agent B has search only and a "Condominio" filter. Its `tools/list` returns only `search_documents`.
  - B cannot match body text ("Riunione" gives 0 results) and sees only documents tagged Condominio.
  - B's `get_document_text` and `list_tags` calls are denied and audited as "denied".
- Revoking B in the UI gave an immediate HTTP 401, while A kept working.
- An invalid token gets 401.
- CSRF: POST without a token returns 403, both same-origin and cross-origin.
- An anonymous `/api/documents` request gets 401.

What lowered the score:
- The audit list does not show which document was touched.
- In code, `list_tags` ignores the grant's tag filter (L).
- Revoke has no confirmation, and the Revoke buttons have identical names (L).
- Audit actions show raw English tool names in the Italian interface.

## Hard gates (QUALITY_JUDGES.md)

| # | Gate | Status |
| --- | --- | --- |
| 1 | Every parity row has a working scenario or accepted deviation | **Partially demonstrated.** I exercised these rows: upload (web, multi-file, camera input), Office/EML/MSG conversion, OCR and reprocess, barcode/ASN split, tags, senders, types, dates, search syntax, duplicates, Trash/Restore, backup, agents, and Italian. I found one parity gap: automatic document-date detection, which Paperless does from content (H2). Many rows were not exercised: workflows, mail accounts, sources, versions, page edits, share links, custom fields, and others. |
| 2 | Fresh install, upload/OCR/search, backup, clean-stack restore | **Partially demonstrated.** Upload, OCR, and search on a fresh account passed, and a manual backup completed. Fresh installation and clean-stack restore were not demonstrated: they need a container rebuild, which is not allowed. |
| 3 | Installed iOS/Android PWA and native Android on real devices | **Not demonstrated.** Needs the owner's hardware. Only browser emulation was used. |
| 4 | Security review: isolation, revocation, CSRF, upload validation, external input, no default transfer to model providers | **Partially demonstrated.** Agent scope and filter isolation, revocation, CSRF, and anonymous 401 were demonstrated. Semantic search is off by default. Not covered: cross-account isolation between humans, upload fuzzing, and external inputs. |
| 5 | Tests, builds, browser journeys, migrations, deployment checks on the candidate | **Not demonstrated by this judge.** I did not run the test suites, builds, or migrations. I only drove the running stack. |

## Findings

### Severe

None found in what I exercised.

### High

**H1. Sign-out, the language picker, and part of the theme picker cannot be reached on common screens, on desktop and mobile.**
- **Cause:** the sidebar is `position: sticky; height: 100vh` on desktop and `position: fixed` in the mobile drawer, with no `overflow-y`. Its content is about 1160 px tall.
- **Effect at 1440x900:** the profile/sign-out button sits at y≈1103, and the Language select's bottom edge at y≈915. Scrolling (wheel or touch) moves the page, not the sidebar, so neither ever comes into view. The note card under the sidebar is rendered outside the dark background, which makes its heading white-on-cream (`d02`, `d03`).
- **Effect at 390x844:** the drawer shows nothing below the Appearance select, so the language switch and sign-out are out of reach (`m10-menu-after-scroll`).
- **Repro:** sign in at 1440x900, or open the menu at 390x844. Try to reach "Sign out" or "Language".
- **Location:** `apps/web/src/style.css:177-188` (`.sidebar`) and `apps/web/src/style.css:1212-1216` (mobile `.sidebar`). Both need `overflow-y: auto` or a compact layout.

**H2. No automatic document date, and no sender from email headers.**
- **What happens:** every uploaded document has `document_date = null`. This includes `email-notice.eml` and `outlook-notice.msg`, even though both carry `Date: Tue, 10 Nov 2026`. Senders are not set from the `From:` header either.
- **Effect:** `date:` retrieval and date sorting only work after manual filing. That conflicts with the "capture without filing" goal, and with Paperless parity, where the created date is parsed from content.
- **Repro:** upload `email-notice.eml`, then call `GET /api/documents/<id>`. `document_date` is null and the dialog's date field is empty.
- **Location:** no date-detection code exists in `services/api` (grep for dateparser or date-detection finds nothing). `archive/email_render.py` `inspect_eml`/`inspect_msg` read the Date header but never set `document_date`.

### Medium

**M1. An interrupted upload shows a raw browser error and has no retry.**
- **What happens:** the banner reads "1 of 1 files could not be added. j1-interrupted-three-pages.pdf: Failed to fetch". The message is raw English even in Italian, there is no Retry button, and the user has to find and pick the file again. On a phone with a flaky connection, that is the main capture failure path.
- **Repro:** abort `POST /api/documents` mid-request (s18, `d27`).
- **Location:** `apps/web/src/App.tsx:991,1039`, which shows `cause.message` directly.

**M2. Locations: "Inside" stays set after you add a location, and there is no UI to fix a mistake.**
- **What happens:** I added "Studio scaffale", then "Scatola 2026" inside it, then "Armadio ingresso" without touching "Inside". It was silently created as "Studio scaffale / Armadio ingresso" (`d19`). The Paper archive screen has no rename, move, or delete for locations; the API only offers DELETE.
- **Repro:** Paper archive → add a nested location → add another name and submit.
- **Location:** `apps/web/src/PhysicalPanel.tsx:73-83` resets `name` but not `parent`. `services/api/archive/physical_views.py:104` has no PATCH, and no delete button is wired in the UI.

**M3. The printed sticker clips the location and wraps the code.**
- **What happens:** on a 70×40 mm label with a three-word title, the location line is cut off ("Studio scaffale / Scatola…"). The sticker code also breaks across lines as "R-" / "7JVVQTRH" (`d21`).
- **Repro:** create a sticker for "Avviso condominio mirtillo" in a nested box, then Print sticker.
- **Location:** `services/api/archive/physical_views.py:324`, where the `.text{overflow:hidden}` styles have no title clamp and no `white-space: nowrap` on the code.

**M4. The sign-out control is mislabeled and has no confirmation.**
- **What happens:** the profile button signs out on click. Its accessible name is its content, "J judge1 Admin", so screen-reader users never hear "Sign out"; the `title` attribute is not used as the name. Clicking your own name logs you out with no confirmation.
- **Location:** `apps/web/src/App.tsx:1197-1206`.

**M5. Some mobile touch targets are too small.**
- **What happens:** the Toggle menu button is 29×29 px, and the row preview and download icons are 24×30 px. Both are below 44 px. After a search, the first result starts about 750 px down a 844 px screen, below the hero, the stats, and saved searches (`m05`).

### Low

- **Mixed locales.** The Overview month labels follow the browser locale ("dic 25 … nov 26", "18/11/2026"), while the interface is English with "18 Nov 2026" elsewhere. Cause: `apps/web/src/OverviewPanel.tsx:30` uses `toLocaleDateString(undefined, …)`.
- **Italian leftovers.** In Italian, the Overview shows "No type", and the Agents audit shows raw action and outcome words ("set document filing", "denied", "error").
- **Ambiguous Revoke buttons.** All Revoke buttons have the identical name "Revoke", with no agent name, and revoking happens with one click and no confirmation. Revoked grants cannot be removed from the list (`apps/web/src/AgentPanel.tsx:216-223`).
- **Tag filter ignored by two MCP tools (code observation, not exercised live).** `list_tags` and `list_filing_options` return all of the owner's tags, senders, and types even for a tag-filtered grant (`services/api/archive/mcp_server.py:185-186`). This reveals names outside the grant's document filter.
- **Audit list lacks the document.** The UI shows which agent and which action, but not which document.
- **Raw exception text on Backups.** The page shows `[Errno 13] Permission denied: '/backup/staging'` on a failed row.
- **`correspondent:` returns nothing.** Paperless-style `correspondent:"…"` gives 0 results with no hint. `from:` works.
- **Paper archive has no shortcut.** There is no `g` shortcut for it, and Find a sticker offers no camera scan in the PWA.
- **Agent form stays filled.** After creating an agent, the form keeps the previous scopes and filter.

## Most serious finding

**H1:** sign-out and language selection cannot be reached on a standard 1440x900 laptop or a 390x844 phone, because the sidebar and drawer have no scroll. A first-time owner cannot sign out or switch to Italian from the place the app puts those controls.
