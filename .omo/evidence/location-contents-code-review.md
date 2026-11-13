# Location contents: present versus missing copies — code review

## Scope reviewed

Uncommitted diff against `94eedfb`: `location_lookup` now returns separate present and missing-copy counts; container pages list only copies currently present. The Physical archive screen explains the difference, and API/browser tests cover missing and found transitions.

## Evidence independently inspected

- `git diff --check`: clean.
- Focused physical API tests: `RIPIANO_DEBUG=1 .venv/bin/pytest archive/test_physical.py -q` — **3 passed**.
- Django checks and migration-drift check — **passed**.
- Code inspection of all response consumers found one typed client consumer, updated alongside the endpoint.
- The supplied evidence also reports a full API suite (**171 passed, 6 skipped**), production PWA build, and desktop/mobile physical-missing journey (**2 passed**). I treated that supplied execution evidence as supplemental rather than the basis for the focused verdict.

## Skill-perspective check

The `remove-ai-slops` and `programming` skill files were unavailable in the listed local roots. `omo ulw-loop status` was also unavailable because its installed runtime target is missing, so this report uses the required fallback path. I applied the requested criteria directly.

The production change has no unnecessary parsing, extraction, normalization, or abstraction: a filtered aggregate is the direct representation of the two user-visible states. Tests exercise state transitions and pagination-facing behavior rather than implementation constants. The browser assertions are not deletion-only: they verify the actual distinction between a missing historical record and a present copy, and its reversal after the copy is found. No brittle prompt test, untyped escape hatch, or implementation-mirroring test was found.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

## Assessment

`location_lookup` retains the existing owner, active-document, and descendant-location scope before splitting its aggregate counts ([physical_views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/physical_views.py:137)). The visible page and cursor are then correctly based on `missing_at__isnull=True`, so a missing sticker cannot occupy a slot or create a cursor gap in the list of copies that are actually present ([physical_views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/physical_views.py:142)). The API returns `missing_count` on every page, and `PhysicalPanel` preserves the first response's totals while appending further present-copy pages ([PhysicalPanel.tsx](/Users/debotta/dbrepos/ripiano/apps/web/src/PhysicalPanel.tsx:84)).

Focused tests cover hierarchy, owner isolation, Trash exclusion, missing/found transitions, and present-copy pagination. The browser journey also verifies the user-visible zero-present/one-missing state and the restored one-present/zero-missing state.

**Scoped score:** 9.7 / 10.

```json
{
  "codeQualityStatus": "CLEAR",
  "recommendation": "APPROVE",
  "reportPath": ".omo/evidence/location-contents-code-review.md",
  "blockers": []
}
```

## Follow-up review: recoverable missing-copy list

The first approach counted missing copies without listing them. This follow-up fixes that product regression: the endpoint now returns a separately paginated `missing_copies` collection, each containing the paper sticker and its document identity. It retains the present-copy list and its cursor independently ([physical_views.py](/Users/debotta/dbrepos/ripiano/services/api/archive/physical_views.py:137)).

The client keeps each cursor and accumulated list independent, so loading more missing copies cannot overwrite present copies, and vice versa ([PhysicalPanel.tsx](/Users/debotta/dbrepos/ripiano/apps/web/src/PhysicalPanel.tsx:90)). Missing records are displayed under a clearly historical heading and open their document through the established document action ([PhysicalPanel.tsx](/Users/debotta/dbrepos/ripiano/apps/web/src/PhysicalPanel.tsx:191)).

I independently reran the focused API suite (**3 passed**), `git diff --check`, Django checks, and the production PWA build. The supplied browser evidence reports the desktop/mobile live journey passing 2/2. The API test now proves 51 present plus 51 missing copies can page independently and validates each cursor ([test_physical.py](/Users/debotta/dbrepos/ripiano/services/api/archive/test_physical.py:122)); the browser test proves that a missing entry remains clickable and reappears in the present list when found ([physical-missing.spec.ts](/Users/debotta/dbrepos/ripiano/apps/web/e2e/physical-missing.spec.ts:58)).

The `remove-ai-slops` and `programming` skill files remain unavailable, so their requested criteria were applied directly. The independent lists and cursors are necessary for recoverability and bounded results; the updated tests verify user-observable behavior, not implementation constants. No new unnecessary parsing, abstraction, brittle prompt test, untyped escape hatch, or implementation-mirroring test was found.

No new findings. **Scoped score remains 9.7 / 10; `codeQualityStatus: CLEAR`; `recommendation: APPROVE`; blockers: none.**
