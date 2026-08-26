"""Tests for fantasy season resolution."""

import pytest

from src.utils.season import DEFAULT_FANTASY_SEASON, resolve_fantasy_season


def test_default_fantasy_season_is_2026(monkeypatch):
    monkeypatch.delenv("FANTASY_SEASON", raising=False)

    assert DEFAULT_FANTASY_SEASON == 2026
    assert resolve_fantasy_season() == 2026


def test_explicit_season_precedes_yahoo(monkeypatch):
    monkeypatch.setenv("FANTASY_SEASON", "2026")

    assert resolve_fantasy_season({"season": "2025"}) == 2026


@pytest.mark.parametrize("value", ["", "twenty-six", "26", "20260", "1999"])
def test_invalid_explicit_season_fails(monkeypatch, value):
    monkeypatch.setenv("FANTASY_SEASON", value)

    with pytest.raises(ValueError, match="FANTASY_SEASON"):
        resolve_fantasy_season({"season": "2026"})


@pytest.mark.parametrize("value", [2026, "2026"])
def test_yahoo_season_is_normalized_when_env_unset(monkeypatch, value):
    monkeypatch.delenv("FANTASY_SEASON", raising=False)

    assert resolve_fantasy_season({"season": value}) == 2026


@pytest.mark.parametrize("value", [True, "", "20260", "1999"])
def test_invalid_yahoo_season_fails_when_provided(monkeypatch, value):
    monkeypatch.delenv("FANTASY_SEASON", raising=False)

    with pytest.raises(ValueError, match="Yahoo season"):
        resolve_fantasy_season({"season": value})
