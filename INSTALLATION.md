# Fantasy Football MCP Server Installation

This guide installs the public Yahoo Fantasy Football MCP stdio server for Claude Desktop or Pi/OMP without putting secrets in client configuration.

Data provided by Yahoo Fantasy Sports. Use requires a Yahoo account, a Yahoo Developer app, and Yahoo Fantasy Sports API access approved by Yahoo.

## Prerequisites

- Python >=3.9
- Git
- A Yahoo Fantasy Sports account with 2026 fantasy football league access
- A Yahoo Developer app from https://developer.yahoo.com/apps/
- Manual Yahoo Fantasy Sports API approval from https://sports.yahoo.com/developer/access/
- Claude Desktop or Pi/OMP if you want MCP client integration

## 1. Clone and install

```bash
git clone https://github.com/derekrbreese/fantasy-football-mcp-public.git
cd fantasy-football-mcp-public
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

The editable install reads `pyproject.toml`, installs `mcp>=1.2.0,<2`, and exposes the current console entrypoint:

```bash
fantasy-football-mcp
```

For MCP client stdio use, configure the Python interpreter and `fantasy_football_multi_league.py` script as shown in section 5.

## 2. Create or reuse a Yahoo Developer app

1. Open https://developer.yahoo.com/apps/.
2. Create a new app or open the existing app you want this server to use.
3. For a new app, use application type `Web Application` and redirect URI `oob` for the manual OAuth flow.
4. Copy the app's Consumer Key and Consumer Secret.
5. Store them in the repository `.env` as `YAHOO_CONSUMER_KEY` and `YAHOO_CONSUMER_SECRET`.

Use `YAHOO_CONSUMER_KEY` and `YAHOO_CONSUMER_SECRET`. Those are the canonical public setup names the current code reads.

## 3. Apply for Yahoo Fantasy Sports API access

Creating a Yahoo Developer app gives you OAuth credentials, but it does not guarantee Fantasy Sports API entitlement.

1. Open https://sports.yahoo.com/developer/access/.
2. Submit or verify Fantasy Sports API access for the same app/consumer key from section 2.
3. Wait for Yahoo's manual review. There is no code path in this project that can bypass Yahoo's approval.
4. If you already had an app, keep using the existing app identity when requesting access so approval attaches to the credentials in `.env`.
5. After approval, run setup or reauthorization to create fresh tokens for the approved app.

### Provisioning errors are not token errors

These responses mean the app is authenticated but not provisioned for Fantasy Sports API access:

- HTTP 401 or 403 from Fantasy Sports endpoints after OAuth succeeds
- `oauth_problem="additional_authorization_required"`
- `This application is not authorized to perform this action.`

Refreshing or reauthenticating tokens will not fix those errors until Yahoo approves Fantasy Sports API access. Apply at https://sports.yahoo.com/developer/access/ with the existing app/consumer key.

Use token refresh or reauthorization only for expired, revoked, missing, or rejected OAuth tokens.

## 4. Configure `.env`

Create `.env` in the repository root:

```env
YAHOO_CONSUMER_KEY=your_consumer_key_here
YAHOO_CONSUMER_SECRET=your_consumer_secret_here
YAHOO_ACCESS_TOKEN=your_access_token_here
YAHOO_REFRESH_TOKEN=your_refresh_token_here
YAHOO_GUID=your_yahoo_guid_here
FANTASY_SEASON=2026

# Reddit is unsupported by default and the tool stays hidden unless enabled.
ENABLE_REDDIT_SENTIMENT=0
# REDDIT_CLIENT_ID=...
# REDDIT_CLIENT_SECRET=...
# REDDIT_USERNAME=...
```

Keep `.env` local. Never copy Yahoo tokens, consumer credentials, GUIDs, league keys, or personal paths into public documentation or MCP client config.

### First OAuth setup

```bash
. .venv/bin/activate
python utils/setup_yahoo_auth.py
```

The setup script opens Yahoo OAuth, exchanges the verifier, preflights Fantasy access, and saves Yahoo token metadata to the project `.env`.

### Existing-app reauthorization

Run this after Yahoo grants Fantasy access, after a refresh grant expires, or when you need to authorize the same app again:

```bash
. .venv/bin/activate
python utils/reauth_yahoo.py
```

### Token refresh

```bash
. .venv/bin/activate
python utils/refresh_yahoo_token.py
```

Restart Claude Desktop or Pi/OMP after token changes.

## 5. Configure MCP stdio clients without secrets

Use the same command/args/cwd configuration for Claude Desktop and Pi/OMP. The server loads secrets from `.env`; client config should contain no `env` block and no credential values.

### Claude Desktop

Add this server entry to `claude_desktop_config.json`, preserving any unrelated entries:

```json
{
  "mcpServers": {
    "yahoo-fantasy-football": {
      "command": "/absolute/path/to/fantasy-football-mcp-public/.venv/bin/python",
      "args": [
        "/absolute/path/to/fantasy-football-mcp-public/fantasy_football_multi_league.py"
      ],
      "cwd": "/absolute/path/to/fantasy-football-mcp-public"
    }
  }
}
```

### Pi/OMP

Register the same stdio command shape in the active Pi/OMP MCP registration source:

```json
{
  "command": "/absolute/path/to/fantasy-football-mcp-public/.venv/bin/python",
  "args": [
    "/absolute/path/to/fantasy-football-mcp-public/fantasy_football_multi_league.py"
  ],
  "cwd": "/absolute/path/to/fantasy-football-mcp-public"
}
```

Replace the paths with absolute paths on the target machine. Do not add credentials to either client config.

## 6. Expected default tools

With Reddit disabled, the stdio server advertises these default tools:

1. `ff_get_leagues` - list leagues for the authenticated Yahoo account.
2. `ff_get_league_info` - get league metadata and the user's team.
3. `ff_get_standings` - get league standings.
4. `ff_get_teams` - get teams in a league.
5. `ff_get_roster` - get roster data for the user's team or an optional team key.
6. `ff_get_matchup` - get raw Yahoo matchup data for a week; it does not add narrative analysis.
7. `ff_get_players` - browse available free agents.
8. `ff_compare_teams` - compare two team rosters.
9. `ff_build_lineup` - optimize a lineup using roster/player data and selected strategy.
10. `ff_refresh_token` - refresh Yahoo OAuth access tokens.
11. `ff_get_draft_results` - get team draft positions and grades when Yahoo supplies them; it returns team-level draft fields only.
12. `ff_get_waiver_wire` - get waiver-wire candidates with stats/projections and optional basic analysis.
13. `ff_get_api_status` - inspect cache and Yahoo API rate-limit state.
14. `ff_clear_cache` - clear cached API responses.
15. `ff_get_draft_rankings` - get Yahoo pre-draft rankings and ADP when available.
16. `ff_get_draft_recommendation` - get strategy-based recommendations from available player/draft data.
17. `ff_analyze_draft_state` - get roster needs and strategic draft-state fields.

`ff_analyze_reddit_sentiment` is optional and hidden by default. It appears in `tools/list` when `ENABLE_REDDIT_SENTIMENT` is truthy. Successful calls also require Reddit dependencies and credentials. Public 2026 setup does not require Reddit.

## 7. Troubleshooting

### OAuth succeeds but every Fantasy endpoint returns 401 or 403

If the response contains `additional_authorization_required` or `This application is not authorized to perform this action`, the app still needs Yahoo Fantasy Sports API access. Apply or verify access at https://sports.yahoo.com/developer/access/ for the existing app/consumer key.

### Missing credential variables

Use these exact names in `.env`:

```env
YAHOO_CONSUMER_KEY=...
YAHOO_CONSUMER_SECRET=...
```

Use the canonical consumer key/secret names above for public setup.

### Token expired or refresh failed

For a normal expired access token:

```bash
. .venv/bin/activate
python utils/refresh_yahoo_token.py
```

If the refresh grant is no longer valid:

```bash
. .venv/bin/activate
python utils/reauth_yahoo.py
```

### No 2026 leagues found

- Confirm `FANTASY_SEASON=2026` in `.env`.
- Confirm Yahoo approved the app for Fantasy Sports API access.
- Confirm `YAHOO_GUID` belongs to the account that owns the league.
- Confirm the Yahoo account has a 2026 Yahoo Fantasy Football league.

### Reddit tool missing

That is expected by default. Public setup leaves Reddit disabled. To experiment locally, install/configure the optional Reddit dependencies and credentials, then set `ENABLE_REDDIT_SENTIMENT=1` before starting the MCP server.

## Security notes

- Do not commit `.env`, tokens, consumer secrets, GUIDs, league keys, or personal client config.
- Keep MCP client config secret-free; use only command, args, and cwd.
- Yahoo refresh tokens can expire if unused or revoked; reauthorize the same app when needed.

## Attribution

Data provided by Yahoo Fantasy Sports. Yahoo and Yahoo Fantasy Sports are trademarks or registered trademarks of Yahoo. This project is not endorsed by or affiliated with Yahoo.