# Interim code review — c8a4a37

Scope: Android scanner shell, server-side scan idempotency, and watched-folder intake. This is not a release or 9.5 quality score: Paperless parity and real-device capture gates remain open.

## Evidence inspected

- Commit `c8a4a3778ebdda0c154c929854f54ca816385d34` and its changed source, migrations, CI, and tests.
- Existing test coverage in `services/api/archive/test_archive.py` and `test_watch_folder.py`.
- The executor's recorded build/test claims were not treated as sufficient proof of real-device behavior. No Android device/emulator scenario artifact was present.

## Skill-perspective check

The required `remove-ai-slops` and `programming` skill files were not available in either `/Users/debotta/.codex/skills` or `/Users/debotta/.agents/skills`, so their check was applied from the supplied criteria.

- **remove-ai-slops:** no deletion-only, tautological, or implementation-constant tests found. The new tests exercise owner-scoped idempotency and stable/revised watched-file behavior.
- **programming:** no untyped escape hatch or brittle prompt test found. The native implementation is necessarily imperative, although a real-device test is still absent.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

1. **Explicit default HTTPS port prevents native scanning and can externalize normal navigation.**
   `apps/android/app/src/main/java/io/ripiano/app/MainActivity.java:146-153` accepts and persists `https://host:443`. The same class then compares that literal string with WebView serialized origins and URL authorities at `199-203`, `215-218`, and `228-235`. Web origins serialize the default HTTPS port without `:443`; therefore the injected bridge rejects `postMessage("scan")`, and navigation can be sent to the external browser. Reproduction: configure the app with `https://nas.example:443`; after sign-in, press **Scan pages**. Normalize a default port away (or compare parsed origins) and add a regression test for it.

2. **An invalid watched file is retried and logged forever until it changes.**
   `services/api/archive/management/commands/watch_folder.py:42-50` only remembers the previous stat tuple. A malformed `*.pdf` or an image extension containing invalid data reaches `ingest_document`, raises `InvalidDocument`, and is retried every poll forever. This is common in a manually maintained incoming folder and produces repeated hashing, disk reads, and log noise; it never creates a visible failed-import record. Record a failed fingerprint (and retry only when it changes), or move failed intake items to an operator-visible error state. Add a test for unchanged invalid input.

### LOW

1. **No direct Android scanner lifecycle or upload-resume test exists.**
   The API tests validate the header contract, but there is no device/emulator test for ML Kit result delivery, private-file persistence, session-cookie upload, or interrupted upload. The README accurately says real-device validation remains a gate, so this is a known limitation rather than a success claim.

## Outcome

- `codeQualityStatus`: **WATCH**
- `recommendation`: **APPROVE** for this interim checkpoint, with the two MEDIUM findings scheduled before a mobile release candidate.
- `blockers`: none at HIGH/CRITICAL severity. Real-device capture remains a documented release hard gate, not satisfied by this review.
