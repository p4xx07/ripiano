# Attention suggestions and calendar export review — 2026-11-24

Scope: local payment/event date detection, read access to suggestions, task preparation, calendar export, English/Italian labels, and desktop/mobile document views. Reviewed the completed diff and synthetic browser screenshots after implementation.

## Findings and changes

- A blank **Scadenza** field could borrow a date from the next field in the OCR text. Detection now requires the date to follow the label directly, allowing whitespace and a short installment phrase.
- That restriction initially missed a second **scadenza rata** and could suggest only the first of two installments. The full API run exposed this; the parser now recognizes the second label and suppresses the ambiguous suggestion. The focused test passes after the correction.
- The UI keeps suggestions optional. **Use as task** fills an editable form and requires Save; **Add to calendar** creates a local `.ics` file. Neither action sends a document to a calendar service or creates a task automatically.
- The endpoint applies the existing readable-document access check and returns no suggestion while OCR is pending. Paid receipts and unlabelled dates remain without a proposed task.
- Desktop and mobile screenshots show the suggestion inside the document essentials area. The event screenshot uses the same synthetic document after saving a payment task, so it is UI coverage rather than a clean product example.

No known high or medium finding remains in this slice. Detection is intentionally narrow: unlabelled dates, multiple future installments, event times, and some OCR layouts need manual handling. The `.ics` is an all-day event; opening it from installed iOS/Android apps needs real-device testing.

## Verification

- `cd services/api && RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_attention_suggestions.py`: **13 passed** after the date-label correction.
- `cd apps/web && npx tsc --noEmit -p .`: exit 0.
- `cd apps/web && npm run build`: exit 0; Vite's existing large-chunk advisory remains.
- Isolated synthetic stack on port 18122, desktop/mobile Playwright scenarios for attention, calendar file, document essentials, archive, paper location and missing copies: **12 passed**.
- Full API suite after the date-label correction: **480 passed, 17 skipped**. The preceding run found one multiple-installment failure, which was corrected and covered by the passing final run.
