# Ripiano continuation — 12 November 2026

Work in `/Users/debotta/dbrepos/ripiano` on `codex/initial-implementation`, draft PR [#1](https://github.com/p4xx07/ripiano/pull/1). The user authorized periodic commits/pushes and merging into `main` only when the app is actually complete and its release gates pass. Keep the draft separate until then.

## Current state

- The daily archive has durable upload/OCR/search, phrase filing, typed custom fields, notes, links, physical stickers and nested locations, Telegram and watched-folder inputs, scoped MCP agents, a PWA, a native Android debug scanner, and checksum-verified NAS backup output. The [parity matrix](FEATURE_PARITY.md) tracks broader Paperless capabilities still missing.
- Trash supports restore, confirmed permanent deletion, backup-locked live-file cleanup with durable retry, and per-owner automatic retention. Retention is disabled by default. The owner can choose 30–3650 days, preview the number currently eligible, and confirm a daily 03:00 Europe/Rome task. Turning it off stops future selection; already queued cleanup finishes. Existing snapshots and Synology Hyper Backup have separate retention.
- This retention slice passed 64 API tests, migration/system checks, a production PWA build, and 58 desktop/mobile browser journeys. A real local maintenance-queue run removed a 31-day-old synthetic trashed document and its live file; a later snapshot verified 2,659 media checksums. Code, UX, and gate judges approved. Evidence is in `.omo/evidence/trash-retention-*` and `qa-artifacts/20261112-trash-retention`.
- The local Compose test stack is on port 18080. Set both `RIPIANO_PORT=18080` and `RIPIANO_PUBLIC_ORIGIN=http://localhost:18080` for local browser tests; otherwise CSRF origin checking rejects sign-in. The test archives contain synthetic documents. Do not use the former temporary checkout.

## Next slices

Prioritize storage paths and export layout, Office/email conversion and inputs, custom-field type changes, file versions and PDF page tools, workflows, wider human permissions and sharing, complete archive export/import, and Italian/English localization. Make each slice a real user journey, run relevant API/browser/restore checks, have the scoped judges review it, then commit and push the draft branch and update the PR summary.

The 9.5 release score is **not assigned**. Calibrated local classification, real iOS/Android PWA capture, real Android scanner hardware, Synology ACL/restore validation, published digest-pinned images, and remaining parity rows are still open. GitGuardian still flags a historical Compose environment-variable placeholder; the PR check must be resolved before merging. Backblaze B2 configuration remains the user's Synology responsibility.
