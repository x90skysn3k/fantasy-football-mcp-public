"""Tests for dynamic Yahoo NFL game and league discovery."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clear_league_cache():
    import fantasy_football_multi_league as ff

    ff.LEAGUES_CACHE.clear()
    yield
    ff.LEAGUES_CACHE.clear()


def yahoo_games_response(*games):
    return {
        "fantasy_content": {
            "users": {
                "0": {
                    "user": [
                        [{"guid": "TEST_GUID_12345"}],
                        {
                            "games": {
                                str(index * 2 + 3): {"game": game}
                                for index, game in enumerate(games)
                            }
                        },
                    ]
                }
            }
        }
    }


def game(game_key, code, season, leagues=None):
    metadata = [
        {"game_key": game_key},
        {"code": code},
        {"season": season},
        {"name": f"{code.upper()} Fantasy"},
    ]
    if leagues is None:
        return [metadata]
    return [metadata, {"leagues": leagues}]


def leagues(*league_dicts):
    league_entries = {
        str(index): {"league": [[league_dict]]}
        for index, league_dict in enumerate(league_dicts)
    }
    league_entries["count"] = len(league_dicts)
    return league_entries


@pytest.mark.asyncio
async def test_discover_nfl_game_selects_nfl_by_code_from_nonzero_key():
    from fantasy_football_multi_league import discover_nfl_game

    response = yahoo_games_response(
        game("700", "nba", "2026"),
        game("933", "nfl", "2026"),
    )

    with patch("fantasy_football_multi_league.yahoo_api_call", AsyncMock(return_value=response)) as mock_api:
        result = await discover_nfl_game()

    mock_api.assert_awaited_once_with(
        "users;use_login=1/games;game_keys=nfl", use_cache=False
    )
    assert result == {"game_key": "933", "season": 2026, "code": "nfl"}


@pytest.mark.asyncio
async def test_discover_nfl_game_bypasses_endpoint_cache_for_current_metadata():
    from fantasy_football_multi_league import discover_nfl_game

    responses = iter(
        [
            yahoo_games_response(game("933", "nfl", "2026")),
            yahoo_games_response(game("944", "nfl", "2027")),
        ]
    )
    endpoint_cache = {}
    calls = []

    async def fake_yahoo_api_call(endpoint, *, use_cache=True):
        calls.append((endpoint, use_cache))
        if use_cache and endpoint in endpoint_cache:
            return endpoint_cache[endpoint]
        response = next(responses)
        if use_cache:
            endpoint_cache[endpoint] = response
        return response

    with patch("fantasy_football_multi_league.yahoo_api_call", fake_yahoo_api_call):
        first = await discover_nfl_game()
        second = await discover_nfl_game()

    assert first == {"game_key": "933", "season": 2026, "code": "nfl"}
    assert second == {"game_key": "944", "season": 2027, "code": "nfl"}
    assert calls == [
        ("users;use_login=1/games;game_keys=nfl", False),
        ("users;use_login=1/games;game_keys=nfl", False),
    ]


@pytest.mark.asyncio
async def test_discover_leagues_uses_nfl_game_at_nonzero_key_and_integer_season():
    from fantasy_football_multi_league import discover_leagues

    game_response = yahoo_games_response(game("933", "nfl", "2026"))
    leagues_response = yahoo_games_response(
        game("700", "nba", "2026", leagues()),
        game(
            "933",
            "nfl",
            "2026",
            leagues(
                {
                    "league_key": "933.l.61410",
                    "league_id": "61410",
                    "name": "Anyone But Andy",
                    "season": "2026",
                    "num_teams": 10,
                    "current_week": 1,
                    "scoring_type": "head2head",
                    "is_finished": 0,
                }
            ),
        ),
    )

    with patch(
        "fantasy_football_multi_league.yahoo_api_call",
        AsyncMock(side_effect=[game_response, leagues_response]),
    ):
        result = await discover_leagues()

    assert result == {
        "933.l.61410": {
            "key": "933.l.61410",
            "id": "61410",
            "name": "Anyone But Andy",
            "season": 2026,
            "num_teams": 10,
            "scoring_type": "head2head",
            "current_week": 1,
            "is_finished": 0,
        }
    }


@pytest.mark.asyncio
async def test_discover_leagues_merges_yahoo_single_key_metadata_entries():
    from fantasy_football_multi_league import discover_leagues

    league_metadata = {
        "0": {
            "league": [
                [
                    {"league_key": "933.l.61410"},
                    {"league_id": "61410"},
                    {"name": "Anyone But Andy"},
                    {"season": "2026"},
                    {"num_teams": 12},
                    {"status": "postdraft"},
                ]
            ]
        },
        "count": 1,
    }
    game_response = yahoo_games_response(game("933", "nfl", "2026"))
    leagues_response = yahoo_games_response(game("933", "nfl", "2026", league_metadata))

    with patch(
        "fantasy_football_multi_league.yahoo_api_call",
        AsyncMock(side_effect=[game_response, leagues_response]),
    ):
        result = await discover_leagues()

    assert result["933.l.61410"]["key"] == "933.l.61410"
    assert result["933.l.61410"]["id"] == "61410"
    assert result["933.l.61410"]["name"] == "Anyone But Andy"
    assert result["933.l.61410"]["season"] == 2026
    assert result["933.l.61410"]["num_teams"] == 12
    assert result["933.l.61410"]["status"] == "postdraft"


@pytest.mark.asyncio
async def test_discover_leagues_cache_is_keyed_by_resolved_season():
    from fantasy_football_multi_league import discover_leagues

    responses = [
        yahoo_games_response(game("933", "nfl", "2026")),
        yahoo_games_response(
            game(
                "933",
                "nfl",
                "2026",
                leagues(
                    {
                        "league_key": "933.l.1",
                        "league_id": "1",
                        "name": "2026 League",
                        "season": "2026",
                    }
                ),
            )
        ),
        yahoo_games_response(game("944", "nfl", "2027")),
        yahoo_games_response(
            game(
                "944",
                "nfl",
                "2027",
                leagues(
                    {
                        "league_key": "944.l.2",
                        "league_id": "2",
                        "name": "2027 League",
                        "season": "2027",
                    }
                ),
            )
        ),
    ]

    with patch("fantasy_football_multi_league.yahoo_api_call", AsyncMock(side_effect=responses)):
        first = await discover_leagues()
        second = await discover_leagues()

    assert list(first) == ["933.l.1"]
    assert first["933.l.1"]["season"] == 2026
    assert list(second) == ["944.l.2"]
    assert second["944.l.2"]["season"] == 2027


@pytest.mark.asyncio
async def test_discover_nfl_game_raises_when_yahoo_returns_no_nfl_game():
    from fantasy_football_multi_league import discover_nfl_game

    with patch(
        "fantasy_football_multi_league.yahoo_api_call",
        AsyncMock(return_value=yahoo_games_response(game("700", "nba", "2026"))),
    ):
        with pytest.raises(RuntimeError, match="NFL game"):
            await discover_nfl_game()


@pytest.mark.asyncio
async def test_discover_nfl_game_raises_for_malformed_nfl_season():
    from fantasy_football_multi_league import discover_nfl_game

    with patch(
        "fantasy_football_multi_league.yahoo_api_call",
        AsyncMock(return_value=yahoo_games_response(game("933", "nfl", "twenty-six"))),
    ):
        with pytest.raises(RuntimeError, match="season"):
            await discover_nfl_game()


@pytest.mark.asyncio
async def test_sleeper_current_season_delegates_to_resolver_with_state_metadata():
    import sleeper_api

    with (
        patch.object(
            sleeper_api.sleeper_client,
            "get_nfl_state",
            AsyncMock(return_value={"season": "2026", "week": 1}),
        ),
        patch("sleeper_api.resolve_fantasy_season", MagicMock(return_value=2026)) as mock_resolve,
    ):
        result = await sleeper_api.get_current_season()

    assert result == 2026
    mock_resolve.assert_called_once_with({"season": "2026"})


def test_setup_uses_current_nfl_metadata_opaque_game_key(monkeypatch, tmp_path):
    module_path = (
        Path(__file__).resolve().parents[2] / "utils" / "setup_yahoo_auth.py"
    )

    class FakeYahooFantasySportsQuery:
        init_kwargs = None
        requested_game_key = None

        def __init__(self, **kwargs):
            type(self).init_kwargs = kwargs

        def get_current_game_metadata(self):
            return SimpleNamespace(code="nfl", game_key="933")

        def get_user_games(self):
            raise AssertionError("setup must not select NFL history from get_user_games()")

        def get_user_leagues_by_game_key(self, game_key):
            type(self).requested_game_key = game_key
            return []

    fake_dotenv = ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    fake_yfpy = ModuleType("yfpy")
    fake_yfpy.YahooFantasySportsQuery = FakeYahooFantasySportsQuery

    monkeypatch.setenv("YAHOO_CLIENT_ID", "client-id")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "client-secret")
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)
    monkeypatch.setitem(sys.modules, "yfpy", fake_yfpy)
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "")
    monkeypatch.chdir(tmp_path)

    spec = importlib.util.spec_from_file_location("setup_yahoo_auth_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)

    assert FakeYahooFantasySportsQuery.init_kwargs["game_code"] == "nfl"
    assert "game_id" not in FakeYahooFantasySportsQuery.init_kwargs
    assert FakeYahooFantasySportsQuery.requested_game_key == "933"

    with pytest.raises(RuntimeError, match="missing game_key"):
        module.discover_yfpy_nfl_game_key(SimpleNamespace(code="nfl"))
