# Italian API messages and Telegram reply language review

An independent read-only review of the slice committed as `1e930e5` while the review ran ("Translate every API message into Italian and let Telegram bots reply in Italian"). It covered readable field labels (`archive/field_labels.py`), the Italian catalog (`messages_it.py`) and scanner (`message_catalog.py`), leading-label translation in `api_language.py`, and the per-source Telegram reply language (model, migration 0052, API, `SourcesPanel`, `telegram.py`).

Verdict: **APPROVE WITH CHANGES**. No high findings, 2 medium, 5 low. The template engine is safe for user data: only `p0` of `{0} …` templates and `Enter the {0}` passes through `VALUES`, and every other placeholder is copied unchanged (checked with `ASN 7 is already used by “Note”`). There are no KeyError paths: `FILTER_ERRORS`, `OWN_ALREADY_ERRORS`, and `SHARED_EDIT_ERRORS` cover every key their call sites can reach, and `_say` falls back to `en`. The API v1 contract only gains `reply_language`; nothing was removed and no type changed. The migration default `en` keeps existing bots unchanged.

## Commands

| Command | Result |
| --- | --- |
| `RIPIANO_DEBUG=1 .venv/bin/pytest -q archive/test_api_language.py archive/test_telegram.py archive/test_api_contract.py archive/test_object_access.py` | 18 passed |
| `npx tsc --noEmit -p .` (apps/web) | clean |
| Script: `extract()` compared with `EXACT`/`TEMPLATES` | 476 exact and 59 templates extracted; none missing today |
| Script: `to_italian` on 23 representative messages | See findings |

## Findings

| Severity | Finding | Location |
| --- | --- | --- |
| MEDIUM | The README and parity row say `test_api_language.py` "fails when a new message has no Italian version". It does not. The test asserts `set(EXACT) <= exact` and `set(TEMPLATES) <= templates`, so the catalog must be a subset of the source, not the reverse. Full coverage holds today only by inspection. Add `exact <= set(EXACT)` and `templates <= set(TEMPLATES)`, with any allow-list made explicit. | `archive/test_api_language.py:16-17`, `README.md`, `docs/FEATURE_PARITY.md` |
| MEDIUM | Raw field and model names still reach users, despite "never raw request keys". `views.py:974` and `metadata_views.py:205` build `f"{field.replace('_',' ').title()} not found"`, which gives "Correspondent not found" or "Document Type not found". In Italian these become "Correspondent: elemento non trovato" and "Document Type: elemento non trovato", because `VALUES` has "Document type", not "Document Type", and has no "Correspondent". The same pattern is at `mcp_server.py:252`. `source_views.py` `f"{key.capitalize()} must be true or false"` gives "Il campo enabled deve essere true o false", which leaks the key and leaves `true`/`false` untranslated. | `archive/views.py:974`, `archive/metadata_views.py:205`, `archive/mcp_server.py:252`, `archive/source_views.py` (`_apply` bool loop), `archive/messages_it.py:267` |
| LOW | The new `{0} …` templates catch any message with the same ending, such as "X not found", "X is required", or "X could not be reached". An unknown `X` therefore yields a mixed sentence ("Sender: elemento non trovato", "Telegram source"-style labels) rather than staying fully English. Today every such source has an `EXACT` entry or a translated label, so this is a future-proofing note. `_value` would also translate user data that exactly equals a label, such as a host named "Server", but no current `{0}`-led template carries user data in `p0`. | `archive/api_language.py:26-27` |
| LOW | `test_field_names_in_messages_are_readable_and_translated` wraps its main asserts in `if … in TEMPLATES:`, so it passes vacuously if those templates are renamed. Assert unconditionally. | `archive/test_api_language.py:444-448` |
| LOW | No test covers the new `OWN_ALREADY_ERRORS`/`SHARED_EDIT_ERRORS` texts or their Italian. The shared-edit 403 no longer names the rejected fields, which is acceptable because the contract does not cover error text. | `archive/object_access_views.py:19-27` |
| LOW | Italian sample (about 45 entries read) is accurate and idiomatic overall. Nits: "Media contains a symlink" becomes "I file contengono…", which is fine. The English source "Another admin changes their own password" is unclear, although the Italian "Solo l'amministratore stesso può cambiare la propria password" reads well. "{0} rifiutato dal bucket" assumes a masculine HTTP method, which is fine. | `archive/messages_it.py`, `archive/people_views.py:153` |
| LOW | `reply_language` is validated and stored for every source kind, not only Telegram. This is harmless, but non-Telegram sources store a meaningless value. The `SourcesPanel` default follows the UI language only for new sources, as intended. | `archive/source_views.py` `_apply` |

## Telegram

`REASONS["it"]` covers all 7 `storage_sources.skip_reason` return values. The `too_large` and `unsupported` paths use the source language, and the new test checks the waiting, `/start`, and skip replies in Italian, plus GET, a 400 for `de`, and a PATCH round trip.
