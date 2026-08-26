"""Tests for season-keyed bye week utility module."""

import json

import pytest

from src.utils import bye_weeks
from src.utils.bye_weeks import (
    build_team_bye_week_map,
    clear_cache,
    get_bye_week_with_fallback,
    load_static_bye_weeks,
)

OFFICIAL_2026_BYES = {
    "ARI": 14,
    "ATL": 11,
    "BAL": 13,
    "BUF": 7,
    "CAR": 5,
    "CHI": 10,
    "CIN": 6,
    "CLE": 11,
    "DAL": 14,
    "DEN": 10,
    "DET": 6,
    "GB": 11,
    "HOU": 8,
    "IND": 13,
    "JAC": 7,
    "KC": 5,
    "LAC": 7,
    "LAR": 11,
    "LV": 13,
    "MIA": 6,
    "MIN": 6,
    "NE": 11,
    "NO": 8,
    "NYG": 8,
    "NYJ": 13,
    "PHI": 10,
    "PIT": 9,
    "SEA": 11,
    "SF": 8,
    "TB": 10,
    "TEN": 9,
    "WAS": 7,
}

CANONICAL_TEAMS = set(OFFICIAL_2026_BYES)


@pytest.fixture(autouse=True)
def clear_bye_week_cache():
    clear_cache()
    yield
    clear_cache()


class TestLoadStaticByeWeeks:
    def test_load_static_bye_weeks_requires_requested_season_dataset(self):
        with pytest.raises(FileNotFoundError, match="2099"):
            load_static_bye_weeks(2099)

    def test_load_static_bye_weeks_returns_official_2026_map(self):
        result = load_static_bye_weeks(2026)

        assert result == OFFICIAL_2026_BYES
        assert set(result) == CANONICAL_TEAMS
        assert len(result) == 32
        assert all(isinstance(team, str) for team in result)
        assert all(isinstance(week, int) and not isinstance(week, bool) for week in result.values())
        assert all(5 <= week <= 14 for week in result.values())

    def test_load_static_bye_weeks_caches_by_season_identity(self):
        season_2026_first = load_static_bye_weeks(2026)
        season_2026_second = load_static_bye_weeks(2026)
        season_2025 = load_static_bye_weeks(2025)

        assert season_2026_first is season_2026_second
        assert season_2026_first is not season_2025
        assert season_2026_first != season_2025

    @pytest.mark.parametrize(
        "payload",
        [
            ["not", "a", "mapping"],
            {team: week for team, week in OFFICIAL_2026_BYES.items() if team != "KC"},
            dict(OFFICIAL_2026_BYES, XXX=7),
            dict(OFFICIAL_2026_BYES, KC=True),
            dict(OFFICIAL_2026_BYES, KC="5"),
            dict(OFFICIAL_2026_BYES, KC=19),
            dict(OFFICIAL_2026_BYES, KC=0),
        ],
    )
    def test_load_static_bye_weeks_fails_on_malformed_dataset(self, monkeypatch, tmp_path, payload):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "bye_weeks_2026.json").write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(bye_weeks, "_DATA_DIR", data_dir)

        with pytest.raises(ValueError, match="bye week data"):
            load_static_bye_weeks(2026)


class TestGetByeWeekWithFallback:
    def test_get_bye_week_prefers_valid_api_data_over_static(self):
        assert get_bye_week_with_fallback("KC", api_bye_week=6, season=2026) == 6
        assert OFFICIAL_2026_BYES["KC"] == 5

    def test_get_bye_week_returns_valid_api_data_without_static_dataset(self):
        assert get_bye_week_with_fallback("KC", api_bye_week=7, season=2099) == 7

    @pytest.mark.parametrize("api_bye_week", [None, 0, 19, True, "7"])
    def test_get_bye_week_uses_static_when_api_data_is_absent_or_invalid(self, api_bye_week):
        assert get_bye_week_with_fallback("KC", api_bye_week=api_bye_week, season=2026) == 5

    def test_get_bye_week_unknown_team_uses_valid_api_fallback(self):
        assert get_bye_week_with_fallback("XXX", api_bye_week=7, season=2026) == 7


class TestBuildTeamByeWeekMap:
    def test_build_team_bye_week_map_uses_static_when_api_data_absent(self):
        assert build_team_bye_week_map(2026) == OFFICIAL_2026_BYES

    def test_build_team_bye_week_map_prefers_valid_api_values(self):
        result = build_team_bye_week_map(2026, {"KC": 6, "SF": 9})

        assert result["KC"] == 6
        assert result["SF"] == 9
        assert result["ARI"] == 14
        assert set(result) == CANONICAL_TEAMS

    def test_build_team_bye_week_map_ignores_invalid_or_unknown_api_values(self):
        result = build_team_bye_week_map(
            2026,
            {"KC": 6, "SF": 0, "BUF": 19, "DAL": True, "XXX": 7},
        )

        assert result["KC"] == 6
        assert result["SF"] == 8
        assert result["BUF"] == 7
        assert result["DAL"] == 14
        assert "XXX" not in result
        assert set(result) == CANONICAL_TEAMS


class TestCacheManagement:
    def test_clear_cache_can_remove_one_season_without_clearing_another(self):
        season_2026_first = load_static_bye_weeks(2026)
        season_2025_first = load_static_bye_weeks(2025)

        clear_cache(2026)

        assert load_static_bye_weeks(2026) is not season_2026_first
        assert load_static_bye_weeks(2025) is season_2025_first

    def test_clear_cache_without_season_removes_all_cached_seasons(self):
        season_2026_first = load_static_bye_weeks(2026)
        season_2025_first = load_static_bye_weeks(2025)

        clear_cache()

        assert load_static_bye_weeks(2026) is not season_2026_first
        assert load_static_bye_weeks(2025) is not season_2025_first
