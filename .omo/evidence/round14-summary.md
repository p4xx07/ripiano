# Round 14 quality gate — 22 November 2026

Candidate: `8a1ab1a82ab11186441656415d73e396f4b7a0e3` on `codex/initial-implementation`. Three judges independently tested pinned images from this commit on separate local Compose projects with the same 15-file corpus. Their firsthand reports and screenshots are [judge 1](judge-1-round-14-report.md), [judge 2](judge-2-round-14-report.md), and [judge 3](judge-3-round-14-report.md). D7 excludes real devices, real providers, and Synology checks from the numeric score; they remain owner-side checks.

| Dimension (weight) | Judge 1 | Judge 2 | Judge 3 |
| --- | ---: | ---: | ---: |
| Capture and filing (25%) | 9.5 | 9.4 | 9.4 |
| Retrieval and physical filing (20%) | 9.5 | 9.5 | 9.5 |
| UX and accessibility (20%) | 9.3 | 9.2 | 9.3 |
| Reliability and recovery (20%) | 9.1 | 9.3 | 9.5 |
| Privacy and agent control (15%) | 9.7 | 9.5 | 9.7 |
| **Exact weighted score** | **9.410** | **9.375** | **9.465** |

**Three-judge mean: 9.4167, reported 9.42/10.** This is +0.19 against round 12's reported 9.23, and below the 9.5 target. All individual dimension scores are at least 9.0.

## Findings and gate status

- **Medium, open:** a member opening a shared document while OCR is pending and the worker is stopped sees neither the processing state nor the recovery guidance visible to the owner. Judge 1 reproduced this on desktop and mobile; see [mobile capture](../../qa-artifacts/20261122-r14-judge-1/mobile-member-worker-stopped.png) and [desktop capture](../../qa-artifacts/20261122-r14-judge-1/desktop-member-worker-stopped.png). The shared panel's code has no processing-health rendering. The document completed when the worker restarted; this is a status/UX defect, not evidence of lost data.
- **Low, open:** worker-stopped guidance appears only after the current two-minute heartbeat grace period. Judges 1 and 2 observed it. An immediate failure could be confused with a normal queue delay, so this needs a considered UX change rather than assuming every short wait is a failure.
- The three judges demonstrated live upload/OCR/search, stopped-worker recovery, scoped MCP access and revocation, and clean-stack snapshot restore. Judge 2 also ran **458 passed, 17 skipped** API tests, **45 passed, 5 skipped** selected browser cases, web typecheck/build, migration/system checks, and Compose validation. The earlier full browser run (**407 passed, 49 skipped**) was on `5afee4e`; the candidate differs from that commit only in documentation/evidence and AGENTS.md, so it is supporting application-code evidence, but no fresh full browser suite ran in round 14.
- Row-by-row R4 parity verification and a complete independent security review remain open. The D7 real-device, provider, and NAS checks remain outside local judging and are not claimed as passed.

**Disposition at scoring time:** the 9.5 rubric target was **not met**, and the medium finding was open. PR #3 stayed in draft. The owner’s later decision and focused fix are recorded below; the numeric result is unchanged.

## Post-round owner decision — 22 November 2026

The owner accepted the 9.42 score as sufficient to begin personal testing, asked for the shared pending-document status defect to be fixed and committed, and explicitly requested no further judge round. The score above is still the score of `8a1ab1a`; it is not a score for the follow-up code. Focused verification of the fix is recorded in [round14-shared-status-fix.md](round14-shared-status-fix.md).
