# Fantasy Live Copilot Reference

## Source Order

1. Official NFL and team injury, transaction, schedule, and depth-chart pages.
2. Documented public APIs already used by the project, including Sleeper.
3. Reputable current fantasy rankings, ADP, and analysis.
4. Search-result summaries only to locate the underlying source.

Use direct article or data URLs in recommendations. A search snippet is not evidence.

## Freshness

| Evidence | Requirement |
|---|---|
| Draft picks and availability | User-confirm immediately before each recommendation |
| Injury and practice status | Refresh every weekly run; refresh near kickoff when decisive |
| ADP and rankings | Same-day during active draft season when available |
| Weather | Refresh on game day for weather-sensitive games |
| Schedule and byes | Version by season; verify against official NFL schedule |
| Stale source | Label it, lower confidence, and state the required refresh |

## Evidence Labels

- **Fact:** official status, transaction, schedule, roster rule, or confirmed user state.
- **Projection:** ranking, ADP, expected points, workload, or model estimate.
- **Inference:** conclusion derived from facts/projections; explain the derivation.
- **Conflict:** reputable sources disagree; show both and state the controlling league-specific factor.

## Draft State Checklist

- season; scoring and league size;
- roster slots and draft style;
- draft position and timer;
- completed picks or confirmed available-player pool;
- confirmed user roster;
- keeper, auction, or special rules.

Return three ranked candidates and two contingencies. Update state only after the user reports the actual pick.

## Weekly State Checklist

- week, scoring, and lineup slots;
- confirmed roster, starters, bench, and IR;
- opponent/matchup context when relevant;
- confirmed available-player pool;
- waiver priority or budget and claim rules;
- trade constraints when evaluating a trade.

Return only applicable sections: starts/sits, waiver priorities, drop candidates, trade considerations, watch list.

## Screenshot Confirmation

Use this before research:

```text
Parsed state — please confirm
League/week: …
Scoring/slots: …
Roster or draft picks: …
Available players: …
Uncertain fields: …

I will not recommend or research player-specific decisions until uncertain fields are corrected or confirmed.
```

Do not capture the Yahoo page yourself. Only inspect an image the user deliberately uploads.

## Recommendation Template

```text
Decision: [ranked action]
Why: [league-specific reasoning]
Evidence and freshness:
- [Fact/Projection/Inference/Conflict] [claim] — [direct URL], [published/updated]
League/roster fit: [slots, scoring, need, scarcity]
Risk and contrary evidence: [what can invalidate this]
Alternatives: [ranked contingencies]
Confidence: [High/Medium/Low and why]
Refresh deadline: [time/event requiring another check]
Human action: [exact checklist the user performs]
```

## Complete Illustrative Weekly Example

Synthetic state: 12-team PPR, one FLEX, Player Alpha and Player Beta compete for FLEX. The user confirmed both names and roster slots.

```text
Decision: Start Player Alpha at FLEX; keep Player Beta as the contingency.

Why: Alpha has the confirmed starting role and the better reception floor for PPR. Beta's value depends on a teammate being ruled out.

Evidence and freshness:
- Fact: Alpha is not listed on the current official injury report — https://www.nfl.com/injuries/, checked game day.
- Fact: Schedule and kickoff are confirmed — https://www.nfl.com/schedules/, checked game day.
- Projection: Public rankings favor Alpha; rankings are estimates, not facts — cite the direct current ranking article used in the real run.

League/roster fit: PPR rewards Alpha's reception floor; no other open slot changes the comparison.

Risk and contrary evidence: A pregame inactive report or role change overrides this recommendation. Beta becomes preferable only if the named teammate is inactive and Beta's workload is confirmed.

Alternatives: 1) Beta if the contingency triggers; 2) the next user-confirmed active FLEX option.

Confidence: Medium — role evidence is current, but final inactive news can change workload.

Refresh deadline: Recheck official inactive and injury news 90 minutes before kickoff.

Human action: Recheck the cited sources, then make the lineup change manually in Yahoo.
```

Generic names keep the example reusable. Real recommendations must cite the actual direct ranking or news page, not the generic research surface above.

## Privacy Checklist

- No passwords, cookies, browser profiles, API secrets, OAuth tokens, or authorization codes.
- No persisted league IDs, opponents, rosters, screenshots, picks, or waiver history.
- No personal data in commits, fixtures, logs, or reports.
- Use synthetic state for testing.

## Common Mistakes

| Mistake | Correction |
|---|---|
| Treating browser inability as the only reason not to scrape | State the Yahoo boundary even when browser access exists. |
| Recommending from default rank under time pressure | Request confirmed state or provide a non-player emergency checklist. |
| Guessing an OCR player name | Show the parse and stop for confirmation. |
| Citing a search snippet | Open and cite the underlying source. |
| Mixing facts and rankings | Label facts, projections, inference, and conflicts separately. |
| Treating a recommendation as completed state | Update only after the user reports the action. |
