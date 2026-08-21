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
