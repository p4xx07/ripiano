# Implementation plan

This plan sequences an independent Ripiano implementation. The parity baseline is Paperless-ngx v3.4.2; the first useful release is not described as full parity. Each milestone ends with a demonstrable user journey and a restore check.

## R0 — foundation and evaluation fixtures

1. Initialize the repository with an MIT license (as in Condivisa), contribution/security notes, pinned toolchains, CI, and a versioned Portainer Compose example. Do not copy Paperless source code.
2. Create `apps/web` (React/TypeScript/Vite/PWA), `apps/android` (Capacitor shell and native bridge), `services/api` (Django/DRF), `services/worker` (same Python package/image, separate process), and `deploy` (Compose/reverse-proxy examples). Keep API contracts in one versioned location.
3. Implement one HTTPS origin for web/API/MCP, initial owner setup, PostgreSQL migrations, task broker, health checks, and GHCR `linux/amd64` image publishing. Verify the complete stack on the DS923+ architecture before a release tag.
4. Assemble a privacy-safe fixture corpus: Italian and English scans, digital PDFs, Office files, receipts, letters, duplicate variants, barcodes, signed PDFs, and multi-page camera captures. Define expected metadata and search results. Real personal documents stay out of Git.
5. Build a component benchmark harness for OCR quality/time, document conversion fidelity, search relevance/time, classification precision/coverage, memory, and Android scanning reliability. Record versions and device conditions.

**Gate:** A fresh Portainer stack reaches a secure setup screen; CI builds; fixture data and benchmark commands are reproducible.

## R1 — safe archive vertical slice

1. User accounts/sessions, document ownership, permission checks, immutable original storage, checksums, upload idempotency, and processing job state.
2. Browser/file upload and watch-folder intake; PDF/image extraction, OCRmyPDF/Tesseract, archive PDF/A where supported, thumbnails and preview.
3. PostgreSQL full-text indexing and basic field/metadata filters; direct download of original and archive versions.
4. Initial PWA Add/Inbox/Library/document screens with Condivisa-inspired clarity and Ripiano's own visual tokens. No metadata is required to safely save a document.
5. First scheduled complete backup to a mounted volume and an automated clean-stack restore scenario.

**Gate:** Upload a fixture document, restart the stack, find its OCR text, download its original, and restore it from backup. A failed OCR job remains visible and retryable.

## R2 — low-effort daily filing

1. Sender rules, document types, tags/nested tags, dates, storage/export layout, and local pretrained classifier with evidence and calibrated thresholds. Corrections become examples. Add an exception-only review queue.
2. Physical-copy model, location hierarchy, sticker/box labels, QR lookup, movement history, and digital-only status.
3. Needs action, due dates, reminders, saved collections, duplicate review, bulk organize, and undo where feasible.
4. iOS/Android PWA capture and a Capacitor Android client with native multi-page scanner, gallery/files import, durable upload drafts, and fallback capture paths.
5. Initial named MCP agent grants and read/organize tools, including two agents with different permissions. Support an optional local Pi or personal-PC classifier worker and missed-run recovery for a 10:00 Mac job.

**Gate:** A camera capture becomes correctly searchable and filed without manual tagging when confidence is sufficient. A physical copy's label resolves to its location. Two agents see different documents and can perform only their granted operations. Real-device iOS and Android capture tests pass.

## R3 — advanced document management

1. Email ingestion and rules, optional Tika/Gotenberg conversion, barcode and ASN workflows, page splitting, and reprocessing.
2. Typed custom fields, notes, document links, versions, PDF editing, audit history, trash/restore, and advanced search syntax.
3. Full workflow editor with consume/add/update/scheduled triggers and assignment/removal/email/webhook/password/AI actions.
4. Users/groups/object permissions, 2FA/OIDC options, sharing links/bundles/email, a complete versioned REST API, and monitoring/task controls.
5. Expanded MCP tool set with per-operation scope step-up, bulk dry-run/approval, revocation, and audit. Optional local/remote AI suggestions, similarity, and document chat.

**Gate:** Each advanced path has an API test and a browser scenario; file-changing actions preserve history and signed-PDF warnings; permissions are enforced consistently in web, Android, REST, and MCP.

## R4 — parity, release, and operations

1. Audit every row in [FEATURE_PARITY.md](FEATURE_PARITY.md) against the frozen v3.4.2 upstream documentation and API. Fill gaps discovered by that audit.
2. Run comparative fixture tests against Paperless where behavior is expected to match, and specific Ripiano tests where behavior intentionally improves.
3. Verify backup retention, a clean-stack restore, upgrades with pre-upgrade backup, index rebuild, agent grant revocation, and NAS path permissions.
4. Complete accessibility, Italian/English localization, Android release build, PWA install guidance, responsive design review, and security review.
5. Publish a pinned image, the Portainer stack, operator guide, and user guide. Label the release feature-complete only after every parity row is verified.

**Gate:** The feature matrix is complete with evidence, all three client surfaces pass their real scenarios, and a clean installation can be restored from a scheduled snapshot.

## Cross-cutting engineering rules

- Keep canonical state in PostgreSQL and immutable media files. Search indexes, previews, and classifier caches are derived and rebuildable.
- Use explicit database transactions, idempotent jobs, and atomic file writes. Never report upload success before the original is durable.
- Apply the same permission service to REST, UI, background jobs, and MCP. Agent rights are always a subset of owner rights.
- Keep local rules and baseline classification working without a PC agent or external model.
- Pin runtime dependencies and image digests at releases; record migration and restore compatibility.
- Test behavior with representative files and real mobile hardware; avoid tests that only duplicate implementation details.
- Preserve the ability to export originals plus metadata in an open format so users can leave Ripiano.

## First implementation task

Start with R0 repository structure and the R1 upload-to-search vertical slice. Do not begin with a large settings surface or an AI agent. The first demo should prove that an original document survives upload, OCR, search, restart, and restore on the intended Compose stack.
