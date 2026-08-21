"""Focused deterministic handler shape tests for MCP tool contracts."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any

import pytest

from src.handlers import draft_handlers, matchup_handlers, player_handlers, roster_handlers


LEAGUE_KEY = "461.l.61410"
TEAM_KEY = "461.l.61410.t.1"


@pytest.mark.asyncio
async def test_draft_recommendation_passes_arguments_to_simple_helper(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_recommendation(
        league_key: str,
        strategy: str,
        num_recommendations: int,
        current_pick: int | None,
    ) -> dict[str, Any]:
        captured.update(
            {
                "league_key": league_key,
                "strategy": strategy,
                "num_recommendations": num_recommendations,
                "current_pick": current_pick,
            }
        )
        return {"recommendations": [{"name": "Player A"}], "strategy": strategy}

    monkeypatch.setattr(draft_handlers, "DRAFT_AVAILABLE", True)
    monkeypatch.setattr(draft_handlers, "get_draft_recommendation_simple", fake_recommendation)

    result = await draft_handlers.handle_ff_get_draft_recommendation(
        {
            "league_key": LEAGUE_KEY,
            "strategy": "aggressive",
            "num_recommendations": 3,
            "current_pick": 12,
        }
    )

    assert captured == {
        "league_key": LEAGUE_KEY,
        "strategy": "aggressive",
        "num_recommendations": 3,
        "current_pick": 12,
    }
    assert result == {"recommendations": [{"name": "Player A"}], "strategy": "aggressive"}


@pytest.mark.asyncio
async def test_draft_state_passes_arguments_to_simple_helper(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_analyze(league_key: str, strategy: str) -> dict[str, Any]:
        captured.update({"league_key": league_key, "strategy": strategy})
        return {"league_key": league_key, "needs": ["RB"], "strategy": strategy}

    monkeypatch.setattr(draft_handlers, "DRAFT_AVAILABLE", True)
    monkeypatch.setattr(draft_handlers, "analyze_draft_state_simple", fake_analyze)

    result = await draft_handlers.handle_ff_analyze_draft_state(
        {"league_key": LEAGUE_KEY, "strategy": "conservative"}
    )

    assert captured == {"league_key": LEAGUE_KEY, "strategy": "conservative"}
    assert result == {"league_key": LEAGUE_KEY, "needs": ["RB"], "strategy": "conservative"}


@pytest.mark.asyncio
async def test_draft_results_shape_wraps_all_team_info(monkeypatch):
    teams = [
        {"team_key": TEAM_KEY, "name": "Team One", "draft_position": 1},
        {"team_key": "461.l.61410.t.2", "name": "Team Two", "draft_position": 2},
    ]

    async def fake_all_teams(league_key: str) -> list[dict[str, Any]]:
        assert league_key == LEAGUE_KEY
        return teams

    monkeypatch.setattr(draft_handlers, "get_all_teams_info", fake_all_teams)

    result = await draft_handlers.handle_ff_get_draft_results({"league_key": LEAGUE_KEY})

    assert result == {"league_key": LEAGUE_KEY, "total_teams": 2, "draft_results": teams}


@pytest.mark.asyncio
async def test_matchup_returns_raw_yahoo_matchups_without_analysis(monkeypatch):
    raw = {"fantasy_content": {"team": [{"matchups": {"count": 1}}]}}
    calls: list[str] = []

    async def fake_team_key(league_key: str) -> str:
        assert league_key == LEAGUE_KEY
        return TEAM_KEY

    async def fake_yahoo(path: str) -> dict[str, Any]:
        calls.append(path)
        return raw

    monkeypatch.setattr(matchup_handlers, "get_user_team_key", fake_team_key)
    monkeypatch.setattr(matchup_handlers, "yahoo_api_call", fake_yahoo)

    result = await matchup_handlers.handle_ff_get_matchup({"league_key": LEAGUE_KEY, "week": 4})

    assert calls == [f"team/{TEAM_KEY}/matchups;week=4"]
    assert result == {
        "league_key": LEAGUE_KEY,
        "team_key": TEAM_KEY,
        "week": 4,
        "message": "Matchup data retrieved",
        "raw_matchups": raw,
    }


@pytest.mark.asyncio
async def test_roster_basic_shape_uses_yahoo_roster_and_team_info(monkeypatch):
    yahoo_payload = {"fantasy_content": {"team": []}}
    parsed_roster = [{"name": "Josh Allen", "position": "QB"}]

    async def fake_team_info(league_key: str) -> dict[str, Any]:
        assert league_key == LEAGUE_KEY
        return {
            "team_key": TEAM_KEY,
            "team_name": "Team One",
            "draft_position": 3,
            "draft_grade": "B+",
        }

    async def fake_yahoo(path: str) -> dict[str, Any]:
        assert path == f"team/{TEAM_KEY}/roster"
        return yahoo_payload

    async def fake_season(league_key: str) -> int:
        assert league_key == LEAGUE_KEY
        return 2026

    def fake_parse(data: dict[str, Any], season: int) -> list[dict[str, Any]]:
        assert data == yahoo_payload
        assert season == 2026
        return parsed_roster

    monkeypatch.setattr(roster_handlers, "get_user_team_info", fake_team_info)
    monkeypatch.setattr(roster_handlers, "yahoo_api_call", fake_yahoo)
    monkeypatch.setattr(roster_handlers, "resolve_league_season", fake_season)
    monkeypatch.setattr(roster_handlers, "parse_team_roster", fake_parse)

    result = await roster_handlers.handle_ff_get_roster(
        {"league_key": LEAGUE_KEY, "data_level": "basic"}
    )

    assert result == {
        "status": "success",
        "league_key": LEAGUE_KEY,
        "team_key": TEAM_KEY,
        "team_name": "Team One",
        "draft_position": 3,
        "draft_grade": "B+",
        "roster": parsed_roster,
    }


@dataclass
class FakePlayer:
    name: str
    position: str
    team: str
    opponent: str | None = "NYJ"
    player_tier: str = "starter"
    matchup_score: int = 7
    matchup_description: str = "Good matchup"
    composite_score: float = 18.51
    yahoo_projection: float = 14.24
    sleeper_projection: float = 13.67
    trending_score: int = 1234
    floor_projection: float = 9.31
    ceiling_projection: float = 23.92


class FakeLineupOptimizer:
    async def parse_yahoo_roster(self, roster_data: dict[str, Any], season: int) -> list[FakePlayer]:
        assert roster_data == {"fantasy_content": {"team": []}}
        assert season == 2026
        return [FakePlayer("Starter", "QB", "BUF"), FakePlayer("Bench", "RB", "SF")]

    async def enhance_with_external_data(
        self, players: list[FakePlayer], week: int | None = None
    ) -> list[FakePlayer]:
        assert week == 5
        return players

    async def optimize_lineup_smart(
        self,
        players: list[FakePlayer],
        strategy: str,
        week: int | None,
        use_llm: bool,
    ) -> dict[str, Any]:
        assert strategy == "balanced"
        assert week == 5
        assert use_llm is False
        return {
            "status": "success",
            "starters": {"QB": players[0]},
            "bench": [players[1]],
            "recommendations": ["Start Starter"],
            "errors": [],
            "data_quality": {
                "total_players": 2,
                "valid_players": 2,
                "players_with_projections": 2,
                "players_with_matchup_data": 2,
            },
            "strategy_used": "balanced",
        }


@pytest.mark.asyncio
async def test_lineup_shape_formats_optimizer_result(monkeypatch):
    optimizer_module = types.ModuleType("lineup_optimizer")
    optimizer_module.lineup_optimizer = FakeLineupOptimizer()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "lineup_optimizer", optimizer_module)

    async def fake_team_key(league_key: str) -> str:
        assert league_key == LEAGUE_KEY
        return TEAM_KEY

    async def fake_yahoo(path: str) -> dict[str, Any]:
        assert path == f"team/{TEAM_KEY}/roster"
        return {"fantasy_content": {"team": []}}

    async def fake_season(league_key: str) -> int:
        assert league_key == LEAGUE_KEY
        return 2026

    monkeypatch.setattr(matchup_handlers, "get_user_team_key", fake_team_key)
    monkeypatch.setattr(matchup_handlers, "yahoo_api_call", fake_yahoo)
    monkeypatch.setattr(matchup_handlers, "resolve_league_season", fake_season)

    result = await matchup_handlers.handle_ff_build_lineup(
        {"league_key": LEAGUE_KEY, "week": 5, "strategy": "balanced", "use_llm": False}
    )

    assert result["status"] == "success"
    assert result["league_key"] == LEAGUE_KEY
    assert result["team_key"] == TEAM_KEY
    assert result["week"] == 5
    assert result["strategy"] == "balanced"
    assert result["optimal_lineup"] == {
        "QB": {
            "name": "Starter",
            "tier": "STARTER",
            "team": "BUF",
            "opponent": "NYJ",
            "matchup_score": 7,
            "matchup": "Good matchup",
            "composite_score": 18.5,
            "yahoo_proj": 14.2,
            "sleeper_proj": 13.7,
            "trending": "1,234 adds",
            "floor": 9.3,
            "ceiling": 23.9,
        }
    }
    assert result["bench"] == [
        {
            "name": "Bench",
            "position": "RB",
            "opponent": "NYJ",
            "composite_score": 18.5,
            "matchup_score": 7,
            "tier": "STARTER",
        }
    ]
    assert result["analysis"] == {
        "total_players": 2,
        "valid_players": 2,
        "players_with_projections": 2,
        "players_with_matchup_data": 2,
        "strategy_used": "balanced",
        "data_sources": [
            "Yahoo projections",
            "Sleeper rankings",
            "Matchup analysis",
            "Trending data",
        ],
    }


@pytest.mark.asyncio
async def test_waiver_basic_shape_without_enhancement(monkeypatch):
    players = [
        {"name": "Available RB", "position": "RB", "owned_pct": 42.0},
        {"name": "Available WR", "position": "WR", "owned_pct": 17.0},
    ]

    async def fake_waivers(
        league_key: str,
        position: str,
        sort: str,
        count: int,
    ) -> list[dict[str, Any]]:
        assert (league_key, position, sort, count) == (LEAGUE_KEY, "all", "rank", 2)
        return players

    monkeypatch.setattr(player_handlers, "get_waiver_wire_players", fake_waivers)

    result = await player_handlers.handle_ff_get_waiver_wire(
        {
            "league_key": LEAGUE_KEY,
            "position": "all",
            "sort": "rank",
            "count": 2,
            "include_analysis": False,
            "include_projections": False,
            "include_external_data": False,
        }
    )

    assert result == {
        "status": "success",
        "league_key": LEAGUE_KEY,
        "position": "all",
        "sort": "rank",
        "total_players": 2,
        "players": players,
    }
