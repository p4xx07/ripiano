# Document essentials UX review — 2026-11-23

Scope: document panel layout, English and Italian labels, responsive CSS, and existing browser regression expectations. Reviewed independently after the implementation and checked fresh desktop/mobile screenshots from the isolated synthetic stack.

## Findings and changes

- The previous first screen asked for ASN, sender, type, path, action, and tags before the person had a reason to edit them. The first screen now shows title, date, an honest OCR/filing summary, small task and paper actions, and filing suggestions when available. Advanced metadata is opened explicitly. Existing ASN/barcode behavior remains intact.
- Save is absent when nothing has changed, and remains mounted while a save is busy. An existing follow-up is summarized; Add task opens its status, date and note. Keep paper copy jumps to the paper section without generating a code on its own.
- Original and portable ZIP downloads are behind a labelled Files disclosure, with a short explanation. The searchable PDF and Retry OCR remain visible in Files.
- Focus after suggestions and after jumping to paper was checked. A shared document uses a different panel, so its existing download link remains directly visible.
- Fixed a stale guide claim that ASN was the physical sticker number. It remains a legacy barcode/import number until the approved sequential paper-code system is implemented.

No high or medium finding remains in this **layout slice**. Specialist sections below the essentials (custom fields, notes, history, sharing, page tools, paper details) still make the full panel long. Sequential paper codes and automatic task/date detection remain separate planned slices. The current local owner stack has not been rebuilt from this branch.

## Verification

- `cd apps/web && npx tsc --noEmit -p . && npm run build`: exit 0; Vite's existing large-chunk advisory remains.
- Final isolated web build: document essentials, Needs action, and note-save regression on desktop and mobile: **6 passed**.
- Broader direct desktop set for upload, automatic filing, ASN barcode splits, suggestions, original/ZIP export, Office import, and OCR retry: **10 passed**.
- Historical affected scenarios: **10 passed, 1 skipped, 1 failed due to an obsolete assertion that Save was visible on a clean document**. Updated that assertion and reran its scenario: **1 passed**. An earlier broad run was stopped after discovering the shared panel needed a conditional test helper; the focused shared-panel scenario then passed.
- Mobile export, filing, navigation and focus set: **7 passed, 3 skipped** (desktop-only cases).
- `git diff --check`: exit 0.
