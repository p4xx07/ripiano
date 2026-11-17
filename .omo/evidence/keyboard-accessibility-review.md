# Keyboard and accessibility — independent review (2026-11-17)

Scope: commit `76774b3`; global keyboard handler, shortcut dialog, skip link, accessible names, and `e2e/accessibility.spec.ts`.

Evidence: web type check and production build passed. Read the shortcut guard: it excludes modifier keys, text fields, content-editable controls, and open dialogs. The browser test covers sign-in, major screens, shortcut dialog, Library row navigation, and skip-link focus.

No high/medium code finding from the inspected path. The browser test was not rerun in this review; the existing check is a basic DOM audit, not a complete assistive-technology or axe scan. Those remain R4 validation limits and do not justify adding an unapproved dependency.

Final full API verification after the review fixes: `243 passed, 9 skipped` (`RIPIANO_DEBUG=1 .venv/bin/pytest -q`).
