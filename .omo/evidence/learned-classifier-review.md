# Learned filing classifier — independent review

Independent code/statistics/security/UX review of the uncommitted slice (reviewer did not edit).

## Fixed before commit
- **High — suggestions vanished during or after training:** any stored model is used whatever the run status; a failed run keeps the previous model and shows a generic message (details only in logs).
- **High — stuck "training":** runs record `started_at`; a run older than 35 minutes (beyond the task limit) is reported as stopped, so polling ends and a new run can start. Broker failures mark the request as failed.
- **High — training cost:** held-out scoring uses at most 1,000 documents, 100 tags, and 200 terms per document; 5,000 documents train in about 5 s. The nightly job skips people with no manual filing.
- **High — payload loaded per request:** `trained_at` is checked first; the payload is read only on a cache miss (LRU of 4 people per worker). People without a model cost one query.
- **Medium — features differed between training and prediction:** one feature path, the same 4,000 characters, terms capped by vocabulary frequency rather than alphabetically.
- **Medium — optimistic metrics:** precision, coverage, and Brier come from folds the calibration did not see (fit on even folds, measure odd, then swap); documents whose label was too rare to learn count as wrong guesses.
- **Medium — tag negatives:** tags train only on documents with a manual tag; rule/agent tags are excluded from evaluation.
- **Medium — tag coverage wording:** coverage is per document for every kind.
- **Medium — concurrent runs/status overwrite:** runs are claimed under a row lock; first-time record creation tolerates races.
- **Medium — retrain spam:** 10-minute cooldown after a run (429).
- **Low:** generic error text; status line is a live region; icon hidden from assistive tech; poll errors clear on success.

## Accepted (low)
- The vocabulary is chosen from all training documents, including held-out folds (slight optimism).
- Platt fit for the final model uses all held-out points; the reported numbers use the split described above.

## Verification
- `archive/test_learning.py`: learnable data gives ≥90% held-out accuracy and precision and confident correct suggestions; random labels give ≤10% coverage; old model survives failed runs; stale-run, cooldown, and broker-failure handling.
- Browser: `learning.spec.ts`, `filing-suggestions.spec.ts`, `auto-filing.spec.ts` pass on the local stack.
