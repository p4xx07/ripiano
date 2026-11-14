# Incremental Italian Library localization — code quality review

## Scope reviewed

Current uncommitted changes after `8620632`: Library browsing, search, filters, document rows, the add-document dialog, user-facing fallback errors, documentation, and the expanded language browser journey. This review does not certify full application localization.

## Evidence inspected

- Full current diff and the new typed `apps/web/src/locales/AppLibrary.ts` catalog.
- The Library’s React callbacks/effects in `apps/web/src/App.tsx`, including error fallbacks that can run after a language switch.
- The semantic labels and dialog name in the browser journey.
- Independent checks:
  - `npm run build` in `apps/web` — passed.
  - `RIPIANO_DEBUG=1 ./.venv/bin/pytest archive/test_api_language.py -q` — **3 passed**.
  - `git diff --check` — passed.

An initial concurrent mobile browser run exposed a test sequencing issue: the mobile sidebar stayed open while the scenario tried to use Library controls. The executor corrected that sequence to open the sidebar, choose the language, close it with its live close button, and only then operate the Library. Per coordination, this reviewer did not re-run shared Playwright output after that correction; the executor is responsible for the final non-concurrent desktop/mobile result.

## Skill-perspective check

The `remove-ai-slops` and `programming` skill files were searched under the available local skill roots but were unavailable. Their review criteria were applied directly. The added browser assertions test visible translated controls and an actual filter state rather than catalog constants alone. The production catalog is a needed typed translation boundary; it does not add unrelated parsing, extraction, normalization, untyped escape hatches, or abstraction.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None remaining. The new locale object is included in each callback/effect that uses it (`loadFilterOptions`, `loadDocuments`, and the native-upload listener), avoiding the stale-language closure defect previously found in the wider localization work.

## Verdict

- `codeQualityStatus`: **CLEAR**
- `recommendation`: **APPROVE**
- `blockers`: None, subject to the executor’s final non-concurrent desktop/mobile Playwright result.
- Scoped score: **9.4/10**. The remaining gap is intentionally documented: bulk Library actions, document detail, and other application areas remain outside this increment.
