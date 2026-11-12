# Filing suggestions gate review

Read-only gate judge verdict, transcribed from its completed agent report: **APPROVE**, no blockers. Scope: the filing-suggestions slice before its checkpoint commit. This scoped gate is not the R4/9.5 release score.

The judge reproduced these checks:
- the full API suite: 81 passed, 1 PostgreSQL-only skip;
- Django system and migration checks: no model changes;
- `tsc --noEmit` and the PWA production build;
- `git diff --check`.

It inspected the final desktop and mobile screenshots: one relevant tag suggestion, the icon inline, and no overflow. In the code, it confirmed:
- owner, trash, and status isolation;
- examples drawn only from manual filing;
- no data changes, no model call, and a bounded query cost (an `Exists` filter and a test capping the request at 8 queries);
- that every code and UX review finding was resolved;
- that the always-rendered `role="status"` regression in the notes and missing-copy journeys is fixed.

It judged the tests behaviour-focused and not overfit.

The judge confirmed why the agents and visual-review journeys failed (desktop and mobile). The Agents navigation needs `session.owner` (`is_superuser`), and the disposable browser account is not an instance admin. Those journeys and `App.tsx` are not part of this slice.

## Residual risks recorded by the judge

1. Rerun the 4 admin-gated journeys with an admin test account before release.
2. A status element inserted already containing text may not be announced by every screen reader, and a repeated identical message is not re-announced.
3. Suggestion fetch errors are hidden. This was accepted, because the box is optional.
4. Every browser upload uses the same fixture image, so matching quality on real OCR is shown only by the API tests.
5. The common-word threshold (max(4, 25% of examples)) and the 300-example cap are heuristics. Representative-archive measurement is still needed before any automatic filing.
6. The shared words come from titles and early OCR text, so users could over-trust a match on a few words. The UI does not show a confidence score.
