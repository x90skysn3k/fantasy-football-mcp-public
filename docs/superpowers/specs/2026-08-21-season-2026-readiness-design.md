# Fantasy Football MCP 2026 Season Readiness Design

**Date:** 2026-08-21
**Status:** Approved

## Goal

Prepare `x90skysn3k/fantasy-football-mcp-public` for public release and personal live use during the 2026 NFL season. The release must support draft preparation and weekly management through the same stdio MCP server in Pi/OMP and Claude Desktop.

## Current State

- The existing checkout is on dirty branch `updates-and-fixes`, 120 commits behind its fork tracking branch. Its uncommitted installer and dependency work must remain untouched.
- The fork's `main` is two commits ahead of and six commits behind active upstream `derekrbreese/fantasy-football-mcp-public/main`.
- The mounted MCP runs this checkout's `fantasy_football_multi_league.py`.
- The only local Yahoo credential set is `.env` in this checkout. It has a complete consumer/app/token field set, but its token timestamp is 2025-08-20 and live league discovery returns Yahoo HTTP 403.
- Cursor points to this checkout. Claude Desktop has no Fantasy Football MCP entry.
- Season handling contains a hard-coded 2025 game identifier and static `bye_weeks_2025.json` selection.
- Reddit sentiment has an open upstream 2026 policy-compatibility issue.
- Upstream tracks a non-placeholder `.yahoo_token.json`. Those third-party credentials must never be used or copied and must not exist in the release tree.

## Source-Control Strategy

Create an isolated `.worktrees/season-2026` worktree on branch `season-2026`, based on `upstream/main` at `9cea554` or its verified descendant. Preserve the dirty legacy checkout unchanged.

Review the fork's two unique commits and the local uncommitted setup changes. Port only behavior still missing from the upstream base. Do not merge the stale `updates-and-fixes` branch wholesale.

The completed branch will be pushed to the user's fork and prepared as a pull request against the fork's `main`. It must not rewrite upstream history.

## Runtime Architecture

`fantasy_football_multi_league.py` remains the canonical stdio server entry point for this release. Pi/OMP and Claude Desktop use the same Python environment, command, working directory, and credential store. Client configs contain no Yahoo secrets.

FastMCP/HTTP files must remain importable, but HTTP deployment is outside this release's acceptance gate. No broad server refactor is included.

The canonical server exposes only tools that are operational for the release target. Yahoo league, roster, matchup, lineup, waiver, standings, draft, token-refresh, and cache-status tools remain enabled. Reddit sentiment registration is disabled by default and appears only when an explicit Reddit feature setting is enabled and validated at startup. Documentation states that Reddit is unsupported for the 2026 release.

## Season Data

Introduce one season resolver used by authentication, Yahoo game discovery, Sleeper calls, roster enhancement, draft tooling, and bye-week fallback.

Resolution order:

1. Explicit `FANTASY_SEASON` configuration when set.
2. Yahoo NFL game metadata for game code `nfl` when authenticated.
3. The release default `2026` when offline or before authorization.

Remove hard-coded Yahoo game ID `449` and direct filename references to `bye_weeks_2025.json`. Static bye weeks become versioned data selected by season, with validated 2026 data and an explicit error when a requested fallback season has no dataset. Live Yahoo/Sleeper values remain preferred where the existing contract already treats them as authoritative; static data is the deterministic fallback, not a silent cross-season substitute.

Season validation accepts a four-digit supported year and rejects malformed values at startup. Team maps must contain all 32 NFL teams and bye weeks within the NFL regular-season range.

## Yahoo Authorization and Credential Custody

Use `YAHOO_CONSUMER_KEY` and `YAHOO_CONSUMER_SECRET` as the canonical app credential names across server code, setup utilities, examples, and documentation. Remove contradictory client-ID-only setup paths rather than maintaining two config conventions.

Use the repository-local, gitignored `.env` as the single credential store for this release. Load it from the server file's directory, independent of the launching client's working directory. OAuth utilities update tokens atomically and preserve unrelated settings. MCP client JSON must contain command/argument/cwd configuration only.

Authorization flow:

1. Try the existing local Yahoo app credentials.
2. Attempt refresh-token grant and persist a successful access/refresh token set plus token timestamp.
3. Verify NFL game discovery and league discovery.
4. If the refresh grant is invalid or revoked, run an interactive authorization-code grant for the existing app.
5. If Yahoo reports that the application itself is not provisioned for Fantasy Sports, stop with a precise diagnostic and create/authorize a replacement Yahoo Developer app; do not mislabel provisioning failure as token expiry.

Never log or return consumer secrets, access tokens, refresh tokens, authorization codes, or complete credential-file content. Verification reports only field presence, timestamps, HTTP status classes, and sanitized Yahoo error descriptions.

Delete `.yahoo_token.json` from the release tree and add token-file patterns to `.gitignore`. The upstream token is presumed compromised and belongs to a third party; the release notes must recommend upstream revocation/history remediation without reproducing it.

## Data Flow and Error Handling

Each MCP tool resolves the active season, ensures a usable Yahoo token through the shared API client, calls the appropriate Yahoo endpoint, and returns typed JSON-compatible output through the existing MCP contract.

Authentication errors are classified into:

- expired access token: refresh once, then retry once;
- invalid/revoked refresh token: require interactive reauthorization;
- application not provisioned for Fantasy Sports: require Yahoo Developer app correction or replacement;
- authorization denied by the user: fail closed without changing stored credentials;
- Yahoo rate limit or transient upstream failure: return the existing sanitized operational error without converting it into an authentication error.

No tool returns canned data on Yahoo failure. Draft and weekly tools may use documented Sleeper/public enrichment only after Yahoo identity, league, and roster context succeeds.

## Verification

Permanent contract tests cover:

- season resolution precedence and malformed configuration;
- 2026 static bye-week completeness and bounds;
- absence of 2025 hard-coding in active season paths;
- Yahoo error classification and one-refresh/one-retry behavior;
- atomic token persistence without secret logging;
- Reddit tool omission by default;
- stable MCP tool names and schemas for draft and weekly workflows;
- client configs containing no credentials.

Repository checks run the focused unit and MCP contract suites, then the complete existing test suite and configured lint/type checks when present.

Behavioral acceptance uses the actual stdio server:

1. Start the server from a directory other than the repository root to prove deterministic `.env` loading.
2. Complete Yahoo authorization with the existing app or a replacement app.
3. Discover at least one 2026 Yahoo NFL league.
4. Exercise league info, standings, roster, matchup, opponent comparison, optimal lineup, players/free agents, waiver wire, draft rankings, draft recommendation, draft-state analysis, draft results when available, API status, and token refresh.
5. Verify that each unavailable preseason or league-state operation returns an accurate state error rather than fabricated data.
6. Configure and handshake the same stdio server from Pi/OMP and Claude Desktop.
7. Restart the server and repeat league discovery to prove persisted authorization.

Personal league data and credential values must not appear in commits, test fixtures, logs, screenshots, or the public pull request.

## Release Deliverables

- `season-2026` branch based on current upstream.
- Versioned 2026 season/bye-week support without hard-coded game IDs.
- Consolidated Yahoo OAuth configuration and sanitized error handling.
- Reddit sentiment disabled by default and documented as unsupported.
- Secret-free Pi/OMP and Claude Desktop stdio configuration instructions.
- Passing automated checks and a recorded sanitized live-smoke result.
- Public fork branch and pull-request-ready change set.

## Non-Goals

- Repairing Reddit API integration.
- Supporting FastMCP/HTTP deployment as a release gate.
- Rewriting the server architecture or splitting the main module.
- Importing upstream's tracked token or rewriting upstream repository history.
- Guaranteeing tool output for Yahoo workflows unavailable before draft completion or schedule activation.
