"""
Utility module for loading and managing NFL bye week data.

Provides season-keyed static bye week data as a fallback when API data is
missing or invalid.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)

CANONICAL_TEAM_ABBRS: Set[str] = {
    "ARI",
    "ATL",
    "BAL",
    "BUF",
    "CAR",
    "CHI",
    "CIN",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GB",
    "HOU",
    "IND",
    "JAC",
    "KC",
    "LAC",
    "LAR",
    "LV",
    "MIA",
    "MIN",
    "NE",
    "NO",
    "NYG",
    "NYJ",
    "PHI",
    "PIT",
    "SEA",
    "SF",
    "TB",
    "TEN",
    "WAS",
}

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Cache for loaded bye week data to avoid repeated file reads. Keyed by season so
# callers cannot accidentally reuse one season's official dataset for another.
_BYE_WEEK_CACHE: Dict[int, Dict[str, int]] = {}


def _is_valid_bye_week(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 18


def _validate_static_bye_weeks(season: int, bye_weeks: object) -> Dict[str, int]:
    if not isinstance(bye_weeks, dict):
        raise ValueError(f"Static bye week data for {season} must be a mapping")

    team_keys = set(bye_weeks)
    if team_keys != CANONICAL_TEAM_ABBRS:
        missing = sorted(CANONICAL_TEAM_ABBRS - team_keys)
        extra = sorted(team_keys - CANONICAL_TEAM_ABBRS)
        details = []
        if missing:
            details.append(f"missing teams: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected teams: {', '.join(extra)}")
        raise ValueError(
            f"Static bye week data for {season} has invalid team keys ({'; '.join(details)})"
        )

    validated: Dict[str, int] = {}
    for team, week in bye_weeks.items():
        if not isinstance(team, str) or not _is_valid_bye_week(week):
            raise ValueError(f"Static bye week data for {season} has invalid bye week for {team}")
        validated[team] = week

    return validated


def load_static_bye_weeks(season: int) -> Dict[str, int]:
    """
    Load strict static bye week data for a season.

    Raises FileNotFoundError when the requested season has no dataset and
    ValueError when a dataset is malformed. Missing or malformed data is never
    converted to an empty fallback map.
    """
    if season in _BYE_WEEK_CACHE:
        return _BYE_WEEK_CACHE[season]

    data_file = _DATA_DIR / f"bye_weeks_{season}.json"
    with data_file.open("r", encoding="utf-8") as file:
        loaded = json.load(file)

    bye_weeks = _validate_static_bye_weeks(season, loaded)
    _BYE_WEEK_CACHE[season] = bye_weeks
    logger.info("Loaded static bye week data for %s teams in %s", len(bye_weeks), season)
    return bye_weeks


def get_bye_week_with_fallback(
    team_abbr: str,
    api_bye_week: Optional[int] = None,
    *,
    season: int,
) -> Optional[int]:
    """
    Get bye week for a team using API-first semantics.

    Valid API bye weeks are preferred without touching static data. Static
    season data is used only when API data is absent or invalid for a canonical
    team.
    """
    if _is_valid_bye_week(api_bye_week):
        return api_bye_week

    static_data = load_static_bye_weeks(season)
    if team_abbr not in static_data:
        logger.warning("No static bye week data found for unknown team %s in %s", team_abbr, season)
        return None

    return static_data[team_abbr]


def build_team_bye_week_map(
    season: int,
    api_team_data: Optional[Dict[str, int]] = None,
) -> Dict[str, int]:
    """
    Build a canonical team-to-bye-week mapping for a season.

    Starts from strict static season data, then overlays valid canonical API bye
    weeks. Unknown teams and malformed API values are ignored instead of being
    added to the canonical map.
    """
    bye_week_map = load_static_bye_weeks(season).copy()

    if not api_team_data:
        return bye_week_map

    for team, week in api_team_data.items():
        if team not in CANONICAL_TEAM_ABBRS:
            logger.warning("Ignoring API bye week for unknown team %s", team)
            continue
        if not _is_valid_bye_week(week):
            logger.warning("Ignoring invalid API bye week %s for %s", week, team)
            continue
        bye_week_map[team] = week

    return bye_week_map


def clear_cache(season: Optional[int] = None) -> None:
    """Clear cached bye week data for one season, or all seasons when omitted."""
    if season is None:
        _BYE_WEEK_CACHE.clear()
        logger.debug("Bye week cache cleared")
        return

    _BYE_WEEK_CACHE.pop(season, None)
    logger.debug("Bye week cache cleared for %s", season)
