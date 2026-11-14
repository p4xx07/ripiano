# Share-link gate review — 12 November 2026

## Recommendation

**APPROVE**

`blockers`: none

This approval is scoped to expiring, revocable original-file share links. It is not an R4, complete Paperless-parity, real-device, or 9.5 release approval.

## Original intent

Continue Ripiano toward the requested Paperless replacement while keeping the simpler NAS-first workflow and judge-reviewed checkpoints. For this slice, let a document owner give someone temporary access without creating an account, make the recipient reach and expiry clear, and allow access to be revoked.

## Desired outcome and criteria

- **SL-1 Controlled creation:** an authenticated document owner can create a bearer link with a bounded 1–30 day expiry, while another owner cannot manage that document's links.
- **SL-2 Minimal disclosure:** the public URL downloads only the preserved original bytes; it does not expose notes, OCR text, tags, metadata, or archive navigation.
- **SL-3 Token privacy and integrity:** only a cryptographic token hash is persisted, the raw URL is shown only on creation, and the server verifies the original size and SHA-256 before serving it.
- **SL-4 Revocation:** explicit revoke, expiry, and moving a document to Trash end future anonymous access; Restore does not silently reactivate a link.
- **SL-5 Concurrent boundary:** public authorization is serialized with revoke and Trash so a revoke that commits before a new authorization prevents that authorization.
- **SL-6 User experience:** the owner sees recipient reach, expiry, one-time URL handling, active/revoked state, and revoke controls in usable desktop and mobile layouts.
- **SL-7 Honest scope:** documentation states that links share originals only and leaves bundles, email sending, wider permissions, real-device checks, and R4/9.5 gates open.

## User outcome review

The scoped outcome is satisfied. The document panel explains that anyone holding the link can download without signing in, offers 1, 7, and 30 day choices, labels the URL as shown once, and lists exact local expiry time with a revoke action. The refreshed desktop and 390px mobile captures are token-masked, legible, and free of clipping.

The server stores a SHA-256 digest of a 32-byte random token, returns the raw URL only from creation, and omits it from later listings. Anonymous GET validates active, untrashed state under matching document/share row locks, verifies immutable original bytes, opens the file while authorization remains locked, and emits `no-store`, `no-referrer`, and `nosniff` headers. Revoke and both Trash paths use the same document-before-share order. Restore leaves revoked links revoked.

The README and parity matrix accurately state the recipient network requirement and that bundles/email remain future work. Broader release documentation continues to withhold the 9.5 score and merge claim.

## Artifacts checked

- Production: `services/api/archive/models.py`, `services/api/archive/share_views.py`, `services/api/archive/views.py`, `services/api/ripiano/urls.py`, `services/api/archive/migrations/0025_sharelink.py`.
- PWA: `apps/web/src/ShareLinksPanel.tsx`, `apps/web/src/DocumentPanel.tsx`, `apps/web/src/style.css`.
- Tests: `services/api/archive/test_share_links.py`, `services/api/archive/test_trash.py`, `apps/web/e2e/share-links.spec.ts`.
- Reviews/evidence: `.omo/evidence/share-links-code-review.md`, `.omo/evidence/share-links-clone-fidelity.md`, `.omo/evidence/share-links-live-check.md`.
- Visuals: `qa-artifacts/20261112-share-links/desktop/{created,revoked}.png`, `qa-artifacts/20261112-share-links/mobile/{created,revoked}.png`.
- Scope/docs: `README.md`, `docs/FEATURE_PARITY.md`, `docs/QUALITY_JUDGES.md`, `docs/CONTINUATION_2026-11-12.md`.

## Independent verification

- `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_share_links.py archive/test_trash.py` — **7 passed, 1 PostgreSQL-only case skipped**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` — **no changes detected**.
- `RIPIANO_DEBUG=1 .venv/bin/python manage.py check` — **no issues**.
- `docker compose --env-file .env.example exec -T api ... .venv/bin/pytest -q archive/test_share_links.py` — **3 passed on PostgreSQL**, including the concurrent revoke/authorization case.
- Final rebuilt-stack journey: `npm run test:e2e -- e2e/share-links.spec.ts` — **2 passed**, desktop and mobile. The first attempt occurred while the parent was recreating the stack and received connection-refused; the rerun after API/web health was green.
- `git diff --check` — clean.
- Direct inspection confirmed the refreshed screenshots show exact expiry time and no bearer token.

The live-check artifact also records the earlier complete **64/64** desktop/mobile browser pass and local **69 passing API tests**. I reproduced the scoped journey and all share/Trash tests rather than treating aggregate counts as sole proof.

## Adversarial and maintenance review

- Invalid token grammar, malformed JSON, boolean/string/out-of-range expiry, foreign-owner management, expired links, explicit revoke, single and bulk Trash, Restore non-reactivation, changed bytes, response headers, and exact public bytes are covered.
- The PostgreSQL test pauses authorization at the file-open boundary and proves revoke waits on the lock, then proves subsequent access is 404. It is implementation-aware because lock ordering is the security contract, but it is narrowly scoped and not tautological.
- The feature introduces one model, one focused view module, one small panel, and one migration. The shared `_media_path` reuse is justified and no speculative abstraction, redundant parser, untyped escape hatch, or production-only test hook was added.
- Tests verify user-visible and security-boundary behavior. They are not deletion-only, removal-verification, duplicated implementation logic, or excessive test volume.
- The code-review report explicitly applies the same unavailable-skill fallback and covers overfit, needless abstraction, maintenance burden, and false-confidence risks. I independently applied those criteria; `remove-ai-slops` and `programming` were not available as skills in this environment.

## Exact evidence gaps and notes

- No raw transcript for the aggregate 64-journey suite is committed; the live-check records it. The scoped final browser journey and server checks were independently reproduced, so this does not block SL-1 through SL-7 and must not be treated as R4 evidence.
- Browser mobile evidence is emulation, not an installed iOS/Android PWA. Real-device capture remains an explicit release gate and is not claimed by this slice.
- This feature shares one original at a time. Bundles and email delivery remain open in the parity matrix.
- An in-flight response whose file descriptor opened before revocation can finish. The lock establishes the enforceable boundary: a revocation that commits first prevents later authorization.
