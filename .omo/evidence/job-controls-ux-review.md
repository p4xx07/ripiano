# Job controls — scoped UX review

**Verdict:** APPROVE for this slice. This is not a score for Ripiano as a whole.

The initial review found repeated accessible button names, lost keyboard focus after a control disappeared, truncated failure details, and no explanation for running jobs. The final implementation gives each action a job-specific accessible name, moves focus to the replacement retry button or new run status, wraps error text, and explains why an active job cannot be stopped.

The reviewer inspected the desktop and mobile captures in `qa-artifacts/20261113-job-controls/`. Both have readable failure details and action targets. The browser journey asserts focus and text wrapping on both viewports. The reviewer judged the slice about 9.3/10 after fixes. A short UUID in the accessible name is unique but less friendly than a date and time; this is a low-priority future refinement.

The browser journey mocks job API responses to make queued and failed states deterministic. Actual API, worker no-op, and retry lineage were separately exercised on the local PostgreSQL stack with synthetic records that were removed afterward.
