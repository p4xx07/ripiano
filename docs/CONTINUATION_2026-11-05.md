# Ripiano handoff — updated 10 November 2026

The user wants exactly one feature completed per turn, then a stop so they can monitor credit usage and decide whether to continue. Resume on branch `codex/initial-implementation` in draft PR [#1](https://github.com/p4xx07/ripiano/pull/1). Do not merge yet. The user has authorized merging into `main` **when the app is actually done** and its release gates pass.

## Current checkpoint

- Core archive, OCR/search, PWA capture paths, native Android debug scanner, automatic tag/sender/type phrase filing, physical stickers/locations, Telegram and watched-folder inputs, agent MCP grants, NAS backup output, and Library filters are implemented in prior commits.
- Saved searches have owner-scoped API and PWA controls to create, reopen, rename, update criteria, and delete. The complete feature was checkpointed at `cb857fe`; desktop/mobile evidence is in `qa-artifacts/1896f45/saved-searches`.
- Search results now show a short match-centered excerpt from OCR text or action notes, or a matching sticker code. The unfiltered Library no longer repeats the beginning of every OCR result. Desktop/mobile screenshots and verification are in `qa-artifacts/cb857fe/search-snippets`.
- Field-qualified Library search now accepts title, OCR text, action note, tag, sender, type, sticker, and exact document date. Quoted names with spaces and combined clauses work; an in-app help panel explains the syntax. Desktop/mobile evidence is in `qa-artifacts/93eb784/field-search`.
- The latest API suite, production PWA build, migration check, and browser result are recorded in the field-search QA review.

## Resume from here

1. Wait for the user to choose or authorize the next feature. Complete one feature, verify it, commit/push a checkpoint, and stop again.
2. Continue the pinned [Paperless parity matrix](FEATURE_PARITY.md) in small slices. The earlier estimate was **roughly 75% of the full all-features project still remaining** before this saved-search slice; it is a planning estimate, not a score.

## Open gates and constraints

- This is a draft, with **no 9.5 judge score**. Storage paths, Office/email conversion and imports, custom fields, versions/PDF editing, workflows, wider permissions/sharing, export/import, localization, and other parity rows remain. Installed iOS/Android PWA capture, real Android scanner hardware, Synology ACLs/restore, and release images require verification.
- The independent code judge hit its usage limit during the targeted tag-rule slice. Do not mark that review as passed. The earlier filing-code and UX reviews cleared their findings.
- GitGuardian flags a **variable placeholder**, `${RIPIANO_DB_PASSWORD:?Set RIPIANO_DB_PASSWORD}`, in historical commit `c7e63c0` at `deploy/compose.portainer.yaml:12` as a generic password. It is not a literal credential, but the external check is red. Resolve that incident or the PR history before merging; do not weaken the Compose secret requirement.
- Backblaze B2 via Synology Hyper Backup is the user's configuration responsibility. Keep the draft PR and `main` separate until the user’s “when done” condition is met.
