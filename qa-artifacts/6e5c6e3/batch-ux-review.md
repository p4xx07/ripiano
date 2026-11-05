# Batch upload UX judge follow-up

Base commit: `6e5c6e3`.

The UX judge found two medium issues: only the first three rejected filenames remained in the result, and upload progress lacked a live announcement. The Library now shows every rejected filename and reason in an expandable report when a batch has more than three failures. The current file number is a polite, atomic status announcement.

Verification: `npm run build` passed; the local Compose web image rebuilt and started; all 20 desktop/mobile Playwright journeys passed. The added 4+ failure journey pauses the second upload, verifies the status says “Adding 2 of 5,” opens the report, and checks all five filenames. The existing mixed-validity journey confirms later valid files still upload and the report survives a Library refresh. Rendered [desktop](batch/desktop/rejected-files.png) and [mobile](batch/mobile/rejected-files.png) captures were inspected; the expanded list wraps within the viewport.

The test uses a disposable synthetic account and real API rejection of unsupported text files. Browser emulation does not satisfy installed PWA or native scanner hardware gates.
