# Match modes and similar documents review

An independent read-only reviewer of the rule match modes returned **REQUEST CHANGES**: 1 high, 2 medium, and 6 low. It ran a timing probe against `classification.py`.

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | Regex ReDoS. The nested-quantifier heuristic was bypassable (`((a+))+b`, `(a\|a)*b`, adjacent quantifiers), and the 100k cap did not bound time. `apply_rules` held the owner and document locks while matching. | Regex mode uses the `regex` package with a hard **0.25 s timeout** per search; a timeout counts as no match and is logged. `apply_rules` now evaluates every rule **before** taking locks, then re-checks under the lock that the rules still exist and the text is unchanged (retrying on change). Tested: four hostile patterns on 5,000–50,000-character inputs finish in under 5 s in total. |
| MEDIUM | Long fuzzy patterns took 11 s per document. | At most 6 fuzzy words. `real_quick_ratio` and `quick_ratio` upper bounds run before `ratio()`, and matching runs outside the locks. Tested. |
| MEDIUM | Regex skipped full case folding (`Straße` did not match `strasse`). | `regex.FULLCASE` with `IGNORECASE`. Tested. |
| LOW | The duplicate check ignored the mode, and regexes were compared case-insensitively. | The check now includes the mode, and regex patterns are compared exactly. Same-target duplicates still hit the unique constraint (409). |
| LOW | Empty-matching regexes (`a*`) matched everything. | Refused at validation. Tested. |
| LOW | Fuzzy limits on short words. | Documented in the README (85% threshold, 6 words). |
| LOW | Partial scanning of long documents. | Documented in the README (regex 100k characters, fuzzy 20k words). |
| LOW | Mixed-version deploys. | `match` is passed as a keyword argument, and tasks queued without it default to phrase. |
| LOW | The UI kept the previous mode. | Opening a rule form resets the mode to "Exact phrase". |

**Similar documents** (`archive/similar.py`, `/api/documents/<id>/similar`, `SimilarPanel.tsx`) was reviewed by the primary agent only:
- Owner-scoped sample of 500 recent ready documents, excluding Trash and split sources.
- Words common to many documents are removed before Jaccard scoring.
- Exact copies (same SHA-256) and likely duplicates (≥ 0.85) are flagged.
- No model or external call.
- `test_similar.py` and the desktop/mobile `e2e/similar.spec.ts` pass.

Verification: `test_match_modes.py` (15) and the full API suite (152 passed, 6 zbar-only skips locally) pass. The `regex` wheel is installed in the Linux ARM image. The match-mode, auto-filing, archive, nested-tags, and similar journeys pass on desktop and mobile.
