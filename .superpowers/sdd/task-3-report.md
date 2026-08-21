# Task 3 Report: Propagate Season Through Yahoo, Parsers, and Sleeper

## Summary
- Added dynamic Yahoo NFL game discovery by `code == "nfl"` with opaque `game_key` selection and explicit failures for missing/malformed NFL metadata.
- Changed league discovery to use dynamic NFL game metadata, normalize league seasons to integers, and cache leagues by resolved season.
- Made Yahoo roster and free-agent parser static bye fallbacks require explicit resolved `season`, then migrated parser callsites via LSP reference coverage.
- Updated waiver/draft bye paths to pass resolved league season and use API-first/static-fallback behavior.
- Updated Sleeper current-season resolution to delegate through `resolve_fantasy_season()` using fetched `state/nfl` metadata.
- Removed active setup-time Yahoo `game_id=449` / `get_user_leagues_by_game_key("449")`; setup now uses `get_current_game_metadata()` and passes the returned opaque `game_key`.
- Constrained MCP to `mcp>=1.2.0,<2` in both dependency files and installed that constraint into the worktree `.venv`.

## RED Evidence
Command:
```bash
.venv/bin/python -m pytest tests/unit/test_league_discovery.py tests/unit/test_bye_weeks.py -q
```
Observed failures after the MCP prerequisite was installed:
- `discover_nfl_game` import missing.
- Old league discovery returned `{}` for nonzero-key NFL metadata.
- `parse_yahoo_free_agent_players(..., season=2026)` was not accepted.
- Main waiver/draft bye paths still produced old implicit-season fallback values.

## GREEN Evidence
Command:
```bash
.venv/bin/python -m pytest tests/unit/test_league_discovery.py tests/unit/test_bye_weeks.py tests/integration/test_mcp_tools.py -q
```
Result:
```text
..........................................                               [100%]
```
Focused Task 3 suites passed: 42 tests passed.

## Focused Coverage Added/Updated
- `discover_nfl_game()` selects NFL by `code` from nonzero Yahoo game keys, normalizes season to `int`, and fails on missing/malformed NFL metadata.
- `discover_leagues()` handles nonzero-key NFL game payloads, returns integer league season, and keeps season-keyed caches separate.
- Yahoo parser bye tests pass explicit season and assert valid Yahoo bye values win while invalid/missing values fall back to official 2026 data.
- Sleeper `get_current_season()` test verifies resolver delegation with fetched state metadata.
- Setup auth test verifies current NFL metadata is used, no `game_id` is passed, historical `get_user_games()` is not used, and the opaque `game_key` is required/passed to league lookup.
- Integration suite imports the canonical server module.

## Self-Review
- LSP references were used before exported parser/discovery API changes; affected parser callsites were migrated.
- `grep` checks found no active `2025`, `449`, `game_id=`, `get_user_leagues_by_game_key("449")`, or `get_user_games()` defaults in canonical Yahoo/Sleeper/setup paths.
- Simplified pre-parsed roster paths do not invent a season; raw Yahoo parser fallback requires and receives explicit resolved season.
- No live Yahoo access was used.

## Dependency Prerequisite
- `pyproject.toml`: `mcp>=1.2.0,<2`
- `requirements.txt`: `mcp>=1.2.0,<2`
- Worktree `.venv`: installed `mcp-1.29.0` after bootstrapping pip with `ensurepip` because pip was initially absent.

## Commits
- Pending at report-write time; commit created immediately after staging this report.

## Concerns
- None known within Task 3 focused scope.

## Review Fix

### RED Evidence
- Command: `.venv/bin/python -m pytest tests/unit/test_league_discovery.py tests/unit/test_bye_weeks.py -q`
  - Expected failures observed before implementation:
    - `discover_nfl_game` still called `yahoo_api_call` without `use_cache=False`.
    - repeated `discover_nfl_game()` returned stale cached `933`/`2026` metadata instead of changed `944`/`2027` metadata.
    - Yahoo league list single-key metadata kept only `league_key`, dropping `league_id`, `name`, `season`, `num_teams`, and `status`.
    - waiver/draft malformed season errors were swallowed and returned empty lists.
- Command: `.venv/bin/python -m pytest tests/integration/test_mcp_tools.py::TestPlayerToolsIntegration::test_waiver_wire_yahoo_failure_surfaces_error -q`
  - Expected failure observed before implementation: handler returned `status == "success"` for a Yahoo API exception because the lower-level broad catch converted it to empty players.

### GREEN Evidence
- Command: `.venv/bin/python -m pytest tests/unit/test_league_discovery.py tests/unit/test_bye_weeks.py tests/integration/test_mcp_tools.py -q`
- Result: `47 passed`.

### Changes
- `discover_nfl_game()` and current dynamic league discovery now call Yahoo with `use_cache=False` so current-season metadata cannot be retained by endpoint cache across seasons.
- `_iter_yahoo_league_dicts()` merges every dict in Yahoo's list-form league metadata before league records are built.
- Discovered league records preserve optional `status` and `count` fields when Yahoo supplies them.
- `get_waiver_wire_players()` and `get_draft_rankings()` no longer use broad empty-list catches; season resolution, Yahoo API, and parser failures propagate.
- `handle_ff_get_waiver_wire()` now surfaces lower-level waiver fetch failures as `status: "error"` instead of false-success empty players.

### Commit
- Base Task 3 commit from original implementation: `e24fdbf`.
- Review fix commit: `TO_BE_FILLED_AFTER_COMMIT`.

### Self-Review
- Focus stayed on the three Important findings plus the required handler regression.
- No OAuth credential custody, Reddit behavior, docs, formatters, linters, builds, or project-wide tests were touched.
- Broad catches remain only in unrelated existing paths and enhancement/per-record fallback areas; the waiver/draft Yahoo/runtime path now propagates.

### Concerns
- Focused suite count is now 47 because five review regressions were added on top of the previous 42 focused tests.
