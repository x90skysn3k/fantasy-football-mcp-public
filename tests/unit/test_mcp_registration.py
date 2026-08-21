"""MCP registration contract tests for default-off Reddit support."""

from __future__ import annotations

import builtins
import importlib
import json
import os
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

EXPECTED_DEFAULT_TOOL_NAMES = [
    "ff_get_leagues",
    "ff_get_league_info",
    "ff_get_standings",
    "ff_get_teams",
    "ff_get_roster",
    "ff_get_matchup",
    "ff_get_players",
    "ff_compare_teams",
    "ff_build_lineup",
    "ff_refresh_token",
    "ff_get_draft_results",
    "ff_get_waiver_wire",
    "ff_get_api_status",
    "ff_clear_cache",
    "ff_get_draft_rankings",
    "ff_get_draft_recommendation",
    "ff_analyze_draft_state",
]

EXPECTED_REDDIT_TOOL_NAME = "ff_analyze_reddit_sentiment"

EXPECTED_DEFAULT_SCHEMAS = json.loads(r"""
{
  "ff_analyze_draft_state": {
    "properties": {
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "strategy": {
        "default": "balanced",
        "description": "Draft strategy for analysis: 'conservative', 'aggressive', or 'balanced' (default: balanced)",
        "enum": [
          "conservative",
          "aggressive",
          "balanced"
        ],
        "type": "string"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_build_lineup": {
    "properties": {
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "strategy": {
        "description": "Strategy: 'conservative', 'aggressive', or 'balanced' (default: balanced)",
        "enum": [
          "conservative",
          "aggressive",
          "balanced"
        ],
        "type": "string"
      },
      "use_llm": {
        "description": "Use LLM-based optimization instead of mathematical formulas (default: false)",
        "type": "boolean"
      },
      "week": {
        "description": "Week number (optional, defaults to current week)",
        "type": "integer"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_clear_cache": {
    "properties": {
      "pattern": {
        "description": "Optional pattern to match (e.g., 'standings', 'roster'). Clears all if not provided.",
        "type": "string"
      }
    },
    "type": "object"
  },
  "ff_compare_teams": {
    "properties": {
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "team_key_a": {
        "description": "First team key to compare",
        "type": "string"
      },
      "team_key_b": {
        "description": "Second team key to compare",
        "type": "string"
      }
    },
    "required": [
      "league_key",
      "team_key_a",
      "team_key_b"
    ],
    "type": "object"
  },
  "ff_get_api_status": {
    "properties": {},
    "type": "object"
  },
  "ff_get_draft_rankings": {
    "properties": {
      "count": {
        "default": 50,
        "description": "Number of players to return (default: 50)",
        "type": "integer"
      },
      "league_key": {
        "description": "League key (optional, uses first available league if not provided)",
        "type": "string"
      },
      "position": {
        "default": "all",
        "description": "Position filter (QB, RB, WR, TE, K, DEF, or 'all')",
        "enum": [
          "QB",
          "RB",
          "WR",
          "TE",
          "K",
          "DEF",
          "all"
        ],
        "type": "string"
      }
    },
    "required": [],
    "type": "object"
  },
  "ff_get_draft_recommendation": {
    "properties": {
      "current_pick": {
        "description": "Current overall pick number (optional)",
        "type": "integer"
      },
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "num_recommendations": {
        "default": 10,
        "description": "Number of top recommendations to return (1-20, default: 10)",
        "maximum": 20,
        "minimum": 1,
        "type": "integer"
      },
      "strategy": {
        "default": "balanced",
        "description": "Draft strategy: 'conservative', 'aggressive', or 'balanced' (default: balanced)",
        "enum": [
          "conservative",
          "aggressive",
          "balanced"
        ],
        "type": "string"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_get_draft_results": {
    "properties": {
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "team_key": {
        "description": "Optional team key if not the logged-in team",
        "type": "string"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_get_league_info": {
    "properties": {
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX'). Use ff_get_leagues to get available keys.",
        "type": "string"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_get_leagues": {
    "properties": {},
    "type": "object"
  },
  "ff_get_matchup": {
    "properties": {
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "week": {
        "description": "Week number (optional, defaults to current week)",
        "type": "integer"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_get_players": {
    "properties": {
      "count": {
        "default": 10,
        "description": "Number of players to return",
        "type": "integer"
      },
      "include_analysis": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": false,
        "description": "Include basic analysis and rankings"
      },
      "include_expert_analysis": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": false,
        "description": "Include expert analysis and recommendations"
      },
      "include_external_data": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": true,
        "description": "Include Sleeper data, trending, and matchups"
      },
      "include_projections": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": true,
        "description": "Include projections from Yahoo and Sleeper"
      },
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "position": {
        "description": "Position filter (QB, RB, WR, TE, K, DEF)",
        "type": "string"
      },
      "sort": {
        "default": "rank",
        "description": "Sort by: 'rank', 'points', 'owned', 'trending'",
        "enum": [
          "rank",
          "points",
          "owned",
          "trending"
        ],
        "type": "string"
      },
      "week": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "description": "Week for projections and analysis (optional, defaults to current)"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_get_roster": {
    "properties": {
      "data_level": {
        "default": "standard",
        "description": "Data detail level: 'basic', 'standard', 'enhanced'",
        "enum": [
          "basic",
          "standard",
          "enhanced"
        ],
        "type": "string"
      },
      "include_analysis": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": false,
        "description": "Include basic roster analysis"
      },
      "include_external_data": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": true,
        "description": "Include Sleeper data, trending, and matchups"
      },
      "include_projections": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": true,
        "description": "Include projections from Yahoo and Sleeper"
      },
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "team_key": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "description": "Optional team key if not the logged-in team"
      },
      "week": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "description": "Week for projections and analysis (optional, defaults to current)"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_get_standings": {
    "properties": {
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_get_teams": {
    "properties": {
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_get_waiver_wire": {
    "properties": {
      "count": {
        "default": 30,
        "description": "Number of players to return (default: 30)",
        "type": "integer"
      },
      "include_analysis": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": false,
        "description": "Include basic waiver priority analysis"
      },
      "include_external_data": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": true,
        "description": "Include Sleeper data, trending, and matchups"
      },
      "include_projections": {
        "anyOf": [
          {
            "type": "boolean"
          },
          {
            "type": "null"
          }
        ],
        "default": true,
        "description": "Include projections from Yahoo and Sleeper"
      },
      "league_key": {
        "description": "League key (e.g., 'nfl.l.XXXXXX')",
        "type": "string"
      },
      "position": {
        "description": "Position filter (QB, RB, WR, TE, K, DEF, or 'all')",
        "enum": [
          "QB",
          "RB",
          "WR",
          "TE",
          "K",
          "DEF",
          "all"
        ],
        "type": "string"
      },
      "sort": {
        "default": "rank",
        "description": "Sort by: 'rank', 'points', 'owned', 'trending'",
        "enum": [
          "rank",
          "points",
          "owned",
          "trending"
        ],
        "type": "string"
      },
      "team_key": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "description": "Optional team key for context (e.g., waiver priority)"
      },
      "week": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "description": "Week for projections and analysis (optional, defaults to current)"
      }
    },
    "required": [
      "league_key"
    ],
    "type": "object"
  },
  "ff_refresh_token": {
    "properties": {},
    "type": "object"
  }
}
""")

EXPECTED_REDDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "players": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of player names to analyze (e.g., ['Josh Allen', 'Jared Goff'])",
        },
        "time_window_hours": {
            "type": "integer",
            "description": "How far back to look for Reddit posts (default: 48 hours)",
            "default": 48,
        },
    },
    "required": ["players"],
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


REDDIT_IMPORT_MODULES = ("src.services", "src.services.reddit_service", "praw", "textblob")


def _clear_registration_modules() -> None:
    prefixes = (
        "fantasy_football_multi_league",
        "fastmcp_server",
        "src.handlers",
        "src.services",
    )
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


def _patch_project_env_loader(monkeypatch: pytest.MonkeyPatch, flag_after_load: str | None) -> None:
    import src.api as api

    monkeypatch.delenv("ENABLE_REDDIT_SENTIMENT", raising=False)

    def fake_load_project_environment() -> None:
        if flag_after_load is None:
            os.environ.pop("ENABLE_REDDIT_SENTIMENT", None)
        else:
            os.environ["ENABLE_REDDIT_SENTIMENT"] = flag_after_load

    monkeypatch.setattr(api, "load_project_environment", fake_load_project_environment)


def _import_legacy_server(
    monkeypatch: pytest.MonkeyPatch,
    *,
    flag_after_load: str | None = None,
    block_reddit_imports: bool = False,
):
    _clear_registration_modules()
    _patch_project_env_loader(monkeypatch, flag_after_load)

    if block_reddit_imports:
        real_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
            if name in {"praw", "textblob", "src.services.reddit_service"}:
                raise AssertionError(f"Reddit dependency imported while disabled: {name}")
            if name == "src.services" and "analyze_reddit_sentiment" in (
                fromlist or ()
            ):  # current eager path
                raise AssertionError("Reddit service imported while disabled: src.services")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", guarded_import)

    return importlib.import_module("fantasy_football_multi_league")


def _json_result(blocks: list[Any]) -> dict[str, Any]:
    assert len(blocks) == 1
    return json.loads(blocks[0].text)


@pytest.mark.asyncio
async def test_default_stdio_advertises_exact_yahoo_tools_with_stable_schemas(monkeypatch):
    server_module = _import_legacy_server(monkeypatch)

    tools = await server_module.list_tools()

    assert [tool.name for tool in tools] == EXPECTED_DEFAULT_TOOL_NAMES
    assert {tool.name: tool.inputSchema for tool in tools} == EXPECTED_DEFAULT_SCHEMAS
    assert set(server_module.TOOL_HANDLERS) == set(EXPECTED_DEFAULT_TOOL_NAMES)


@pytest.mark.asyncio
async def test_default_stdio_does_not_import_reddit_service_or_dependencies(monkeypatch):
    server_module = _import_legacy_server(monkeypatch, block_reddit_imports=True)

    tools = await server_module.list_tools()

    assert EXPECTED_REDDIT_TOOL_NAME not in [tool.name for tool in tools]
    assert EXPECTED_REDDIT_TOOL_NAME not in server_module.TOOL_HANDLERS
    assert not any(name in sys.modules for name in REDDIT_IMPORT_MODULES)


@pytest.mark.asyncio
async def test_default_reddit_dispatch_is_unknown(monkeypatch):
    server_module = _import_legacy_server(monkeypatch)

    result = _json_result(
        await server_module.call_tool(
            EXPECTED_REDDIT_TOOL_NAME,
            {"players": ["Josh Allen"], "time_window_hours": 12},
        )
    )

    assert result == {"error": f"Unknown tool: {EXPECTED_REDDIT_TOOL_NAME}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("true_value", ["1", "true", "yes", "on", "TRUE", "Yes", "On"])
async def test_enabled_stdio_adds_only_reddit_after_project_env_loading(monkeypatch, true_value):
    server_module = _import_legacy_server(monkeypatch, flag_after_load=true_value)

    tools = await server_module.list_tools()

    assert [tool.name for tool in tools] == EXPECTED_DEFAULT_TOOL_NAMES + [
        EXPECTED_REDDIT_TOOL_NAME
    ]
    assert {
        tool.name: tool.inputSchema for tool in tools if tool.name != EXPECTED_REDDIT_TOOL_NAME
    } == EXPECTED_DEFAULT_SCHEMAS
    assert (
        next(tool.inputSchema for tool in tools if tool.name == EXPECTED_REDDIT_TOOL_NAME)
        == EXPECTED_REDDIT_SCHEMA
    )
    assert set(server_module.TOOL_HANDLERS) == set(
        EXPECTED_DEFAULT_TOOL_NAMES + [EXPECTED_REDDIT_TOOL_NAME]
    )


@pytest.mark.asyncio
async def test_enabled_reddit_dispatch_reaches_lazy_handler(monkeypatch):
    server_module = _import_legacy_server(monkeypatch, flag_after_load="1")

    reddit_service = types.ModuleType("src.services.reddit_service")

    async def analyze_reddit_sentiment(
        players: list[str], time_window_hours: int
    ) -> dict[str, Any]:
        return {
            "source": "fake-reddit-service",
            "players": players,
            "time_window_hours": time_window_hours,
        }

    reddit_service.analyze_reddit_sentiment = analyze_reddit_sentiment
    monkeypatch.setitem(sys.modules, "src.services.reddit_service", reddit_service)

    result = _json_result(
        await server_module.call_tool(
            EXPECTED_REDDIT_TOOL_NAME,
            {"players": ["Amon-Ra St. Brown"], "time_window_hours": 6},
        )
    )

    assert result == {
        "source": "fake-reddit-service",
        "players": ["Amon-Ra St. Brown"],
        "time_window_hours": 6,
    }


def _install_fastmcp_stub(monkeypatch: pytest.MonkeyPatch) -> type:
    fake_fastmcp = types.ModuleType("fastmcp")

    class Context:
        pass

    class FastMCP:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.tools: dict[str, dict[str, Any]] = {}
            self.prompts: dict[str, Any] = {}
            self.resources: dict[str, Any] = {}

        def tool(self, *, name: str, description: str, meta: dict[str, str]):
            def decorator(func):
                self.tools[name] = {"description": description, "meta": meta, "func": func}
                return func

            return decorator

        def prompt(self, func=None, **kwargs):
            def decorator(inner):
                self.prompts[inner.__name__] = inner
                return inner

            return decorator(func) if callable(func) else decorator

        def resource(self, uri: str):
            def decorator(func):
                self.resources[uri] = func
                return func

            return decorator

    fake_fastmcp.Context = Context
    fake_fastmcp.FastMCP = FastMCP
    monkeypatch.setitem(sys.modules, "fastmcp", fake_fastmcp)
    return FastMCP


def test_installed_console_entrypoint_invokes_canonical_gated_stdio_without_reddit(tmp_path):
    install_target = tmp_path / "site"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(install_target),
            str(PROJECT_ROOT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    probe = f"""
import builtins
import importlib.metadata
import os
import sys

install_target = {str(install_target)!r}
sys.path.insert(0, install_target)
os.environ.pop("ENABLE_REDDIT_SENTIMENT", None)

real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "src.mcp_server":
        raise AssertionError("console entrypoint imported noncanonical src.mcp_server")
    if name in {{"praw", "textblob", "src.services.reddit_service"}}:
        raise AssertionError(f"Reddit dependency imported while disabled: {{name}}")
    if name == "src.services" and "analyze_reddit_sentiment" in (fromlist or ()):
        raise AssertionError("Reddit service imported while disabled: src.services")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import

distributions = [
    distribution
    for distribution in importlib.metadata.distributions(path=[install_target])
    if distribution.metadata["Name"] == "fantasy-football-mcp"
]
assert len(distributions) == 1
entrypoints = [
    entrypoint
    for entrypoint in distributions[0].entry_points
    if entrypoint.group == "console_scripts" and entrypoint.name == "fantasy-football-mcp"
]
assert len(entrypoints) == 1
assert entrypoints[0].value == "fantasy_football_multi_league:cli_main"

cli_main = entrypoints[0].load()
module = sys.modules["fantasy_football_multi_league"]
assert module.__file__.startswith(install_target)
assert sys.modules["src.api"].__file__.startswith(install_target)
calls = []

async def fake_main():
    calls.append("canonical-main")

module.main = fake_main

assert cli_main is module.cli_main
assert cli_main() is None
assert calls == ["canonical-main"]
assert "src.mcp_server" not in sys.modules
assert not any(
    name in sys.modules
    for name in ("src.services", "src.services.reddit_service", "praw", "textblob")
)
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_fastmcp_default_registration_uses_same_default_off_tool_set(monkeypatch):
    _clear_registration_modules()
    _patch_project_env_loader(monkeypatch, None)
    _install_fastmcp_stub(monkeypatch)

    fastmcp_server = importlib.import_module("fastmcp_server")

    assert set(fastmcp_server.server.tools) == set(EXPECTED_DEFAULT_TOOL_NAMES)
    assert EXPECTED_REDDIT_TOOL_NAME not in fastmcp_server.server.tools
    matchup_tool = fastmcp_server.server.tools["ff_get_matchup"]
    assert "Returns the raw Yahoo matchup payload" in matchup_tool["description"]
    assert "raw Yahoo matchup payload" in matchup_tool["meta"]["prompt"]
    assert "opponent" not in matchup_tool["meta"]["prompt"].lower()
    assert "projection" not in matchup_tool["meta"]["prompt"].lower()


def test_fastmcp_enabled_registration_adds_only_reddit(monkeypatch):
    _clear_registration_modules()
    _patch_project_env_loader(monkeypatch, "yes")
    _install_fastmcp_stub(monkeypatch)

    fastmcp_server = importlib.import_module("fastmcp_server")

    assert set(fastmcp_server.server.tools) == set(
        EXPECTED_DEFAULT_TOOL_NAMES + [EXPECTED_REDDIT_TOOL_NAME]
    )
