"""Fantasy season resolution helpers."""

import os
from typing import Any, Mapping, Optional

DEFAULT_FANTASY_SEASON = 2026
MIN_SUPPORTED_SEASON = 2020
MAX_SUPPORTED_SEASON = 2100


def _normalize_season(value: object, *, source: str) -> int:
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError(f"{source} must be a four-digit season")

    season_text = str(value)
    season = int(season_text)
    if len(season_text) != 4 or not MIN_SUPPORTED_SEASON <= season <= MAX_SUPPORTED_SEASON:
        raise ValueError(f"{source} must be a supported four-digit season")

    return season


def resolve_fantasy_season(
    yahoo_game_metadata: Optional[Mapping[str, Any]] = None,
) -> int:
    """Resolve the fantasy football season using explicit config before Yahoo metadata."""
    if "FANTASY_SEASON" in os.environ:
        return _normalize_season(os.environ["FANTASY_SEASON"], source="FANTASY_SEASON")

    if yahoo_game_metadata and yahoo_game_metadata.get("season") is not None:
        return _normalize_season(yahoo_game_metadata["season"], source="Yahoo season")

    return DEFAULT_FANTASY_SEASON
