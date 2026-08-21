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
- Review fix: tightened 401 handling so only Yahoo `token_rejected` responses trigger the one refresh/one retry path; unknown non-provisioning 401s now fail safely without refreshing.

## TDD / Verification
- RED: `.venv/bin/python -m pytest tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py -q` failed at collection because `src.api.yahoo_credentials` and `YahooProvisioningError` did not exist.
- GREEN: `.venv/bin/python -m pytest tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py -q` -> `25 passed`.
- Utility syntax check: `.venv/bin/python -m py_compile src/api/yahoo_credentials.py src/api/yahoo_client.py src/api/__init__.py config/settings.py fantasy_football_multi_league.py utils/setup_yahoo_auth.py utils/reauth_yahoo.py utils/refresh_yahoo_token.py utils/verify_setup.py src/agents/yahoo_auth.py tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py tests/unit/test_league_discovery.py tests/unit/test_yahoo_review_fixes.py` -> exit 0.

## Self-review notes
- Confirmed LSP references for exported `yahoo_api_call`, `refresh_yahoo_token`, and the re-exported refresh symbol before changing the API surface.
- Confirmed `yfpy` setup no longer writes tokens directly to checkout `.env`; the utility persists token data only through the seam.
- Focused tests cover checkout-scoped env loading, canonical credential requirements, atomic token persistence, secret-safe failures, provisioning classification, refresh rejection, loop prevention, and unchanged operational-error status semantics.
- Review-fix test coverage now includes unknown 401 no-refresh behavior while preserving `token_rejected` refresh/retry.

## Concerns
- `yfpy` constructor keyword names remain `YAHOO_CLIENT_ID` / `YAHOO_CLIENT_SECRET` because those are third-party API parameter names, not environment-variable conventions.

## Review Fix
- Resolved `TASK4-CREDENTIAL-SEAM-BYPASS`: `src/agents/yahoo_auth.py` now loads and persists tokens only through the checkout `.env` seam, no longer accepts/uses an alternate token-store path, no longer creates `yahoo_tokens.json`, does not print token prefixes, performs one refresh attempt, and redacts upstream auth errors from logs/exceptions.
- Resolved `TASK4-CANONICAL-NAME-CUTOVER`: `Settings` uses Pydantic 2 `validation_alias` for canonical Yahoo names, `render.yaml` provisions `YAHOO_CONSUMER_KEY` / `YAHOO_CONSUMER_SECRET`, and `utils/verify_setup.py` reads canonical names without printing token bytes.
- Resolved `TASK4-PERSISTENCE-INTEGRITY`: `persist_yahoo_tokens` now holds a `filelock` lock across read/transform/fsync/replace, writes temporary files as `0600` before replacement, preserves non-newline-terminated files, atomically updates token fields plus optional GUID together, cleans temporary files on replacement failure, and leaves one complete Yahoo record under concurrent writers.
- Resolved `TASK4-401-REFRESH-CLASSIFICATION`: Yahoo API refresh is limited to explicit `oauth_problem="token_rejected"`; arbitrary 401 responses return a redacted API error without refreshing.
- Resolved `TASK4-UTILITY-PROVISIONING-RESULT`: setup and reauth reuse the shared provisioning classifier/message, fail instead of reporting success when Fantasy API provisioning is absent, and do not persist tokens after provisioning failure.
- Resolved `TASK4-FOCUSED-TEST-GAPS`: added focused regressions in `tests/unit/test_yahoo_review_fixes.py` plus the arbitrary-401 case in `tests/unit/test_api_client.py` and updated the setup import/opaque-game-key utility test.
- Resolved `TASK4-DEAD-COMPATIBILITY-SHIMS`: removed the dead `update_env_file` and `update_claude_config` refresh utility APIs rather than retaining no-op compatibility surfaces.

### Review-fix TDD / Verification
- RED: `.venv/bin/python -m pytest tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py tests/unit/test_yahoo_review_fixes.py -q` failed with 11 review-regression failures after adding the focused regressions; a later stricter arbitrary-401 parameter confirmed refresh is not triggered by a non-`oauth_problem` `token_rejected` substring.
- GREEN: `.venv/bin/python -m pytest tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py tests/unit/test_yahoo_review_fixes.py tests/unit/test_league_discovery.py -q` -> `45 passed` (the earlier combined run before the stricter extra parameter was `44 passed`).
- Compile check: `.venv/bin/python -m py_compile src/api/yahoo_credentials.py src/api/yahoo_client.py src/api/__init__.py config/settings.py src/agents/yahoo_auth.py utils/setup_yahoo_auth.py utils/reauth_yahoo.py utils/refresh_yahoo_token.py utils/verify_setup.py tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py tests/unit/test_yahoo_review_fixes.py tests/unit/test_league_discovery.py` -> exit 0.

### Review-fix self-review
- Grep review confirmed active config/deployment/verify surfaces use canonical Yahoo environment names; remaining `YAHOO_CLIENT_ID` / `YAHOO_CLIENT_SECRET` references are third-party `yfpy` constructor keyword names or negative legacy-name tests.
- Grep review confirmed no `yahoo_tokens.json`, token-prefix stdout, auth-URL stdout/logging, or refresh utility MCP-config shim remains in production code.
