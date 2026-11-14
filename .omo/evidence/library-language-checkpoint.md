# English-first Library language checkpoint

Scope: finish the daily Library localization slice already in progress, then defer further translation. English is the default on every device; Italian remains an explicitly selectable, partial preview. Selecting the device language is also explicit and persists across reloads.

Verification after the final changes:

- `npm run build` in `apps/web`: passed.
- `git diff --check`: passed.
- `e2e/language.spec.ts` on desktop and mobile: 4 passed, including an `it-IT` device with English default and explicit device-language opt-in.
- Existing English `e2e/filing-metadata.spec.ts` on desktop: 1 passed, covering sender/type management and Library filtering.
- Temporary browser-test account and its uploaded document were removed through the normal media purge path; the maintenance worker completed the cleanup job.
- Code and UX judges approved the Library slice in their separate reports. The independent gate judge could not run because its session hit a usage limit; this note does not claim a gate approval.

Further Italian coverage is tracked in `docs/FEATURE_PARITY.md` and deliberately deferred. The English Library controls and daily filing path remain the release priority.
