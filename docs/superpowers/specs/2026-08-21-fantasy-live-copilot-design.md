# Fantasy Live Copilot Skill Design

**Date:** 2026-08-21
**Status:** Approved

## Goal

Add one repository-local `fantasy-live-copilot` skill that supports live draft decisions and weekly roster decisions using user-confirmed league state plus current, cited public research. The skill is recommendation-only. It never automates authenticated Yahoo page access or fantasy actions.

## Why a Skill

The Yahoo Fantasy API currently requires separate application provisioning. The existing app can refresh OAuth tokens but is not entitled to Fantasy endpoints. The copilot must remain useful while that external approval is pending and continue to add research value after the official MCP tools become available.

The browser is a research surface, not an unofficial Yahoo API. Yahoo's current Terms of Service prohibit automated collection from Yahoo services without express prior permission. The skill therefore does not navigate, inspect, extract, scrape, or act on authenticated Yahoo Fantasy pages. It does not reverse-engineer private endpoints.

Relevant policies and sources:

- Yahoo automated collection restriction: https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html
- Yahoo Fantasy API access workflow: https://sports.yahoo.com/developer/
- Yahoo Fantasy API access application: https://sports.yahoo.com/developer/access/
- Official NFL fantasy research surface: https://www.nfl.com/news/series/fantasy

## Location and Activation

Create the versioned skill at:

```text
skills/fantasy-live-copilot/SKILL.md
```

The skill activates for requests involving live fantasy draft recommendations, roster construction, starts/sits, waiver priorities, drop decisions, matchup planning, or trade evaluation. It must not activate for requests to scrape Yahoo, bypass API provisioning, automate draft picks, submit claims, accept trades, or modify lineups.

## Operating Modes

### Draft Mode

Required state:

- season and scoring format;
- league size and roster slots;
- draft style and pick timer when known;
- user's draft position;
- completed picks in order or the current available-player pool;
- user's confirmed roster.

Flow:

1. Parse supplied text, CSV, screenshot, or official MCP output.
2. Normalize player, team, and position names.
3. Show the parsed draft state and require confirmation when OCR or ambiguous text was used.
4. Research current ADP, rankings, injuries, transactions, depth-chart movement, and role changes.
5. Exclude confirmed drafted players.
6. Score candidates for value, roster fit, positional scarcity, floor, ceiling, and current risk.
7. Return three ranked recommendations plus two contingency options.
8. Update draft state only after the user reports the actual selection.

The skill never clicks a player, enters a draft room, submits a pick, or treats a recommendation as a completed pick.

### Weekly Mode

Required state:

- scoring format, lineup slots, and week;
- user's confirmed roster;
- current starters and bench when available;
- opponent or matchup context when supplied;
- available-player list for waiver analysis;
- waiver budget or priority when relevant.

Flow:

1. Parse and confirm supplied league state.
2. Research official injury reports, practice participation, transactions, depth charts, game status, weather, and current fantasy analysis.
3. Identify lineup constraints, byes, injuries, inactive risk, and replacement options.
4. Produce starts/sits, waiver priorities, drop candidates, trade considerations, and watch-list items.
5. Explain the recommendation's sensitivity to late news and state the next refresh deadline.

The skill may recommend trade targets or evaluate a proposed trade. It never submits, accepts, rejects, or cancels a Yahoo trade; sets a lineup; submits a waiver claim; or changes league settings.

## State Inputs

Accepted inputs, in descending reliability:

1. Typed output from approved official Yahoo MCP tools.
2. User-pasted structured tables, text, or CSV.
3. User-uploaded screenshots analyzed through the image inspection tool.

The skill must not capture Yahoo screenshots itself through browser automation. For user-supplied screenshots, it must:

- quote or tabulate the parsed player names and state;
- mark unreadable or uncertain fields;
- ask for confirmation before recommendations;
- avoid retaining the screenshot or parsed personal league state beyond the active session.

## Public Research

Preferred source order:

1. NFL and official team injury, transaction, schedule, and depth-chart information.
2. Public league data APIs already used by the project, such as Sleeper, within their documented contracts.
3. Reputable current fantasy rankings, ADP, and analysis pages that permit normal access.
4. Search-result summaries only as leads; recommendations cite the underlying page.

Tool selection:

- `web_search` discovers current sources.
- `read` retrieves static pages and documents.
- `browser` is used only when a permitted public source requires JavaScript or interactive viewing.
- authenticated Yahoo pages are excluded from browser use.

Every material claim includes a direct source URL and publication or update time when available. The skill distinguishes:

- verified fact;
- projection or ranking;
- inference;
- unresolved source conflict.

## Freshness Policy

- Draft availability and pick state: user-confirmed immediately before each recommendation.
- Injury and practice status: refreshed for every weekly run and again near kickoff when the recommendation depends on availability.
- ADP and rankings: same-day during active draft season when possible.
- Weather: refreshed on game day for materially weather-sensitive decisions.
- Static schedule and bye data: versioned by season and checked against the official schedule.

Stale evidence is not silently reused. The output names stale items and reduces confidence.

## Recommendation Contract

Each recommendation contains:

```text
Decision
Why
Evidence
Roster/league fit
Risk and contrary evidence
Alternatives
Confidence
Refresh deadline
```

Draft output ranks three primary candidates and two contingencies. Weekly output separates starts/sits, waiver adds, drop candidates, trades, and watch-list items. Recommendations use concise tables when comparing players.

The skill never describes a projection as fact. When reputable sources conflict, it reports the disagreement and explains which source or league-specific factor controls the recommendation.

## Error Handling

- Missing scoring or roster settings: request the minimum missing state before ranking players.
- OCR ambiguity: stop and confirm parsed fields.
- Player-name collision: require team/position confirmation.
- Stale source: refresh or label stale and lower confidence.
- Source unavailable or blocked: use another permitted source and disclose the gap.
- Yahoo API provisioning failure: use manual user-supplied state; do not fall back to Yahoo browser scraping.
- Request for automated Yahoo action: refuse the action and provide a recommendation/checklist instead.

## Privacy and Safety

- Never request or store Yahoo passwords, cookies, session tokens, consumer secrets, OAuth tokens, or browser-profile data.
- Never embed credentials in prompts, skill files, MCP configs, logs, reports, or examples.
- Do not retain personal league identifiers, opponent identities, rosters, screenshots, or draft history beyond the active session.
- Do not publish screenshots or personal league data in commits or test fixtures.
- All decisions remain human-confirmed and user-executed.

## Verification

Skill evaluation fixtures cover:

1. Twelve-team PPR draft with confirmed pick history and an available-player pool.
2. Draft screenshot containing one ambiguous player name that requires confirmation.
3. Weekly lineup with a late injury and two replacement options.
4. Waiver run with budget constraints and a required drop candidate.
5. Conflicting rankings with official injury evidence controlling the recommendation.
6. Stale article rejected in favor of current evidence.
7. Yahoo API provisioning failure falling back to manual state.
8. Request to scrape Yahoo rejected.
9. Request to submit a draft pick, waiver claim, trade, or lineup change rejected.
10. Approved Yahoo MCP output accepted without exposing credential material.

The skill passes only if recommendations cite current sources, separate facts from projections, confirm ambiguous input, and preserve the no-Yahoo-automation boundary.

## Non-Goals

- Browser scraping of Yahoo Fantasy pages.
- Automated draft-room participation.
- Automated lineup, waiver, trade, or league-setting changes.
- Reverse-engineering Yahoo private endpoints.
- Persistent storage of personal league state.
- Repairing or replacing Yahoo's Fantasy API provisioning process.
