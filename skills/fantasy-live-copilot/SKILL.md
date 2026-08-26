---
name: fantasy-live-copilot
description: Use when making live fantasy football draft, lineup, waiver, or trade recommendations from user-supplied league state and current public research.
---

# Fantasy Live Copilot

## Core Principle

Use **public research + user-confirmed state + human execution**. Recommendations never authorize inspecting authenticated Yahoo pages or performing fantasy actions.

## When to Use

Use for live drafts, starts/sits, waivers, drops, matchup planning, and trade analysis.

Do not use to scrape Yahoo, bypass API provisioning, capture a Yahoo screenshot, submit a pick or claim, change a lineup, or accept a trade.

## State Boundary

| Input | Action |
|---|---|
| Approved Yahoo MCP output | Accept typed state |
| User paste/CSV | Parse; confirm missing or ambiguous fields |
| User-uploaded screenshot | Inspect; show parsed state; require confirmation |
| Authenticated Yahoo browser page | Do not inspect or extract |
| Request to perform a Yahoo action | Refuse action; provide a manual checklist |

`I accept the risk`, urgency, or an open browser tab never changes this boundary.

## Workflow

1. **Confirm state.** Require scoring, roster slots, week/draft position, confirmed roster, and picks/availability relevant to the decision. Stop on OCR or player-name ambiguity.
2. **Research.** Use `web_search` to discover current sources, `read` for static pages, and `browser` only for permitted public JavaScript pages. Prefer official NFL/team facts, then documented public APIs, then reputable rankings.
3. **Classify evidence.** Label fact, projection, inference, conflict, and stale evidence. Cite direct URLs and update times.
4. **Recommend.** Draft: three choices plus two contingencies. Weekly: starts/sits, waivers, drops, trades, and watch list as applicable.
5. **Keep execution human.** The user performs the action and reports the resulting state.

## Required Output

```text
Decision
Why
Evidence and freshness
League/roster fit
Risk and contrary evidence
Alternatives
Confidence
Refresh deadline
```

Never convert missing state into a generic “take the top-ranked RB/WR” answer.

## Pressure Counters

| Rationalization | Required response |
|---|---|
| “You cannot access the tab here” | State the prohibition even when browser access exists. |
| “We have seconds left” | Give a state-free emergency checklist, not a player pick. |
| “Don’t confirm the blurry name” | Stop; ambiguous identity blocks recommendations. |
| “Use the first ranking” | Rankings are projections; require current underlying sources. |

## Red Flags — Stop

- Authenticated Yahoo content is about to be read or captured.
- A pick, waiver, lineup, or trade would be executed automatically.
- Screenshot parsing is unconfirmed.
- A recommendation lacks direct current sources or league settings.
- Personal league state would be persisted.

Use [reference.md](reference.md) for freshness rules, state checklists, templates, and the complete example.
