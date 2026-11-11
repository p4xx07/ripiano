# Ripiano quality gate

Target: an average score of **at least 9.5/10** from three independent reviews after the release candidate is feature-complete. A score is evidence of quality only when the reviewer uses a running stack and the same representative fixture corpus. A code-only impression is not a release score.

## Hard gates before scoring

1. Every capability in [FEATURE_PARITY.md](FEATURE_PARITY.md) has a working scenario or an explicit, accepted deviation. Missing parity is a release blocker regardless of average score.
2. Fresh installation, upload/OCR/search, backup, and clean-stack restore pass. The restored stack is checked for originals, tags, locations, and revoked grants.
3. Installed iOS PWA, installed Android PWA, and native Android client pass real-device capture and interrupted-upload scenarios. Browser emulation is useful during development, but cannot satisfy this gate.
4. Security review covers account and agent isolation, token revocation, CSRF, upload validation, external input boundaries, and no default transfer of document content to model providers.
5. Unit/API tests, production builds, browser journeys, migrations, and deployment checks pass on the candidate commit.

## Independent reviews

Each reviewer records a score from 0–10 for every dimension, a running-stack artifact, the most serious finding, and whether each hard gate was demonstrated. Reviews are performed independently before scores are compared.

| Dimension | Weight | Scenario |
| --- | ---: | --- |
| Capture and filing friction | 25% | Add a camera scan, gallery image, PDF, Telegram file, and watched-folder file. Retrieve all without visiting a mandatory TODO screen. Correct an uncertain suggestion in one screen. |
| Retrieval and physical filing | 20% | Find an OCR phrase, sender, date, and tag; scan a sticker; move a paper copy; print and re-scan its label. |
| UX and accessibility | 20% | Complete the same tasks on desktop, installed iOS PWA, installed Android PWA, and Android client with keyboard/screen-reader and touch checks. |
| Reliability and recovery | 20% | Interrupt upload and worker, restart services, retry, create a backup, and restore an empty stack without losing originals or permissions. |
| Privacy and agent control | 15% | Connect two agents with different scopes and document filters, inspect their tool lists and audit entries, revoke one, and confirm a cloud agent sees no content without text permission. |

The weighted mean of the three reviewers must be at least 9.5, every reviewer must score each dimension at least 9.0, and no severe unresolved finding may remain. A judge report includes exact commands, device/browser versions, fixture IDs, screenshots or traces, and the candidate commit SHA. Score changes require a new run, not a prose justification.

## Current development evidence

The current implementation has a local clean-stack restore drill, 54 API tests, 3 local-classifier tests, 2 Android origin tests, production PWA and native Android debug builds, and 46 desktop/mobile browser journeys for upload/OCR/search/tag/physical copy, typed custom fields with value and field-qualified search, visual custom-field filters and inclusive number/date ranges saved as reusable searches, field rename and guarded deletion, portable single-document ZIP export, reciprocal related-document links, printable shelf and box labels with nested-content lookup, missing/found paper-copy status with last known location and sticker lookup, OCR reprocessing with original-byte preservation, dated document notes, reversible Trash with owner/MCP/sticker isolation, correspondent and document-type management/search with Library filters, saved searches, field-qualified search, sorting, nested tag creation/moves and descendant-inclusive Library filters, bulk tag/sender/type filing, automatic phrase filing with manual corrections, mixed-validity batch upload, complete batch failure reporting, agent grant/revocation, optional follow-ups, exception-only Inbox, pagination, dialog focus, and rendered UI review. PostgreSQL checks cover reprocess/retry, note ownership/search/paging, precise search, bulk filing, and cursor behavior. Celery route checks and a live stack check show separate OCR and maintenance queues. A live watched-folder mount imported a file, processed it, and did not import it again after restarting the watcher. The isolated synthetic archive in `qa-artifacts/20261111-showcase` provides full desktop/mobile UI screenshots; its browser check confirms that document-date sorting shows the document date even in a western time zone. Dark and AMOLED themes have separate browser screenshots and checks of persistence, OS appearance, true-black tokens, and themed install manifests in `qa-artifacts/20261111-appearance`. The browser journeys use emulation. No Android device or emulator was available for scanner validation. The Paperless parity matrix, calibrated local classification, and other release gates are still incomplete, so **no 9.5 score or release claim is assigned**.
