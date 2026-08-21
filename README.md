# Fantasy Football MCP Server

A Model Context Protocol (MCP) stdio server for Yahoo Fantasy Football league discovery, rosters, standings, waiver/player data, lineup optimization, draft helpers, cache status, and Yahoo token refresh.

Data provided by Yahoo Fantasy Sports. Use of Yahoo Fantasy Sports API data is subject to Yahoo developer terms and Yahoo's Fantasy Sports API approval process.

## Current public setup

- Python >=3.9 is required.
- The project entrypoint from `pyproject.toml` is `fantasy-football-mcp`.
- The stdio server script is `fantasy_football_multi_league.py`.
- The project installs `mcp>=1.2.0,<2` for the stdio MCP server.
- The default fantasy football season is 2026. Set `FANTASY_SEASON=2026` explicitly in `.env` for reproducible public setup.
- Yahoo OAuth consumer credentials must use the canonical variable names `YAHOO_CONSUMER_KEY` and `YAHOO_CONSUMER_SECRET`.
- Reddit sentiment is disabled by default. The Reddit tool is advertised only when `ENABLE_REDDIT_SENTIMENT` is set to `1`, `true`, or `yes`; successful use also requires the optional Reddit dependencies and credentials.

## Installation

```bash
git clone https://github.com/derekrbreese/fantasy-football-mcp-public.git
cd fantasy-football-mcp-public
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

The editable install uses `pyproject.toml`, including the console script:

```bash
fantasy-football-mcp
```

For MCP clients, prefer the explicit stdio script configuration shown below so the server always starts with the repository as its working directory and loads the repository-root `.env`.

## Yahoo Fantasy API access

Yahoo app creation and Yahoo Fantasy Sports API access are separate steps.

1. Create or open your Yahoo Developer application at https://developer.yahoo.com/apps/.
2. Save the app's Consumer Key and Consumer Secret in the project `.env` as `YAHOO_CONSUMER_KEY` and `YAHOO_CONSUMER_SECRET`.
3. Apply for Yahoo Fantasy Sports API access at https://sports.yahoo.com/developer/access/ using the same existing app/consumer key.
4. Wait for Yahoo's manual review. This external approval cannot be bypassed in code, by refreshing tokens, or by recreating local config.
5. After approval, run the OAuth setup or reauthorization script to obtain tokens for the approved app.

Existing apps may need the same access request or reauthorization if Yahoo has not provisioned Fantasy Sports API access for that app. Keep the same app identity when applying so approval attaches to the credentials in `.env`.

### Provisioning errors vs token errors

Provisioning failures mean the app is authenticated but not approved for the Fantasy Sports API. Typical Yahoo responses include:

- `oauth_problem="additional_authorization_required"`
- `This application is not authorized to perform this action.`
- HTTP 401 or 403 from Fantasy Sports endpoints after OAuth succeeds

Refreshing tokens does not fix provisioning. Apply for access at https://sports.yahoo.com/developer/access/ and include the existing app/consumer key.

Token errors mean the app is provisioned but the access token is expired, revoked, missing, or rejected. Use `ff_refresh_token`, `utils/refresh_yahoo_token.py`, or `utils/reauth_yahoo.py` for token problems.

## Environment

Create `.env` in the repository root. Do not copy these secrets into MCP client configuration.

```env
YAHOO_CONSUMER_KEY=your_consumer_key_here
YAHOO_CONSUMER_SECRET=your_consumer_secret_here
YAHOO_ACCESS_TOKEN=your_access_token_here
YAHOO_REFRESH_TOKEN=your_refresh_token_here
YAHOO_GUID=your_yahoo_guid_here
FANTASY_SEASON=2026

# Optional; default is disabled and the tool is hidden unless explicitly enabled.
ENABLE_REDDIT_SENTIMENT=0
# REDDIT_CLIENT_ID=...
# REDDIT_CLIENT_SECRET=...
# REDDIT_USERNAME=...
```

`YAHOO_ACCESS_TOKEN`, `YAHOO_REFRESH_TOKEN`, and `YAHOO_GUID` are written by the auth scripts. Consumer key/secret come from the Yahoo Developer app.

## OAuth setup and reauthorization

First-time token setup:

```bash
. .venv/bin/activate
python utils/setup_yahoo_auth.py
```

Reauthorize an existing app after token expiry or after Yahoo grants Fantasy Sports access:

```bash
. .venv/bin/activate
python utils/reauth_yahoo.py
```

Refresh a valid grant:

```bash
. .venv/bin/activate
python utils/refresh_yahoo_token.py
```

The scripts save Yahoo-owned token fields only to the repository `.env`. Restart any MCP client after token changes.

## Canonical stdio client configuration

Use the same command/args/cwd shape for Claude Desktop and Pi/OMP registrations. Keep credentials in `.env`; do not put `env` or secret values in client config.

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

If your client stores only one server entry at a time, use the inner object exactly:

```json
{
  "command": "/absolute/path/to/fantasy-football-mcp-public/.venv/bin/python",
  "args": [
    "/absolute/path/to/fantasy-football-mcp-public/fantasy_football_multi_league.py"
  ],
  "cwd": "/absolute/path/to/fantasy-football-mcp-public"
}
```

## Available MCP tools

Default tool list with Reddit disabled:

### League and team

- `ff_get_leagues` - list Yahoo Fantasy Football leagues for the authenticated account.
- `ff_get_league_info` - return metadata and the authenticated user's team for a league.
- `ff_get_standings` - return standings for a league.
- `ff_get_teams` - return all teams in a league with basic information.
- `ff_get_roster` - return the logged-in team roster, or an optional `team_key`, with optional projections/external data.
- `ff_get_matchup` - return Yahoo matchup data for the user's team and week. This is raw matchup data without added narrative analysis.
- `ff_compare_teams` - compare two team rosters within a league.
- `ff_build_lineup` - build an optimized lineup from roster/player data using conservative, aggressive, or balanced strategy.

### Players and waivers

- `ff_get_players` - browse available free agents with optional filters and projections.
- `ff_get_waiver_wire` - return top available waiver-wire players with stats/projections and optional basic analysis.
- `ff_get_draft_rankings` - return Yahoo pre-draft rankings and ADP when Yahoo supplies that data.

### Draft helpers

- `ff_get_draft_results` - return teams with draft position and draft grade fields when Yahoo supplies them; it returns team-level draft fields only.
- `ff_get_draft_recommendation` - return strategy-based draft recommendations from available Yahoo/player data when draft support is available.
- `ff_analyze_draft_state` - return roster needs and strategic draft-state fields when draft support is available.

### Admin

- `ff_get_api_status` - return Yahoo API rate-limit/cache status.
- `ff_clear_cache` - clear cached API responses, optionally by pattern.
- `ff_refresh_token` - refresh Yahoo OAuth access tokens using the refresh token in `.env`.

### Optional Reddit tool

`ff_analyze_reddit_sentiment` is disabled by default. It appears in `tools/list` when `ENABLE_REDDIT_SENTIMENT` is truthy. Successful calls also require Reddit dependencies and credentials. Public setup does not require Reddit.

## Troubleshooting

### Yahoo provisioning or authorization errors

If OAuth succeeds but Fantasy endpoints return `additional_authorization_required` or `This application is not authorized to perform this action`, the app is not provisioned for Fantasy Sports API access. Submit or verify the access request at https://sports.yahoo.com/developer/access/ with the existing app/consumer key.

### Expired or rejected token

Run:

```bash
. .venv/bin/activate
python utils/refresh_yahoo_token.py
```

If refresh fails because the grant is gone or too old, run:

```bash
. .venv/bin/activate
python utils/reauth_yahoo.py
```

Restart the MCP client after token changes.

### No leagues found

- Confirm Yahoo has approved Fantasy Sports API access for the app.
- Confirm `FANTASY_SEASON=2026` or the intended season is set.
- Confirm `YAHOO_GUID` belongs to the Yahoo account that owns the leagues.
- Confirm the account has active Yahoo Fantasy Football leagues for that season.

## License

MIT License - see LICENSE for details.

## Attribution

Data provided by Yahoo Fantasy Sports. Yahoo and Yahoo Fantasy Sports are trademarks or registered trademarks of Yahoo. This project is not endorsed by or affiliated with Yahoo.