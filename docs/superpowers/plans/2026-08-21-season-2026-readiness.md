# Fantasy Football MCP 2026 Season Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a secret-free 2026 Yahoo Fantasy Football MCP release that supports draft and weekly workflows through one stdio server in Pi/OMP and Claude Desktop.

**Architecture:** Start an isolated `season-2026` worktree from `upstream/main`, then cherry-pick the approved design and this plan. Add a pure season resolver and season-keyed bye data, consolidate Yahoo authorization behavior in `src/api`, and keep the canonical `fantasy_football_multi_league.py` tool schemas stable while disabling Reddit by default.

**Tech Stack:** Python 3.13 locally with Python >=3.9 compatibility, MCP Python SDK, aiohttp, python-dotenv, pytest/pytest-asyncio, Ruff, Black, Mypy, Yahoo Fantasy Sports OAuth 2.0, Sleeper API.

## Global Constraints

- Preserve the dirty `updates-and-fixes` checkout unchanged.
- Base `season-2026` on active upstream commit `9cea554` or a verified descendant.
- Canonical release entry point: `fantasy_football_multi_league.py` over stdio.
- Pi/OMP and Claude Desktop use one interpreter, script, working directory, and `.env`; client configs contain no secrets.
- `FANTASY_SEASON` precedence: explicit validated value, normalized Yahoo metadata, then release default `2026`.
- Official 2026 bye source: NFL schedule release dated 2026-05-15, https://www.nfl.com/news/2026-nfl-schedule-release-every-team-bye-week.
- Canonical Yahoo app fields: `YAHOO_CONSUMER_KEY` and `YAHOO_CONSUMER_SECRET`.
- Reddit sentiment is disabled by default and unsupported for this release.
- Never print, log, commit, or fixture consumer secrets, tokens, authorization codes, GUIDs, or personal league data.
- HTTP/FastMCP remains importable but is not a release gate.

---

### Task 1: Isolated Upstream Base and Secret Hygiene

**Files:**
- Delete: `.yahoo_token.json`
- Modify: `.gitignore`
- Modify: `pyproject.toml`
- Add by cherry-pick: `docs/superpowers/specs/2026-08-21-season-2026-readiness-design.md`
- Add by cherry-pick: `docs/superpowers/plans/2026-08-21-season-2026-readiness.md`

**Interfaces:**
- Consumes: git refs `upstream/main`, current spec commit, current plan commit.
- Produces: clean `season-2026` worktree; tracked test files; packaged `src/data/*.json`; no tracked token files.

- [ ] **Step 1: Create the isolated worktree**

Use `superpowers:using-git-worktrees`. Add persistent HTTPS upstream remote if absent, fetch it, create `.worktrees/season-2026` at `upstream/main`, then cherry-pick the design and plan commits. Do not stash, reset, clean, or checkout the dirty parent worktree.

- [ ] **Step 2: Remove the leaked token and fix ignore rules**

Delete `.yahoo_token.json`. Add these exact auth patterns:

```gitignore
.yahoo_token.json
yahoo_token.json
*.token.json
.tokens/
```

Remove the `.gitignore` rules that exclude `tests/`, `test_*.py`, and `*_test.py`; tests are release artifacts. Keep `.env*` ignored while preserving already tracked `.env.example`.

- [ ] **Step 3: Package season data**

Change package data to include nested JSON:

```toml
[tool.setuptools.package-data]
src = ["data/*.json", "*.json", "*.yaml", "*.yml"]
```

- [ ] **Step 4: Verify repository hygiene**

Run:

```bash
git ls-files '.env' '.yahoo_token.json' 'yahoo_token.json' '*.token.json'
git check-ignore -v .yahoo_token.json .env
```

Expected: first command prints nothing; second reports both files ignored.

- [ ] **Step 5: Commit**

```bash
git add .gitignore pyproject.toml docs/superpowers

git rm .yahoo_token.json

git commit -m "security: remove tracked Yahoo token material"
```

### Task 2: Season Resolver and Official 2026 Bye Data

**Files:**
- Create: `src/utils/season.py`
- Create: `src/data/bye_weeks_2026.json`
- Modify: `src/utils/bye_weeks.py`
- Create: `tests/unit/test_season.py`
- Modify: `tests/unit/test_bye_weeks_utility.py`

**Interfaces:**
- Consumes: optional `FANTASY_SEASON`; optional Yahoo game metadata containing `season`.
- Produces: `DEFAULT_FANTASY_SEASON: int`; `resolve_fantasy_season(yahoo_game_metadata: Optional[Mapping[str, Any]] = None) -> int`; season-keyed bye helpers.

- [ ] **Step 1: Write failing resolver tests**

Cover explicit-env precedence, Yahoo integer/string normalization, default 2026, and invalid explicit values:

```python
@pytest.mark.parametrize("value", ["", "twenty-six", "26", "20260", "1999"])
def test_invalid_explicit_season_fails(monkeypatch, value):
    monkeypatch.setenv("FANTASY_SEASON", value)
    with pytest.raises(ValueError, match="FANTASY_SEASON"):
        resolve_fantasy_season({"season": "2026"})


def test_explicit_season_precedes_yahoo(monkeypatch):
    monkeypatch.setenv("FANTASY_SEASON", "2026")
    assert resolve_fantasy_season({"season": "2025"}) == 2026
```

Treat an unset variable differently from a present empty variable: empty is malformed and fails closed.

- [ ] **Step 2: Run resolver tests to verify failure**

Run: `python -m pytest tests/unit/test_season.py -q`

Expected: collection/import failure because `src.utils.season` does not exist.

- [ ] **Step 3: Implement the pure resolver**

```python
DEFAULT_FANTASY_SEASON = 2026
MIN_SUPPORTED_SEASON = 2020
MAX_SUPPORTED_SEASON = 2100


def _normalize_season(value: object, *, source: str) -> int:
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError(f"{source} must be a four-digit season")
    season = int(str(value))
    if len(str(value)) != 4 or not MIN_SUPPORTED_SEASON <= season <= MAX_SUPPORTED_SEASON:
        raise ValueError(f"{source} must be a supported four-digit season")
    return season


def resolve_fantasy_season(
    yahoo_game_metadata: Optional[Mapping[str, Any]] = None,
) -> int:
    if "FANTASY_SEASON" in os.environ:
        return _normalize_season(os.environ["FANTASY_SEASON"], source="FANTASY_SEASON")
    if yahoo_game_metadata and yahoo_game_metadata.get("season") is not None:
        return _normalize_season(yahoo_game_metadata["season"], source="Yahoo season")
    return DEFAULT_FANTASY_SEASON
```

- [ ] **Step 4: Write failing bye-data tests**

Require exact 32-team keys, integer weeks 5-14, API-first behavior, season-keyed cache identity/isolation, explicit `FileNotFoundError` for missing data, and optional per-season cache clearing.

The 2026 map is:

```json
{"ARI":14,"ATL":11,"BAL":13,"BUF":7,"CAR":5,"CHI":10,"CIN":6,"CLE":11,"DAL":14,"DEN":10,"DET":6,"GB":11,"HOU":8,"IND":13,"JAC":7,"KC":5,"LAC":7,"LAR":11,"LV":13,"MIA":6,"MIN":6,"NE":11,"NO":8,"NYG":8,"NYJ":13,"PHI":10,"PIT":9,"SEA":11,"SF":8,"TB":10,"TEN":9,"WAS":7}
```

- [ ] **Step 5: Run bye tests to verify failure**

Run: `python -m pytest tests/unit/test_bye_weeks_utility.py -q`

Expected: failures because helpers do not accept `season` and 2026 data is absent.

- [ ] **Step 6: Implement season-keyed bye loading**

Use these contracts:

```python
_BYE_WEEK_CACHE: dict[int, dict[str, int]] = {}

def load_static_bye_weeks(season: int) -> dict[str, int]: ...

def get_bye_week_with_fallback(
    team_abbr: str,
    api_bye_week: Optional[int] = None,
    *,
    season: int,
) -> Optional[int]: ...

def build_team_bye_week_map(
    season: int,
    api_team_data: Optional[dict[str, int]] = None,
) -> dict[str, int]: ...

def clear_cache(season: Optional[int] = None) -> None: ...
```

Validate the loaded object before caching: exact canonical 32-team key set, non-bool integer values, weeks 1-18. Prefer valid API bye data; use static only when API data is absent or invalid. Do not return `{}` for a missing or malformed requested dataset.

- [ ] **Step 7: Run focused tests and commit**

```bash
python -m pytest tests/unit/test_season.py tests/unit/test_bye_weeks_utility.py -q
git add src/utils/season.py src/utils/bye_weeks.py src/data/bye_weeks_2026.json tests/unit/test_season.py tests/unit/test_bye_weeks_utility.py
git commit -m "feat: add season-aware 2026 bye data"
```

Expected: focused tests pass.

### Task 3: Propagate Season Through Yahoo, Parsers, and Sleeper

**Files:**
- Modify: `fantasy_football_multi_league.py`
- Modify: `src/parsers/yahoo_parsers.py`
- Modify: `sleeper_api.py`
- Modify: `lineup_optimizer.py`
- Modify: `utils/setup_yahoo_auth.py`
- Modify: `tests/conftest.py`
- Create: `tests/unit/test_league_discovery.py`
- Modify: `tests/unit/test_bye_weeks.py`
- Modify: `tests/integration/test_mcp_tools.py`

**Interfaces:**
- Consumes: Task 2 resolver and bye helper signatures.
- Produces: `discover_nfl_game() -> dict[str, Any]`; normalized integer league seasons; no active 2025/game-ID defaults.

- [ ] **Step 1: Write failing discovery and propagation tests**

Mock `yahoo_api_call` with Yahoo games stored under a nonzero numeric key and season string `"2026"`. Assert `discover_nfl_game()` selects game code `nfl`, returns `{"game_key": <dynamic key>, "season": 2026, "code": "nfl"}`, and `discover_leagues()` returns integer season 2026 without assuming index `0`.

Update parser/main bye tests to pass `season=2026`; assert valid Yahoo bye values win and missing/invalid values fall back to the official 2026 map.

- [ ] **Step 2: Run focused tests to verify failure**

Run:

```bash
python -m pytest tests/unit/test_league_discovery.py tests/unit/test_bye_weeks.py -q
```

Expected: missing discovery function and season-argument failures.

- [ ] **Step 3: Implement normalized game discovery**

Call Yahoo through the symbolic NFL resource; never infer a numeric game key. Extract the game object by `code == "nfl"`, normalize its season through `resolve_fantasy_season`, and raise a descriptive runtime error when the response has no NFL game. Key league caches by resolved season.

Pass resolved season into both canonical bye callsites and into `parse_yahoo_free_agent_players(..., *, season: int)`. Do not silently swallow malformed NFL game metadata.

- [ ] **Step 4: Unify Sleeper season behavior**

Make root `SleeperAPI.get_current_season()` delegate to `resolve_fantasy_season()` using successfully fetched `state/nfl` season metadata. Preserve explicit season parameters on projections/stats. Remove 2025 labels from fallback projections unless the values are explicitly season-qualified; do not claim manually maintained defensive rankings are 2026 data.

- [ ] **Step 5: Remove hard-coded setup game ID**

Replace `game_id=449` and `get_user_leagues_by_game_key("449")` with Yahoo game-code discovery. Update fixtures from season `"2025"` to parameterized/current `"2026"`; numeric game keys remain opaque fixture strings.

- [ ] **Step 6: Run focused tests and commit**

```bash
python -m pytest tests/unit/test_league_discovery.py tests/unit/test_bye_weeks.py tests/integration/test_mcp_tools.py -q
git add fantasy_football_multi_league.py src/parsers/yahoo_parsers.py sleeper_api.py lineup_optimizer.py utils/setup_yahoo_auth.py tests
git commit -m "feat: resolve the active Yahoo fantasy season"
```

Expected: focused suites pass.

### Task 4: Yahoo Credential Custody and Authorization Errors

**Files:**
- Create: `src/api/yahoo_credentials.py`
- Modify: `src/api/yahoo_client.py`
- Modify: `src/api/__init__.py`
- Modify: `fantasy_football_multi_league.py`
- Modify: `config/settings.py`
- Modify: `utils/setup_yahoo_auth.py`
- Modify: `utils/reauth_yahoo.py`
- Modify: `utils/refresh_yahoo_token.py`
- Modify: `.env.example`
- Create: `tests/unit/test_yahoo_credentials.py`
- Modify: `tests/unit/test_api_client.py`

**Interfaces:**
- Consumes: repository-root `.env`, canonical consumer key/secret, Yahoo token responses.
- Produces: `load_project_environment() -> Path`; `persist_yahoo_tokens(access_token: str, refresh_token: str, expires_in: int, *, env_path: Path = PROJECT_ENV_PATH) -> None`; `YahooProvisioningError`.

- [ ] **Step 1: Write failing credential tests**

Assert that environment loading is anchored to the checkout rather than the process working directory; canonical consumer fields are required; token persistence replaces only Yahoo token fields, preserves unrelated lines, writes mode `0o600`, and uses `os.replace`; captured logs/exceptions never contain sentinel token values.

- [ ] **Step 2: Write failing API error tests**

Using mocked aiohttp responses, cover:

```python
@pytest.mark.parametrize("status, body", [
    (401, 'oauth_problem="additional_authorization_required"'),
    (403, '{"error":{"description":"This application is not authorized to perform this action."}}'),
])
async def test_provisioning_failure_never_refreshes(status, body): ...
```

Also cover `401 token_rejected` refreshes once and retries once; failed refresh requires reauthorization; second 401 does not loop; 429/5xx stay operational errors.

- [ ] **Step 3: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py -q`

Expected: missing credential module and incomplete 403 classification failures.

- [ ] **Step 4: Implement one credential seam**

Load `.env` from `Path(__file__).resolve().parents[2] / ".env"` before API configuration. Replace `YAHOO_CLIENT_ID`/`YAHOO_CLIENT_SECRET` reads and documentation with `YAHOO_CONSUMER_KEY`/`YAHOO_CONSUMER_SECRET`. Atomically persist successful access/refresh tokens and `YAHOO_TOKEN_TIME`; never embed tokens in MCP client configs.

- [ ] **Step 5: Complete provisioning classification**

Retain upstream's `additional_authorization_required` handling and add the observed 403 authorization description. Raise `YahooProvisioningError` with the access-form URL `https://sports.yahoo.com/developer/access/`; never attempt refresh for provisioning failures. Keep exactly one refresh/retry for rejected access tokens.

- [ ] **Step 6: Run focused tests and commit**

```bash
python -m pytest tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py -q
git add src/api config/settings.py fantasy_football_multi_league.py utils .env.example tests/unit/test_yahoo_credentials.py tests/unit/test_api_client.py
git commit -m "fix: unify Yahoo authorization and token custody"
```

Expected: focused auth tests pass without secret output.

### Task 5: Default-Off Reddit and Stable MCP Contracts

**Files:**
- Modify: `fantasy_football_multi_league.py`
- Modify: `src/handlers/__init__.py`
- Modify: `src/handlers/analytics_handlers.py`
- Modify: `fastmcp_server.py`
- Create: `tests/unit/test_mcp_registration.py`
- Create: `tests/unit/test_tool_contracts.py`

**Interfaces:**
- Consumes: `ENABLE_REDDIT_SENTIMENT` boolean environment setting.
- Produces: exact default 17-tool Yahoo/system inventory; optional eighteenth Reddit tool; lazy Reddit imports.

- [ ] **Step 1: Write failing registration tests**

Assert the exact default set:

```python
EXPECTED_DEFAULT_TOOLS = {
    "ff_get_leagues", "ff_get_league_info", "ff_get_standings", "ff_get_teams",
    "ff_get_roster", "ff_get_matchup", "ff_get_players", "ff_compare_teams",
    "ff_build_lineup", "ff_refresh_token", "ff_get_draft_results",
    "ff_get_waiver_wire", "ff_get_api_status", "ff_clear_cache",
    "ff_get_draft_rankings", "ff_get_draft_recommendation", "ff_analyze_draft_state",
}
```

With the flag absent, Reddit is neither advertised nor dispatchable and importing the server does not import `praw`, `textblob`, or `src.services.reddit_service`. With flag value `1`, only `ff_analyze_reddit_sentiment` is added. Snapshot existing Yahoo input schemas before editing and assert they remain equal.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/unit/test_mcp_registration.py tests/unit/test_tool_contracts.py -q`

Expected: Reddit is currently registered unconditionally.

- [ ] **Step 3: Implement conditional lazy registration**

Evaluate `ENABLE_REDDIT_SENTIMENT` after `.env` loading with accepted true values `{1,true,yes,on}`. Build `TOOL_HANDLERS` from the 17 default handlers and add the Reddit handler only when enabled. Move Reddit service imports inside `handle_ff_analyze_reddit_sentiment`. Apply the same default-off condition to FastMCP registration without making HTTP a release gate.

- [ ] **Step 4: Test handler behavior and commit**

Add deterministic handler passthrough/result-shape tests for draft recommendation, draft state, draft results, roster, matchup, lineup, and waiver. These tests must describe current behavior accurately; they must not call simplified draft advice “AI-powered” or raw matchup JSON “analysis.”

```bash
python -m pytest tests/unit/test_mcp_registration.py tests/unit/test_tool_contracts.py -q
git add fantasy_football_multi_league.py fastmcp_server.py src/handlers tests/unit/test_mcp_registration.py tests/unit/test_tool_contracts.py
git commit -m "fix: disable unsupported Reddit tools by default"
```

Expected: contract tests pass with default 17 tools.

### Task 6: Public Docs, Client Configuration, and End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `INSTALLATION.md`
- Create locally only: `.build/season-2026-live-smoke.json`
- Modify locally only: `/Users/syoung/Library/Application Support/Claude/claude_desktop_config.json`
- Modify locally only: the active Pi/OMP MCP registration source identified during execution.

**Interfaces:**
- Consumes: completed server, local `.env`, Yahoo Developer access status.
- Produces: secret-free client configs, automated evidence, sanitized live-smoke evidence, pull-request-ready branch.

- [ ] **Step 1: Update public documentation**

Document Python setup, canonical consumer variables, `FANTASY_SEASON=2026`, Yahoo's manual Fantasy API access application, existing-app reauthorization, provisioning-versus-token errors, default-disabled Reddit, and the canonical stdio command. Remove claims that draft recommendation is AI-powered/live-draft-aware, matchup output is analyzed, or draft results contain a pick board when the implementation does not provide those contracts. Include Yahoo attribution required by the current developer portal.

- [ ] **Step 2: Install and run automated gates**

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest tests/unit tests/integration -q
.venv/bin/python -m ruff check .
.venv/bin/python -m black --check .
.venv/bin/python -m mypy src fantasy_football_multi_league.py fastmcp_server.py
```

Fix only failures caused by this change. Existing unrelated gate failures must be recorded with exact evidence and separated from changed-path verification.

- [ ] **Step 3: Smoke the actual stdio server**

Launch the server from `/tmp` using the worktree interpreter/script. Send MCP `initialize` and `tools/list`; assert 17 default tools and no Reddit tool. Repeat with `ENABLE_REDDIT_SENTIMENT=1` only if Reddit dependencies and credentials are intentionally supplied; Reddit success is not a release gate.

- [ ] **Step 4: Configure both clients without secrets**

For Claude Desktop and Pi/OMP, configure only:

```json
{
  "command": "/absolute/path/to/.worktrees/season-2026/.venv/bin/python",
  "args": ["/absolute/path/to/.worktrees/season-2026/fantasy_football_multi_league.py"],
  "cwd": "/absolute/path/to/.worktrees/season-2026"
}
```

Preserve all unrelated client entries. Validate JSON/YAML syntax before restart. Never copy `.env` values into client config.

- [ ] **Step 5: Complete Yahoo access and live acceptance**

The existing refresh grant is valid, but every Fantasy endpoint currently returns 403 `This application is not authorized to perform this action.` Sign in at `https://developer.yahoo.com/apps/`, confirm the existing Client ID, and submit/verify Fantasy API access at `https://sports.yahoo.com/developer/access/`. This human review is external and cannot be bypassed in code.

After authorization, run the actual MCP tools for leagues, league info, standings, roster, matchup, team comparison, lineup, free agents, waivers, draft rankings, draft recommendation, draft state, draft results when available, API status, and refresh. Record only tool name, success/error state, sanitized status, and timestamp in `.build/season-2026-live-smoke.json`.

- [ ] **Step 6: Restart and persistence check**

Restart both stdio clients and repeat league discovery. Expected: no interactive grant and at least one 2026 NFL league. Preseason/unavailable operations must return accurate state errors, not empty fabricated success.

- [ ] **Step 7: Review, commit, and prepare the fork branch**

```bash
git add README.md INSTALLATION.md
git commit -m "docs: publish 2026 Yahoo season setup"
```

Run a final reviewer and security review, rerun changed-path tests plus the stdio smoke, confirm no secret-bearing files are tracked, then push `season-2026` to `x90skysn3k/fantasy-football-mcp-public` over authenticated HTTPS and prepare a pull request against the fork's `main`.
