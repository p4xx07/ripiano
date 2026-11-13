# Backup and NAS browse job controls

The desktop and mobile PNGs show the Backups screen with a synthetic failed NAS browse copy and its retry control. The browser test supplies deterministic API responses so the action state and responsive layout can be reviewed without racing a background worker.

`apps/web/e2e/job-controls.spec.ts` covers cancel, retry, unique accessible action names, keyboard focus restoration, and wrapped failure details on both viewports. `services/api/archive/test_job_controls.py` covers permissions, state transitions, worker no-op after cancellation, retry lineage, queue failure, and reconciliation. A separate local PostgreSQL check exercised cancel and retry endpoints and removed its synthetic records.
