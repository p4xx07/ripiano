# Judge 2 — round 12 report

- **Candidate:** `71315f4531f0ef02d0205aa77bfdce0019c9c127`. The checked-out HEAD is `57c76a3`, which adds only evidence files on top of it. The running stack `ripiano-j2` was built from the candidate.
- **Date:** 2026-11-20, 11:15–11:45 CET
- **Stack:** http://localhost:18102, Compose project `ripiano-j2`. It started empty; I did first-time setup through the UI with the setup key.
- **Browser:** Playwright 1.64.1 (`npx playwright --version`), Chrome channel, Google Chrome 157.0.8103.79, macOS (Darwin 25.6.0).
  - Desktop runs used a 1440x900 viewport.
  - Mobile runs used emulation: 390x844, `isMobile`, `hasTouch`, DPR 2.
  - The browser locale is Italian, so most journeys ran in Italian. One keyboard run switched to English.
- **Screen reader:** none installed. I used Playwright's `ariaSnapshot()` as a stand-in.
- **Artifacts:** `qa-artifacts/20261120-r12-judge-2/` holds 40 PNGs, with token values blurred.
- **Scripts:** all scripts, passwords and agent tokens are in the scratch folder `/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j2r12/` (none in the repository).

## Commands and scripts

- **API suite:**
  - Command: `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q`
  - Result: `457 passed, 17 skipped in 78.92s`, which matches `round12-verification.md`.
- **Compose wrapper (`dc`):**
  - `docker compose -p ripiano-j2 --env-file …/jstacks/j2/stack.env <cmd>`
  - I used it for `kill worker`, `start worker`, `stop/start api`, `stop/start broker`, `down -v`, `up -d db broker api`, `stop web worker maintenance_worker scheduler mcp api`, and `run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261120T103444018773Z-3d623b1b --yes`.
  - I also used it to copy a file into the maintenance worker's `/consume` (`cp … maintenance_worker:/consume/`).
  - Read-only checks used `exec -T api /app/.venv/bin/python manage.py shell`.
- **Browser scripts (Node, under the scratch folder):** `setup.mjs`, `up1/up2.mjs` (camera / multi-file), `gal.mjs` (gallery on mobile), `file2.mjs` (filing), `correct.mjs` (mobile suggestion correction), `search.mjs`, `paper.mjs`, `sticker.mjs`, `rescan.mjs`, `agent.mjs`, `revoke2/3.mjs`, `apidown.mjs`, `brk.mjs`, `backup.mjs`, `marta.mjs`, `orig.mjs`, `kbd.mjs`, `focus*.mjs`, `mob.mjs`, `i18n.mjs`, `sec.mjs`, `dup.mjs`.
- **MCP client:** `mcp.mjs`, a Streamable-HTTP JSON-RPC client using bearer tokens.
- **Label QR decode:** a screenshot of the label's SVG was decoded with pyzbar inside the stack's own worker container. It decoded to `http://localhost:18102/?sticker=R-WXTNYMUQ`.

## Fixture IDs used

`judge.png` was uploaded through the camera button, the gallery button (mobile), and again while the worker was down.

The following were added with Browse files: `three-pages.pdf`, `office-letter.docx`, `email-notice.eml`, `office-sheet.xlsx`, `office-open.odt`, `outlook-notice.msg`, `office-slides.pptx`, `office-legacy.doc`, `asn-batch-desktop.pdf`, `barcode-batch-desktop.pdf`, `tag-barcode-desktop.pdf`, `barcode-batch-mobile.pdf`, `asn-batch-mobile.pdf`, `tag-barcode-mobile.pdf`.

`outlook-notice.msg` was also dropped into the consume (watched) folder as `cartella-outlook-notice.msg`.

Edge probes used two files I generated in the scratch folder, not from the corpus: `fake.pdf` (bytes that are not a PDF) and `x.html`.

## Scores

| Dimension | Weight | Score | Evidence (exercised) | Not exercisable / out of scope |
| --- | ---: | ---: | --- | --- |
| Capture and filing friction | 25% | 9.2 | See capture and filing evidence below. Friction: the near-identical `asn-batch-mobile (1/2)` got no suggestion, and the hint text suggests the user has filed nothing similar (L1). Accepting a suggestion saves at once while other edits need Save; the UI says so, but it is a mixed model. | Telegram file and real camera capture: out of scope by owner decision |
| Retrieval and physical filing | 20% | 9.4 | See retrieval evidence below. Friction: the new-copy location picker shows "Ancora nessuna posizione" as its placeholder even when locations exist (L2). | Real camera QR scan (desktop Chrome has no BarcodeDetector; the emulated camera has no permission and shows a clear fallback, see 38) |
| UX and accessibility | 20% | 9.2 | See accessibility evidence below. Friction: the worker-down explanation appears only on Overview (M1). The emulated camera dialog blames camera permission. | Installed iOS/Android PWA, Android client, real screen reader: out of scope; ariaSnapshot used instead |
| Reliability and recovery | 20% | 9.3 | See reliability evidence below. Friction: while the worker is down, the Library card and the document dialog only say "In attesa" or "L'anteprima compare quando l'elaborazione è finita"; the explanation and the fix are only on Overview (M1). | NAS restore: out of scope |
| Privacy and agent control | 15% | 9.5 | See privacy evidence below. Limitation: an agent can be limited to only one tag (single select). | Real cloud agent client: out of scope (the MCP protocol was exercised directly) |

**Capture and filing evidence**

- Camera input (`capture="environment"`), gallery, 8-file mixed batch (PDF, Office, legacy DOC, ODT, EML, MSG) all reached Ready within about 10 s. The batch reported "Aggiunti 8 documenti". The email title came from its Subject. Barcode PATCHT split and ASN codes worked.
- The consume folder imported a file in about 48 s and removed it from the folder (`source=folder`).
- Nothing required a TODO screen. Inbox lists only exceptions (exact copies).
- Suggestions were learned after filing 4 documents. They are explained ("Simile a … · in comune: separator, letter, meadow, quokka").
- On mobile I accepted the sender, rejected the tag, picked another tag and type, and saved, all in one dialog (11, 12).
- The exact-copy flag is byte-accurate (checked by sha256).

**Retrieval evidence**

- UI searches all returned the correct sets:
  - OCR phrases: `heron` and `9473` (OCR from the PNG), `mirtillo`, `girasole`, `wombat`
  - Sender: `sender:"Quokka Srl"` and plain `Quokka`
  - Tag: `tag:casa`
  - Date: `date:2026-11-10` and `2026-11-10`
- Paper archive steps:
  1. Created nested locations, then a sticker R-WXTNYMUQ.
  2. The lookup accepts lowercase input. The sticker result now has Move / Missing / Print / Open (18).
  3. The printed label QR decodes to `/?sticker=R-…`. Opening it on mobile lands on the sticker result. Moving the copy there was recorded in history (19, 20).

**Accessibility evidence**

- Keyboard: the skip link works; `/` focuses search; `J` and Enter open a document; Esc returns focus to the item; `N` opens Add; `?` opens the shortcut list; `G P` goes to the paper archive.
- The focus ring is visible (3px outline plus halo). Result counts are announced in a live region ("2 documenti trovati").
- At 390 px there is no horizontal overflow on 11 screens. Tag checkboxes sit inside 350x44 labels.
- I found no English strings on 17 Italian screens. The English switch works.

**Reliability evidence**

- **Worker killed (idle):** the upload waited, `/api/jobs` reported `worker_not_running`, and the document was Ready 5 s after the worker restarted.
- **Worker killed mid-processing** (`asn-batch-desktop.pdf`): the state became "stalled" after 2 min. The Library then explained that it would retry by itself and offered "Riprova subito". It was requeued automatically at about 3 min and split exactly once.
- **API stopped during a mobile upload:** "Aggiunta 2 di 2…" was held. After the API restart both files arrived exactly once (30, 31).
- **Broker stopped:** the upload was accepted as "In attesa" and was Ready 30 s after the broker restarted.
- **Backup and restore:**
  1. Backup from the UI completed (34).
  2. `down -v`, then a restore into empty volumes following BACKUP_RESTORE.md.
  3. All 70 of 70 manifest files are sha256-identical after restore. Previews are excluded by design and are rebuilt.
  4. DB inventory is identical: 35 docs, 4 tags, 3 locations, 1 copy, 2 grants (1 revoked), 1 share, 53 events.
  5. Originals equal the fixtures. The revoked token still returns 401 and the active token still works. Marta still sees only the shared document; the owner's private original returns 404 for her.

**Privacy evidence**

- I created two agents in the UI:
  - "Assistente locale": search, OCR text and tags, on all documents.
  - "Assistente cloud": search only, filtered to the `casa` tag.
- `tools/list` showed 4 tools versus 1.
- Scope checks on the cloud agent:
  - It cannot see `wombat` (not tagged casa).
  - It gets no hits for body-only words (`Riunione`, `meadow`), so search cannot be used to probe document text.
  - `get_document_text` is refused and audited as "rifiutato".
- The audit list names the agent, the action and the document, but not the query text.
- Revoke uses an inline confirmation; the next MCP request returns `401 invalid_token`. Revocation survived the restore. Both grants were revoked at the end.
- CSRF: a POST without a token returns 403, and a POST from a foreign Origin returns 403. Uploads are validated: the fake PDF and `.html` are rejected with clear messages.

**Weighted mean:** 0.25·9.2 + 0.20·9.4 + 0.20·9.2 + 0.20·9.3 + 0.15·9.5 = **9.31**

## Hard gates

| Gate | Result |
| --- | --- |
| 1. Parity scenarios | Partially demonstrated by me: upload channels, Office/email conversion, barcodes/ASN/split, tags/senders/types, suggestions, search syntax, paper copies, sharing, agents, backup/restore. I did not re-verify every FEATURE_PARITY row in 30 minutes; I found no missing capability in what I touched. |
| 2. Fresh install, upload/OCR/search, backup, clean-stack restore | **Pass** on my own stack. See the reliability evidence: originals, tags, locations, revoked grants and sharing were all checked after `down -v`. |
| 3. Installed iOS/Android PWA, native Android | Out of scope by owner decision (D7). |
| 4. Security review | Pass for what I exercised: account isolation (404 on another user's original), agent tool and tag scoping, no text probing through search, token revocation, CSRF, upload validation, no external model calls (semantic search off). This was not a full code security review. |
| 5. Tests and builds | Credible. I re-ran the API suite with the same result (`457 passed, 17 skipped`). The verification record lists commands and result lines for the type check, build, migrations and 402 e2e passes. As instructed, I did not re-run the build or e2e. |
| Synology DS923+ performance/ACL/NAS restore, real Telegram/Google/Microsoft/Dropbox | Out of scope by owner decision. |

## Findings

**Severe:** none. **High:** none.

**Medium**

- **M1: the worker-down explanation is shown only on Overview.**
  - Repro:
    1. Run `dc kill worker`.
    2. Upload `judge.png` from the Library (mobile or desktop).
    3. Wait more than 2 minutes.
  - Result:
    - `/api/jobs` returns `problem: "worker_not_running"`, and Overview shows "il riconoscimento del testo non è attivo … Avvia di nuovo il container worker".
    - The Library, where the upload happened, shows only "In attesa" with no banner (26).
    - The document dialog says "L'anteprima compare quando l'elaborazione è finita" (29).
    - The Inbox shows nothing.
  - Impact: a family member who uploads gets no hint that processing has stopped.
  - Cause: `JobsPanel`, which renders `problemWorker`, is mounted only in `OverviewPanel.tsx:142` (`git show HEAD:apps/web/src/OverviewPanel.tsx`). The Library and DocumentPanel never read `processing.problem`.

**Low**

- **L1: no suggestion for a near-identical document, and the hint is misleading.**
  - Repro:
    1. File `asn-batch-desktop (1/2)` as Quokka Srl / Lettera / lavoro.
    2. Upload `asn-batch-mobile.pdf` and open part (1/2).
  - Result: `/filing-suggestions` and `/similar` are empty. The text is "Firstdocument DESO oie Firstdocumentcontinued", which has too few shared terms. The dialog says "I suggerimenti compaiono qui dopo che hai archiviato alcuni documenti simili", although the user just did (42).
- **L2: the new-copy location placeholder is wrong when locations exist.**
  - Where: Document dialog, Copie cartacee.
  - Result: the select's empty option reads "Ancora nessuna posizione" / "No location yet" even when three locations exist.
  - Cause: `apps/web/src/DocumentPanel.tsx:1431` always renders `m.noLocationYet`.
- **L3: accepted suggestions are recorded as manual filing.** Accepting a suggestion stores `correspondent_origin: "manual"` and tag origin `manual`, so history cannot distinguish an accepted suggestion from manual filing.
- **L4: the broker outage is not reported quickly.**
  - Repro: stop the broker and upload.
  - Result: in the first about 20 s, `/api/jobs` reported `problem: null`, state `queued`. I did not wait long enough to see whether `queue_unavailable` appears later.
  - Recovery was automatic.

## Most serious finding

M1: when the OCR worker is down, the problem and its fix appear only on the Overview screen. The Library and document views, where people upload and look for their document, show an unexplained "In attesa".

## Notes

- My first agent-creation script echoed one agent token into my local terminal output; it never reached the artifacts or the repository. I revoked that grant (and the other one) before finishing; both now return 401.
- The stack is left running, restored from the snapshot.
