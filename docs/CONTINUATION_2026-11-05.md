# Ripiano handoff — paused 5 November 2026

The user asked to pause until next week to preserve their weekly limit. Resume on branch `codex/initial-implementation` in draft PR [#1](https://github.com/p4xx07/ripiano/pull/1). Do not merge yet. The user has authorized merging into `main` **when the app is actually done** and its release gates pass.

## Current checkpoint

- Core archive, OCR/search, PWA capture paths, native Android debug scanner, automatic tag/sender/type phrase filing, physical stickers/locations, Telegram and watched-folder inputs, agent MCP grants, NAS backup output, and Library filters are implemented in prior commits. The last complete feature checkpoint is `d5208c9` (Library filters).
- This pause checkpoint adds only the SavedView backend: model/migration `0014`, owner-scoped GET/POST/PATCH/DELETE `/api/saved-views`, input validation, and API coverage. It has **no PWA controls yet**, so saved searches are not a finished user feature. The latest API suite passed 32 tests.
- The latest complete Library-filter slice passed 31 API tests, 24 desktop/mobile browser journeys, a production PWA build, and migration checks. Screenshots and details are in `qa-artifacts/963c996/library-filters`.

## Resume from here

1. Add the SavedView client type and PWA controls to create, reopen, rename/update, and delete saved searches. Keep mobile layout and keyboard focus usable.
2. Add a real desktop/mobile browser journey for save, clear, reopen, and delete. Run API tests, production build, migrations, and the full browser suite. Record screenshots and a QA artifact before the next checkpoint.
3. Update the draft PR description and continue the pinned [Paperless parity matrix](FEATURE_PARITY.md). The user's estimate request was answered as **roughly 75% of the full all-features project still remaining**; this is a planning estimate, not a score.

## Open gates and constraints

- This is a draft, with **no 9.5 judge score**. Storage paths, Office/email conversion and imports, custom fields, versions/PDF editing, workflows, wider permissions/sharing, export/import, localization, and other parity rows remain. Installed iOS/Android PWA capture, real Android scanner hardware, Synology ACLs/restore, and release images require verification.
- The independent code judge hit its usage limit during the targeted tag-rule slice. Do not mark that review as passed. The earlier filing-code and UX reviews cleared their findings.
- GitGuardian flags a **variable placeholder**, `${RIPIANO_DB_PASSWORD:?Set RIPIANO_DB_PASSWORD}`, in historical commit `c7e63c0` at `deploy/compose.portainer.yaml:12` as a generic password. It is not a literal credential, but the external check is red. Resolve that incident or the PR history before merging; do not weaken the Compose secret requirement.
- Backblaze B2 via Synology Hyper Backup is the user's configuration responsibility. Keep the draft PR and `main` separate until the user’s “when done” condition is met.
