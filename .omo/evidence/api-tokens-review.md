# API tokens review

An independent read-only reviewer returned **REQUEST CHANGES**: no critical or high findings, 1 medium, and 5 low. It confirmed the following:
- `rip_` plus 256-bit tokens, with only a SHA-256 hash stored, unique and looked up by hash;
- inactive users, expired tokens, and revoked tokens get 401;
- `last_used_at` is throttled;
- the CSRF exemption applies only after a valid token on `/api/`;
- admin gating holds;
- no 2FA bypass, because minting a token needs a 2FA-passed session plus the password;
- mixing a cookie and a token is safe, because `Authorization` is not CORS-simple.

| Severity | Finding | Resolution |
| --- | --- | --- |
| MEDIUM | A token could mint MCP agent grants and public share links that outlive it. The test passed for the wrong reason (it used a non-superuser). | Tokens get 403 on `/api/agents`, `/api/share-bundles`, and non-GET `/api/documents/<id>/shares`, as well as on sign-in, setup, and account endpoints. The test now uses the superuser owner. |
| LOW | Tokens survived a password change. | A `pre_save` signal revokes all of a person's tokens when the password hash changes. Tested. |
| LOW | Any invalid token header got 401 even on public share downloads. | Anonymous share-link and bundle downloads ignore the header. Tested. |
| LOW | The token-creation password check was unthrottled. | It shares the sign-in throttle. |
| LOW | The OpenAPI outline was public. | `/api/schema.json` requires sign-in. Tested. |
| LOW | UI label duplication, and the token card cannot be dismissed. | The label reads "Your password (to create a token)". The card clears on revoke or navigation; accepted. |

Verification: `test_api_tokens.py` passes, and so does the full API suite (cache cleared per test). The desktop and mobile journey `e2e/api-tokens.spec.ts` creates a token in the UI, uses it from a cookieless client for documents and the schema, confirms 403 on token management, revokes it, and confirms 401.

The Overview dashboard (`stats_views.py`, `OverviewPanel.tsx`) was reviewed by the primary agent only. It covers owner-scoped totals that exclude Trash and split sources, untagged documents counted outside the joined aggregate, a zero-filled 12-month series, and an accessible table view. `test_overview.py` and `e2e/overview.spec.ts` pass.
