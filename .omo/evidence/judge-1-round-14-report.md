# Judge 1 — independent round-14 quality report

**Candidate:** `8a1ab1a82ab11186441656415d73e396f4b7a0e3` on `codex/initial-implementation`
**Date:** 2026-11-22
**Result:** **9.41/10 weighted**, below the 9.5 review target. No severe finding observed; one medium and one low finding remain. The release hard gates are **not all demonstrated**. I did not read another round-14 judge report before completing this one.

I applied `AGENTS.md`, `docs/DECISIONS.md` D7, `docs/QUALITY_JUDGES.md`, `docs/FEATURE_PARITY.md`, and `docs/HANDOFF_2026-11-22.md`. D7 excludes real phones, real Telegram/cloud accounts, and DS923+ checks from the numeric score; they remain owner-side checks.

## Environment and evidence boundary

- Isolated project: `ripiano-r14-j1`, environment file `/private/tmp/ripiano-round14/j1/stack.env`, origin `http://localhost:18121`. API image `ripiano-r14-api:8a1ab1a` (`sha256:4a97072adcce48064f41019814c5a4ffb5bbc9bf6bcc33c11c795c654ce3d054`); web image `ripiano-r14-web:8a1ab1a` (`sha256:84138b5ddf412e235145d3a3a6aac1d786f865aa068d2ae0da5383c59770ab18`). Initial production-mode HTTP start was rejected as designed; I set `RIPIANO_DEBUG=1` for localhost HTTP and recreated this isolated stack.
- Restore project: `ripiano-r14-j1-restore`, separate database/media/backup volumes, same pinned images, origin `http://localhost:18124`. Port 18122 was occupied by another project, so I selected 18124 before its web container started.
- Chrome **157.0.8103.79** through Playwright **1.64.1**, desktop 1440×900 and emulated touch mobile 390×844, English locale; Docker Compose **5.5.0**; API virtualenv Python **3.13.5**. Browser scripts blocked service-worker registration to make each fresh context deterministic. This is browser emulation, not an installed PWA or physical scanner.
- Temporary usernames/passwords, setup key, database password, and MCP tokens stayed in mode-0600 files under `/private/tmp/ripiano-round14/j1`; this report and QA artifacts contain none of them. All screenshots are under [`qa-artifacts/20261122-r14-judge-1`](../../qa-artifacts/20261122-r14-judge-1/).

## Shared fixture corpus

I uploaded **all 15** files in `apps/web/e2e/fixtures` through the live upload API. Each upload returned 202, then reached `ready` with an archive file. I downloaded every original and compared its SHA-256 to its source file: **15/15 matched**, also **15/15 after clean-stack restore**. Barcode/ASN batch PDFs generated additional split records; the original source IDs below remained retrievable.

| Shared fixture | Document ID |
| --- | --- |
| `asn-batch-desktop.pdf` | `f62dbf8e-fd65-4785-af20-94cbd0310ec6` |
| `asn-batch-mobile.pdf` | `30f7db6f-1550-4e46-99d4-2f9f636bec0b` |
| `barcode-batch-desktop.pdf` | `8e4d34d9-9906-4ed0-8608-40507638fef2` |
| `barcode-batch-mobile.pdf` | `965147ef-9ef9-42ac-8c9a-1fcb4399bc45` |
| `email-notice.eml` | `a2ece431-c138-4b59-8065-5282cad2446e` |
| `judge.png` | `718dfd1f-bcdd-40ee-a844-b5ab8bc88ad4` |
| `office-legacy.doc` | `c1649279-2d1d-47aa-9dc6-f043318782ef` |
| `office-letter.docx` | `b04a65f4-45c7-4ea4-9db6-92f79c0476f3` |
| `office-open.odt` | `5bc51321-286e-49ef-ad92-f07dba759392` |
| `office-sheet.xlsx` | `bcdf6aae-5891-48fb-be0a-4915746c115a` |
| `office-slides.pptx` | `15559302-eb2a-49ae-bc5e-a8e42595f7cd` |
| `outlook-notice.msg` | `e2707ee3-aa37-4f2e-a3be-e55c47c9684e` |
| `tag-barcode-desktop.pdf` | `34163aa6-b854-4bc9-bb34-0f839ed94c99` |
| `tag-barcode-mobile.pdf` | `c5d4b735-3dca-4054-badd-29c6c60af425` |
| `three-pages.pdf` | `77204c94-09f5-4a39-87fe-d265ea4ce097` |

**Clearly derived fixtures, not part of the shared corpus:** `derived-worker.eml` (`074d3d60-1360-4089-85bd-70aa3c5f40d2`) for stopped OCR; `email-header-unrelated.eml` (`d6bd4167-75b6-44bd-8b9d-dbc7a026b44c`) sharing the email fixture's recipient, Date and header structure but with unrelated sender/subject/body; `email-header-related.eml` (`a90c7e01-bd88-4217-baaa-256e4a2b107b`) and `email-header-related-mobile.eml` (`ec67677c-e028-418c-bc51-7842fd90ea87`) with related TARI text. `member-waiting.docx` (`805a4e06-ee18-432e-a83b-8840a8ce1696`) reused `office-letter.docx` bytes under a new name solely for the shared pending-document probe. Derived files are in the judge's `/private/tmp` scratch area. Browser file-picker and offline uploads reused `judge.png` bytes under unique names.

## Scenario results

### Capture and filing — 9.5/10

- Desktop and touch-mobile browser Add dialogs offered camera, gallery, and file browsing. Live file-picker image uploads returned 202 and appeared in Library; screenshots: [`desktop-upload-dialog.png`](../../qa-artifacts/20261122-r14-judge-1/desktop-upload-dialog.png), [`mobile-upload-dialog.png`](../../qa-artifacts/20261122-r14-judge-1/mobile-upload-dialog.png), and the corresponding `*-uploaded.png` images. This tests the chooser flow, not a real camera capture.
- The built-in **Consume folder** imported a copy of `office-letter.docx`: `POST /api/sources/<id>/run` returned 202, the document became `ready` with source `folder`, and the input disappeared from `/consume`. This is a local watched-folder scenario.
- `email-notice.eml` and `outlook-notice.msg` reached ready with detected `2026-11-10` dates. Filing the first email with a manual `Judge private` tag did **not** suggest that tag for the unrelated MSG or for `email-header-unrelated.eml`. It **did** suggest the tag for the two related derived emails. The mobile jump link reached the suggestion; one tap persisted the manual tag and announced “Tag Judge private saved. Other edits still need Save changes.” See [`mobile-filing-suggestion-before.png`](../../qa-artifacts/20261122-r14-judge-1/mobile-filing-suggestion-before.png) and [`mobile-filing-suggestion-after.png`](../../qa-artifacts/20261122-r14-judge-1/mobile-filing-suggestion-after.png). No mandatory TODO screen was encountered.

### Retrieval and physical filing — 9.5/10

- Live API searches returned the expected fixture for `lampone`, `mirtillo`, `judge`, `text:lampone`, and `date:2026`; `office` returned five Office fixtures. Desktop/mobile Library search rendered the TARI row: [`desktop-search.png`](../../qa-artifacts/20261122-r14-judge-1/desktop-search.png), [`mobile-search.png`](../../qa-artifacts/20261122-r14-judge-1/mobile-search.png).
- I created `Study shelf` and nested `Blue box`, registered a physical copy of the email, moved it into the box, and fetched the sticker lookup and movement history (`move`, `placement`). The printable label endpoint returned HTML with an SVG QR. The same sticker route rendered a card with the destination and Move/Print/Open actions on both browser widths: [`desktop-sticker.png`](../../qa-artifacts/20261122-r14-judge-1/desktop-sticker.png), [`mobile-sticker.png`](../../qa-artifacts/20261122-r14-judge-1/mobile-sticker.png). I did not decode the printed QR with a physical phone under D7.

### UX and accessibility — 9.3/10

- Desktop/mobile browser Library, document, search, Add, sticker result, and suggestion screens rendered without page errors or horizontal overflow in the sampled views. `/` focused Search; `?` opened shortcuts. The targeted Playwright accessibility and offline-upload specs passed **6/6** across desktop/mobile (visible accessible names and labels, unique IDs, alt text, heading/landmark basics, keyboard navigation, skip link, and offline upload queue). Output directory: [`targeted-playwright`](../../qa-artifacts/20261122-r14-judge-1/targeted-playwright/). This is a basic automated audit, not a full screen-reader session or axe scan.
- **M1 below:** a family member opening a shared pending document did not get the owner-facing stopped OCR explanation. See [`mobile-member-worker-stopped.png`](../../qa-artifacts/20261122-r14-judge-1/mobile-member-worker-stopped.png) and the desktop counterpart.

### Reliability and recovery — 9.1/10

- I stopped only `ripiano-r14-j1`'s OCR worker and uploaded `derived-worker.eml`. `/api/jobs` eventually reported `pending: 1`, `worker.running: false`, `problem: worker_not_running`; desktop/mobile Library and the owner's document dialog explained the stopped recognition worker and that waiting files resume on restart. See `*-worker-stopped-library.png` and `*-worker-stopped-document.png` in the assigned QA directory. Restarting the worker took the pending document through `processing` to `ready` without reupload.
- A snapshot requested **while that document was pending** completed as `20261122T155742910192Z-4a01c748` in the isolated local named volume `ripiano-r14-j1_ripiano_backup`. I confirmed `/backup` was that project volume, not an external destination. I copied it only to the restore project's separate local Docker volume, restored into an empty database/media stack with the same pinned image, then started the services. Restored login succeeded; all 15 originals matched their source SHA-256; the manual tag, nested paper-copy location, and revoked agent state survived; the pending derived document reached `ready` after worker startup (about 36 seconds of polling). No restore data was sent to a NAS or cloud destination.
- Targeted desktop/mobile offline-upload tests passed, including the queued-on-device message and automatic send after reconnect. My separate exploratory mobile script observed a 202 after reconnect but sampled the queue message too early; I rely on the targeted test's awaited assertion for that claim.
- **L1 below:** the worker failure was not surfaced immediately, because the heartbeat had to become stale after about two minutes. The restarted worker then processed the waiting file promptly.

### Privacy and agent control — 9.7/10

- I created two distinct, one-day MCP grants with different tag filters: a “cloud metadata” agent with only `documents:search` filtered to `Judge private`, and a “local text” agent with `documents:search` + `documents:text` filtered to `Judge public`. The official MCP client saw only `search_documents` for the first and `search_documents` + `get_document_text` for the second. Each search saw only its own tagged email; cross-filter search returned no documents. Cloud text calls were denied, including on its in-filter document; local text read its own MSG but was denied the other document. Audit entries recorded `ok` and `denied` outcomes without document text.
- Revoking the cloud grant returned 200. Subsequent MCP GETs returned **401 `invalid_token`** on both original and restored stacks. The restored agent list kept `revoked_at` for that grant while the local grant remained active. A separate regular user got **404** for the owner's unshared email and **200** for the specific shared pending document. This establishes the tested scopes and isolation; it is not a network-egress audit of all possible third-party features.

## Findings

| ID | Severity | Evidence and impact |
| --- | --- | --- |
| **M1** | **Medium** | With the OCR worker stopped long enough for `/api/jobs` to report `worker_not_running`, the owner Library and document showed recovery guidance, but a regular member opening a **shared pending document** saw only the minimal shared-document card (added date, notes, history, original download). It showed neither the pending processing state nor advice to contact the archive owner. The backend document was still `pending`; the worker resumed it after restart. This is a real information gap for family readers, not a lost file. See `desktop-member-worker-stopped.png` and `mobile-member-worker-stopped.png`. I did not test a member-owned pending document. |
| **L1** | **Low** | Immediately after stopping the OCR worker, `/api/jobs` still reported `worker.running: true` and no problem while the last heartbeat was within its two-minute freshness window. After expiry it reported `worker_not_running` and the browser guidance appeared. A person can wait roughly two minutes without the explanation. The eventual recovery worked. |

No high or critical issue was demonstrated. I did not score the real-device/provider/NAS checks excluded by D7 as defects.

## Score calculation

| Dimension | Weight | Score | Weighted contribution |
| --- | ---: | ---: | ---: |
| Capture and filing friction | 25% | 9.5 | 2.375 |
| Retrieval and physical filing | 20% | 9.5 | 1.900 |
| UX and accessibility | 20% | 9.3 | 1.860 |
| Reliability and recovery | 20% | 9.1 | 1.820 |
| Privacy and agent control | 15% | 9.7 | 1.455 |
| **Weighted mean** | **100%** | | **9.410** |

Every dimension is at least 9.0, but this review's mean is below 9.5. The three-judge mean cannot be calculated from this independent report.

## Hard-gate status

1. **Parity row by row — not demonstrated.** The full `FEATURE_PARITY.md` R4 matrix still requires individual scenario evidence and accepted deviations; this judge sampled representative rows.
2. **Fresh install/upload/OCR/search/backup/empty-stack restore — demonstrated locally.** The restore checks above included original bytes, tag, nested location, revoked grant, and pending OCR recovery. This is a local Docker drill, not a NAS restore.
3. **Installed iOS/Android PWAs and native Android on real phones — untested owner-side check under D7.** No physical camera, interrupted native upload, or mobile screen reader was claimed.
4. **Security review — partial.** Live checks covered account/agent isolation, text scope, revocation, audit, and an observed CSRF rejection during an early request; I did not complete a full token/CSRF/upload-validation/external-input/network-egress audit.
5. **All candidate tests/builds/migrations/deployment checks — not demonstrated by this judge.** The pinned containers migrated and ran, and 6 targeted browser tests passed. The handoff's 458 API tests and full browser suite were on the earlier round-13 code; they do not substitute for a candidate-commit gate here.

Owner-side checks still open and **not scored** under D7: installed iOS/Android PWA, native Android capture/interrupted upload, real Telegram and cloud-drive accounts, DS923+ performance/ACL/restore, Pi gateway, and published-image validation.

## Reproduction commands

Commands used from `/Users/debotta/dbrepos/ripiano`; values inside `stack.env`, `restore.env`, `owner.txt`, `member.txt`, and `grants.json` were never printed or committed.

```sh
git rev-parse HEAD
docker image inspect ripiano-r14-api:8a1ab1a ripiano-r14-web:8a1ab1a --format '{{.RepoTags}} {{.Id}}'
docker compose -p ripiano-r14-j1 --env-file /private/tmp/ripiano-round14/j1/stack.env -f deploy/docker-compose.yaml up -d
python3 /private/tmp/ripiano-round14/j1/live.py
services/api/.venv/bin/python /private/tmp/ripiano-round14/j1/mcp_probe.py
python3 /private/tmp/ripiano-round14/j1/revoke.py
docker compose -p ripiano-r14-j1 --env-file /private/tmp/ripiano-round14/j1/stack.env -f deploy/docker-compose.yaml stop worker
python3 /private/tmp/ripiano-round14/j1/upload_derived.py
node /private/tmp/ripiano-round14/j1/worker_ui.cjs
python3 /private/tmp/ripiano-round14/j1/backup.py
docker compose -p ripiano-r14-j1 --env-file /private/tmp/ripiano-round14/j1/stack.env -f deploy/docker-compose.yaml start worker
python3 /private/tmp/ripiano-round14/j1/suggestions.py
node /private/tmp/ripiano-round14/j1/mobile_suggestion_ui.cjs
node /private/tmp/ripiano-round14/j1/ui.cjs
node /private/tmp/ripiano-round14/j1/ux.cjs
node /private/tmp/ripiano-round14/j1/upload_ui.cjs
# targeted Playwright run: accessibility.spec.ts and offline-upload.spec.ts,
# --workers=1 --output=qa-artifacts/20261122-r14-judge-1/targeted-playwright
# with RIPIANO_E2E_ORIGIN and test credentials passed via the Python subprocess environment

docker compose -p ripiano-r14-j1-restore --env-file /private/tmp/ripiano-round14/j1/restore.env -f deploy/docker-compose.yaml up -d db broker api
docker compose -p ripiano-r14-j1-restore --env-file /private/tmp/ripiano-round14/j1/restore.env -f deploy/docker-compose.yaml stop api
docker run --rm --entrypoint sh --user 0 -v ripiano-r14-j1_ripiano_backup:/src:ro -v ripiano-r14-j1-restore_ripiano_backup:/dst ripiano-r14-api:8a1ab1a -c 'mkdir -p /dst/complete && cp -a /src/complete/. /dst/complete/'
docker compose -p ripiano-r14-j1-restore --env-file /private/tmp/ripiano-round14/j1/restore.env -f deploy/docker-compose.yaml run --rm --no-deps api .venv/bin/python manage.py restore_snapshot 20261122T155742910192Z-4a01c748 --yes
docker compose -p ripiano-r14-j1-restore --env-file /private/tmp/ripiano-round14/j1/restore.env -f deploy/docker-compose.yaml up -d
python3 /private/tmp/ripiano-round14/j1/restore_verify.py
```

The shared corpus upload command was `node /private/tmp/ripiano-round14/j1/api.cjs`; it uploaded each file once with the live session and saved response IDs to scratch. The consume-folder probe copied `apps/web/e2e/fixtures/office-letter.docx` into this project's maintenance container at `/consume/j1-office-letter.docx`, then requested its source run. The member probe used `python3 /private/tmp/ripiano-round14/j1/member_setup.py` and `node /private/tmp/ripiano-round14/j1/member_ui.cjs` while this project's OCR worker was stopped.
