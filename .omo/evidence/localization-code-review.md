# Incremental English/Italian localization — code quality review

## Scope reviewed

Uncommitted localization groundwork plus the sign-in flow, app shell/navigation, Backups, selected filing/archive panels, and reviewed Italian API-error handling. This is **not** a review or approval of full-app localization parity.

## Evidence independently inspected

- Current dirty diff and untracked localization files, including `apps/web/src/i18n.ts`, `apps/web/src/locales/*.ts`, `apps/web/src/api.ts`, `services/api/archive/api_language.py`, and `services/api/archive/messages_it.py`.
- Client/API contract and security-sensitive middleware behavior: `Accept-Language`, `Vary`, `Content-Language`, JSON-only mutation, streaming-response exclusion, and Django translation override.
- Tests: `services/api/archive/test_api_language.py` and `apps/web/e2e/language.spec.ts`.
- Review-run verification:
  - `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_api_language.py -q` — **3 passed**.
  - `npm run build` in `apps/web` — **passed** (`tsc -b` and Vite/PWA build). Vite reports the existing/aggregate 530.56 kB minified main-chunk warning.
- Executor evidence additionally reported a clean full API suite (188 passed, 7 skipped), Django checks, and desktop/mobile E2E. Those results are consistent with the inspected tests, but are not substituted for the independent commands above.

## Skill-perspective check

The required `remove-ai-slops` and `programming` skills were searched for in the available local skill roots and were unavailable. Their documented perspectives were applied directly: tests were checked for deletion-only, tautological, implementation-mirroring, and brittle prompt-style assertions; production code was checked for untyped escape hatches and unnecessary parsing/normalization.

No violations requiring a MEDIUM-or-higher finding were found. The API tests exercise a real request/response path and the E2E tests cover sign-in, translated server error, persistence, navigation, and mobile sidebar behavior; they are not merely assertions of implementation constants. The AST catalog extractor is limited to test/source-catalog validation and has a stated purpose, rather than being unnecessary production parsing.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None. During review, stale localized fallback callbacks/effects were found; the final diff corrects them by including the message set in their dependencies (for example `apps/web/src/App.tsx:588-597`, `apps/web/src/CustomFieldsPanel.tsx:50-52`, and `apps/web/src/DocumentLinks.tsx:21-25`).

### LOW

1. The `system` preference resolves the browser language on initial load or when the selector changes, but does not subscribe to a browser/OS language-change event. An already open PWA will therefore keep its current language until reload or preference change after the device language changes. This is a low-frequency polish gap, not a correctness or security issue. `apps/web/src/i18n.ts:26-42`, `apps/web/src/i18n.ts:60-70`.

## Scope and regression assessment

The incomplete surfaces are accurately disclosed in `README.md` and `docs/FEATURE_PARITY.md`; they are out of scope for this incremental slice and do not masquerade as full parity. The middleware is scoped to `/api/`, only transforms non-streaming JSON objects with a top-level `error` string, preserves unknown messages, and adds `Vary: Accept-Language`, avoiding a cache-language mix-up. The localStorage preference and language header do not create an authorization or data-exposure path.

## Verdict

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- Scoped score: **9.4/10** for the incremental localization slice.
- `blockers`: None.
