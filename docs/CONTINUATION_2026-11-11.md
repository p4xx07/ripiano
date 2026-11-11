# Ripiano handoff — updated 11 November 2026

The user asked Codex to continue implementation regularly after the credit balance reset, with periodic GitHub checkpoints and judge-system evidence. Work in the real checkout `/Users/debotta/dbrepos/ripiano`, branch `codex/initial-implementation`, draft PR [#1](https://github.com/p4xx07/ripiano/pull/1). Do not return to the old temporary checkout. The user authorized merging into `main` **when the app is actually done** and its release gates pass; the draft is not at that point.

## Current checkpoint

- The foundation includes owner sign-in, durable upload/OCR/search, PWA capture paths, native Android debug scanner, phrase-based tag/sender/type filing, physical stickers and locations, Telegram and watched-folder inputs, scoped agent MCP grants, scheduled NAS backup output, and a clean-stack restore drill.
- The Library has filters, saved searches, contextual snippets, field-qualified search, signed-cursor sorting, and owner-scoped bulk tagging/sender/type filing. Bulk manual corrections survive later automatic filing. The API now requires a full PostgreSQL text-search match before ranking results, and Library cards show manual tags first.
- Documents now have dated searchable notes and a per-document OCR rebuild action. The reprocess browser journey verifies that original bytes remain identical after rebuilding the searchable PDF.
- Reversible Trash now preserves originals, notes, tags, physical stickers, and history. Search, downloads, needs-action views, bulk edits, and MCP access exclude trashed documents; sticker lookup gives a restore notice. The PWA has an explicit confirmation and a responsive Trash/Restore page. Processing documents cannot enter Trash until OCR finishes. There is no permanent purge yet.
- Reclassification and backup tasks use a `maintenance` Celery queue and worker; new uploads and retries use the separate `celery` processing queue. Both local and Portainer Compose examples include the new service.
- The latest feature checkpoint includes Trash/Restore. The local API suite passed **45 tests** with no pending migrations; the production PWA build passed; **32 desktop/mobile browser journeys** passed with three workers and a 120-second per-test limit. Trash evidence and screenshots are in `qa-artifacts/20261111-trash`, with earlier feature reviews in neighboring artifact folders. Update the draft PR body to reflect this checkpoint.

## Continue from here

1. Continue the pinned [Paperless parity matrix](FEATURE_PARITY.md) in reviewable feature slices. Verify each slice, record running-stack evidence, commit, and push the draft branch. Update the PR summary and judge evidence. Do not award a 9.5 score until the independent release reviews and hard gates actually pass.
2. Prioritize the remaining daily-use and parity gaps: permanent deletion/retention with a full integrity and backup review; storage/export layout; Office/email conversion and inputs; custom fields/document links; versions/PDF page tools; workflows; wider permissions/sharing; export/import; localization. Make each one an end-to-end user journey, not an API-only stub.
3. Keep the existing local test stack on port 18080 in mind. Its `localtest` archive contains many synthetic documents and phrase rules, so concurrent browser runs can queue long reclassification jobs. The separate maintenance worker reduced queue head-of-line blocking, but use controlled browser concurrency and inspect the worker queue if OCR waits. The NAS and real mobile hardware still need verification.

## Open gates and constraints

- This is a draft, with **no 9.5 judge score or feature-complete claim**. The parity matrix, calibrated local classification, installed iOS/Android PWA capture, real Android scanner hardware, Synology ACLs/restore, and released digest-pinned images remain open.
- GitGuardian flags `${RIPIANO_DB_PASSWORD:?Set RIPIANO_DB_PASSWORD}` in historical commit `c7e63c0` at `deploy/compose.portainer.yaml:12` as a generic password. It is a variable placeholder, not a literal credential, but the external check is red. Resolve that incident or the PR history before merging without weakening the Compose secret requirement.
- Backblaze B2 via Synology Hyper Backup is the user's configuration responsibility. Keep the draft PR and `main` separate until the user's “when done” condition is met.
