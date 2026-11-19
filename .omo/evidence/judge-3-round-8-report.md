# Judge 3 — round 8 report

- Candidate SHA: `3dd08c2497a070475a249cf485184356a3a056c3` (running stack at http://localhost:18080; file:line references checked against HEAD)
- Date: 2026-11-19
- Reviewer account: `judge3` (archive owner/admin). Test sub-account created for this run: `j3r8-sub` (left turned off at the end).
- Browser: Playwright 1.64.1 (`npx playwright --version`), Chrome channel 157.0.8103.79. Desktop 1440x900; mobile emulation 390x844 with `isMobile`, `hasTouch`, DPR 2; locale it-IT.
- Emphasis: security and reliability (agent scopes/guards via MCP and workflows, D9/D10, password change and account off/on, workflow runs in Italian, upload validation and retries, whether the parity claims match the build).
- Artifacts: `qa-artifacts/20261119-r8-judge-3/` (14 PNGs; no tokens visible). Scripts, token files and state were kept in the session scratchpad folder `judge3-r8/`, outside the repository. Token files were deleted after use.

## Commands and scripts run

All scripts are in the scratchpad folder `judge3-r8/`:

| Script | What it did |
| --- | --- |
| `rc.py` | A small `requests` client: session sign-in with CSRF/Origin headers, and a JSON-RPC MCP helper (`POST /mcp`, bearer token) |
| `p1.py`, `p1b.py` | Created tags `j3r8-filterA`, `j3r8-filterB`, `j3r8-trigger` and `j3r8, comma; tag`; uploaded 3 fixtures; created agent A (search+text, filter A), agent B (search+tag+filing, filter B), sender `j3r8-sender`, and workflows W1 (updated, tag trigger → add filterA + comma tag) and W2 (updated, sender → add filterA); MCP `tools/list` and tool calls for scope and guard checks |
| `p2.py` | Single human edit, `add_tag_id`, bulk-tags; workflow runs in `it` and `en`; document history |
| (inline) | Agent activity log (it), revoke B, `?forget=1` with a wrong password, no body, and on an active agent |
| `p3.py` | Sub-account: token + agent + share link + bundle; then own password change, admin password reset, account off, account on; status of each credential after every step |
| `p4.py` + inline | Upload validation (empty, fake PDF, .exe, random bytes as .jpg), scan-ID retry with the same and a different file, invalid scan ID, missing CSRF, foreign Origin; truncated PDF → damaged flow → retry |
| (inline) | Personal API token limits (share link, bundle, agent, workflow), token on MCP, agent token on REST, session cookie on MCP, token revocation |
| `b1.mjs` | Desktop, Italian: Agents screen, D10 Remove with a wrong then the correct password, workflow runs screen |
| `b2.mjs` | Mobile, Italian: Library, search, document dialog (touch-target sweep, horizontal overflow), Add sheet, two invalid files through the gallery/file picker, Agents screen; desktop keyboard (Tab, `?`, `G`+letter) |
| `b3.mjs` | Desktop, Italian, as `j3r8-sub` after off/on: how the revoked links appear in the document dialog |

Run as `cd apps/web && node <scratch>/bN.mjs` (the Playwright module was imported by its absolute path) and `python3 pN.py` from the scratch folder.

**Fixture IDs used:** `three-pages.pdf`, `judge.png`, `office-letter.docx`, `outlook-notice.msg`, `office-sheet.xlsx`. Derived inputs made by me in scratch: an empty PDF, a text file named `.pdf`, an `MZ` stub named `.exe`, 2 KB of random bytes named `.jpg`, and `three-pages.pdf` cut to 60% of its length.

**Cleanup:** agents A and B revoked (B also removed through D10), the temporary personal API token revoked, W1 and W2 paused, `j3r8-sub` turned off. No active `j3r8` grant remains. No other account's data was touched.

## Scores

| Dimension | Weight | Score | Evidence (this run) | Not exercisable or not exercised |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.0 | Web/API upload of PDF, PNG, DOCX, MSG all `ready`. Mobile Add sheet offers camera, gallery, and file picker. Bad files are refused one by one with clear Italian reasons ("Il file è vuoto", "Impossibile leggere questo file come PDF…", allowed types listed), and "2 file su 2 non sono stati aggiunti" is announced (m04). Scan-ID retry: same file 200 with the same document, different file 409 with a clear message, invalid ID 400. A workflow-filed sender/tag shows in the Library. | Camera capture (emulation only), Telegram and watched folder (out of scope by D7 or not set up for this account). I did not exercise suggestion correction this round. |
| Retrieval and physical filing | 20% | 8.9 | Mobile search finds `j3r8-doc1`; the document dialog has a first-page preview, no horizontal overflow, and no target under 44 px (m02, m03). Document history attributes each change to a person, agent, or workflow. | Sticker scan, paper-copy move, label print/re-scan not repeated this round (my emphasis was security). |
| UX and accessibility | 20% | 8.8 | Italian across Agents, Workflows, Library, document dialog and errors. Workflow run details are translated, including a tag name containing ", " and "; " (d04). No horizontal scroll at 390 px. Dialog close and focus outlines are visible. `?` opens the shortcut dialog, `G`+letter navigates. D10 Remove flow: the password field is inline, the wrong password shows the `alert` "La password non è corretta", and success is announced in a `status`. | Real screen readers and installed PWAs (D7). Friction: see L1–L4. |
| Reliability and recovery | 20% | 9.0 | A truncated PDF is kept as the original, made partly searchable, marked failed with a precise Italian explanation, and listed for attention; retry is accepted (202). Upload validation refuses empty, fake, executable, and corrupt-image files before ingestion. CSRF is enforced (403 without a token and with a foreign Origin). The restore drill on this exact commit (`.omo/evidence/restore-drill-round8.md`) is credible: SHA-256 of originals, tags, nested location and sticker, and revoked versus active grant all checked after a clean-stack restore. | Restarting workers or containers and interrupting an upload mid-stream (not allowed on the shared stack). |
| Privacy and agent control | 15% | 8.8 | `tools/list` matches the scopes exactly (A: search, text; B: search, list_tags, change tags, filing options, set filing). A cannot read a document outside its filter. B cannot add or remove A's filter tag by ID or by case-insensitive name. B adding a trigger tag runs W1, which skips filterA and records why. B setting a sender runs W2, which also skips filterA. Revoke gives 401 on the next call. Activity log in Italian, including refused calls. D10: wrong password 400, no body 400, active agent 409. Own password change, admin reset, and account off all kill API tokens and agents; off also ends sessions; links and bundles give 404 after off and stay dead after on, and so do agents and tokens; a fresh sign-in works. API token boundaries hold: 403 for share link, bundle, agent, and workflow; 401 on MCP; agent token 401 on REST; session cookie 401 on MCP. | A cloud MCP client end to end (curl-level JSON-RPC only). Finding M1 lowers this score. |

**Weighted mean:** 0.25×9.0 + 0.20×8.9 + 0.20×8.8 + 0.20×9.0 + 0.15×8.8 = **8.89**

## Hard gates

| Gate | Demonstrated in this run? |
| --- | --- |
| 1. Parity rows have a working scenario or an accepted deviation | Partly. The rows I exercised (upload channels, OCR/damaged PDF, workflows, users/agents/tokens, share links and bundles with D9, localization, keyboard) match the running build. One wording mismatch is in L3. Rows not exercised this round: email, Sources, barcodes, versions, PDF editing. Not demonstrated in full. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | Accepted from `restore-drill-round8.md` (same commit, credible checks, including revoked grants and locations). Upload/OCR/search re-confirmed live. |
| 3. Installed iOS/Android PWA and native Android on real devices | Out of scope by owner decision (D7). |
| 4. Security review (isolation, revocation, CSRF, upload validation, input boundaries, no default content transfer) | Demonstrated for everything listed above, with the open finding M1. No document content left the stack (no provider configured; Ripiano only serves MCP). |
| 5. Tests, builds, journeys, migrations, deploy checks on the candidate | Not run by me (I may not rebuild or restart). The restore drill ran migrations through 0060 on an empty database. |
| DS923+ performance, ACLs, NAS restore; real Telegram and cloud accounts | Out of scope by owner decision (D7). |

## Findings

### Severe
None.

### High
None.

### Medium

**M1 — Public share links and bundles survive a password change and an admin password reset, and creating them needs no password.**
Changing your password (or an admin resetting it) is presented as the way to recover from a stolen session: it signs out other devices and ends API tokens and agents. Creating an agent or token even asks for the password "so a stolen session cannot leave a long-lived agent behind" (docs/AGENT_ACCESS.md). Public original-file links (up to 20 per document, up to 30 days) and share bundles (any selection of documents) are a stronger way to keep access, yet:
- they are created from a session with no password check (`share_views.py:33-67`, `bundle_views.py` `share_bundles`);
- they are not ended by `revoke_tokens_on_password_change` (`api_tokens.py:44-59` revokes only `ApiToken` and `AgentGrant`) nor by an admin reset (`people_views.py` `person_detail`; only `_end_access`, run on off/on, ends links);
- there is no account-wide list of active single-document links. `ShareLinksPanel` is only mounted per document (`DocumentPanel.tsx:906`) and there is no `/api/share-links` list route, so after a compromise the owner would have to open every document to find them.

Reproduction (`p3.py`): as `j3r8-sub`, create a link (`POST /api/documents/<id>/shares`) and a bundle. Change the password (`POST /api/account/password`). Token → 401, agent → 401, other session → 401, but the link → **200** and the bundle → **200**. The same happens after an admin reset (`PATCH /api/people/<id>` with `password`): link 200, bundle 200. Only turning the account off (D9) ends them.
The password panel text ("disconnects your API tokens and agents") is accurate, so this is a gap in the protection, not a false claim. D9 deliberately covered only deactivation; this case needs an owner decision. Options: end links and bundles on a password change or reset as well, offer "also end my share links" in the password panel, or at least add an account-wide active-links list and require the password to create a link.

### Low

**L1 — An agent's change can still lead, later, to another agent's filter tag being added.** Agent B (filing scope) sets sender `j3r8-sender` on doc3. W2 ("sender → add filterA") skips filterA because an agent made the change; this is correct. The next unrelated human edit (a title change) re-runs W2 because the condition still matches, and filterA is added, so agent A can now read the document. Repro: `p1b.py` then `p2.py`, doc3 runs in d04 ("non aggiunta" ×2, then "aggiunta l'etichetta j3r8-filterA" after the title edit). The owner's own rule fires on a human action, so this is arguably intended, but the condition was supplied by another agent. Mitigations: an "added by agent" provenance condition, or a note in AGENT_ACCESS.md.

**L2 — The workflow run status says "Applicato" when the run's only action was refused.** For example: "Applicato — etichetta j3r8-filterA non aggiunta (limita l'accesso…)". A "Saltato" or "Nulla applicato" status would read more truthfully (`workflows.py:302-330` always saves an applied status).

**L3 — The Workflows intro says "Each workflow acts once per document" (`locales/WorkflowsPanel.ts:73/206`), but "updated" workflows run on every matching update.** W2 ran 3 times on doc3 in this run; only notes, webhooks, and emails are once-only (`workflows.py` `first_time`). The parity row ("once-per-document runs") has the same wording. Suggested: "Notes, webhooks and emails are sent once per document."

**L4 — Revoked links do not say why and still show an expiry date.** After off/on, the owner sees "Revocato · Scade il 26/11/2026" in the document dialog (d07). The API returns `revoked_reason: "account_off"`, but no web component reads it (`grep revoked_reason apps/web/src` finds nothing). D9 says the owner "decides again", and the UI gives them no hint that the account being turned off ended the link.

**L5 — The Agents screen shows the whole activity log unpaged.** On mobile the page is about 17,000 px tall (m05). Recent activity should be paged or folded like the "Revocati o scaduti" group.

**L6 — Refusal outcomes are inconsistent in the activity log.** A guarded tag change is logged as `denied`, but an agent reading a document outside its filter is logged as `error` ("non riuscito"). For an audit trail, out-of-scope reads are the more interesting refusals.

## Most serious finding

**M1:** public share links and bundles, created without a password, outlive both a password change and an admin password reset. A stolen session can therefore keep anonymous download access for up to 30 days after the victim "secures" the account, and there is no account-wide list of active links to find them.
