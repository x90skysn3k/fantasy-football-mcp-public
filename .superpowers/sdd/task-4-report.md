# Task 4 Report: Yahoo Credential Custody and Authorization Errors

## Summary
- Added a single checkout-anchored Yahoo credential seam in `src/api/yahoo_credentials.py`.
- Switched active configuration and examples to canonical `YAHOO_CONSUMER_KEY` / `YAHOO_CONSUMER_SECRET`.
- Persisted successful refresh/setup/reauth token updates atomically through `persist_yahoo_tokens`, with mode `0600` and preservation of unrelated `.env` lines.
- Classified Yahoo Fantasy API provisioning failures as `YahooProvisioningError` for both upstream `401 additional_authorization_required` and the observed `403 This application is not authorized to perform this action.` response.
- Preserved one-refresh/one-retry behavior for rejected access tokens and prevented second-401 refresh loops.
- Kept 429/5xx as operational Yahoo API errors while omitting response bodies from exception messages.
- Removed token-copy behavior for Claude/Cursor/Antigravity MCP configs from setup, reauth, and refresh utilities.
- Made auth/refresh utility output avoid printing token values or token-bearing exception/response bodies.

## TDD / Verification
- RED: `.venv/bin/python -m pytest tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py -q` failed at collection because `src.api.yahoo_credentials` and `YahooProvisioningError` did not exist.
- GREEN: `.venv/bin/python -m pytest tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py -q` -> `23 passed`.
- Utility syntax check: `.venv/bin/python -m py_compile src/api/yahoo_credentials.py src/api/yahoo_client.py src/api/__init__.py config/settings.py fantasy_football_multi_league.py utils/setup_yahoo_auth.py utils/reauth_yahoo.py utils/refresh_yahoo_token.py tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py` -> exit 0.

## Self-review notes
- Confirmed LSP references for exported `yahoo_api_call`, `refresh_yahoo_token`, and the re-exported refresh symbol before changing the API surface.
- Confirmed `yfpy` setup no longer writes tokens directly to checkout `.env`; the utility persists token data only through the seam.
- Focused tests cover checkout-scoped env loading, canonical credential requirements, atomic token persistence, secret-safe failures, provisioning classification, refresh rejection, loop prevention, and unchanged operational-error status semantics.

## Concerns
- `yfpy` constructor keyword names remain `YAHOO_CLIENT_ID` / `YAHOO_CLIENT_SECRET` because those are third-party API parameter names, not environment-variable conventions.
