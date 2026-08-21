"""Regression tests for Task 4 review findings."""

import asyncio
import importlib
import multiprocessing
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

def _load_yahoo_auth_module():
    module_path = Path(__file__).resolve().parents[2] / "src" / "agents" / "yahoo_auth.py"
    spec = importlib.util.spec_from_file_location("yahoo_auth_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _persist_tokens_worker(args):
    env_path, index = args
    from src.api.yahoo_credentials import persist_yahoo_tokens

    persist_yahoo_tokens(
        f"access-{index}",
        f"refresh-{index}",
        3600,
        env_path=Path(env_path),
        guid=f"guid-{index}",
    )


def test_settings_accepts_canonical_yahoo_environment_only(tmp_path, monkeypatch):
    from config.settings import Settings

    for key in (
        "YAHOO_CLIENT_ID",
        "YAHOO_CLIENT_SECRET",
        "YAHOO_CONSUMER_KEY",
        "YAHOO_CONSUMER_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("YAHOO_CONSUMER_KEY", "canonical-key")
    monkeypatch.setenv("YAHOO_CONSUMER_SECRET", "canonical-secret")

    settings = Settings(cache_dir=tmp_path / "cache", log_file=tmp_path / "logs" / "app.log")

    assert settings.yahoo_client_id == "canonical-key"
    assert settings.yahoo_client_secret == "canonical-secret"


def test_verify_setup_uses_canonical_names_and_never_prints_token_bytes(tmp_path, capsys, monkeypatch):
    from utils import verify_setup

    sentinel_access = "sentinel-access-token-that-must-not-print"
    sentinel_refresh = "sentinel-refresh-token-that-must-not-print"
    for key in (
        "YAHOO_CLIENT_ID",
        "YAHOO_CLIENT_SECRET",
        "YAHOO_CONSUMER_KEY",
        "YAHOO_CONSUMER_SECRET",
        "YAHOO_ACCESS_TOKEN",
        "YAHOO_REFRESH_TOKEN",
        "YAHOO_GUID",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(verify_setup, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "YAHOO_CONSUMER_KEY=canonical-key\n"
        "YAHOO_CONSUMER_SECRET=canonical-secret\n"
        f"YAHOO_ACCESS_TOKEN={sentinel_access}\n"
        f"YAHOO_REFRESH_TOKEN={sentinel_refresh}\n"
        "YAHOO_GUID=sentinel-guid\n",
        encoding="utf-8",
    )

    assert verify_setup.check_env_file() is True

    output = capsys.readouterr().out
    assert "YAHOO_CONSUMER_KEY" in output
    assert "YAHOO_CONSUMER_SECRET" in output
    assert "YAHOO_CLIENT_ID" not in output
    assert "YAHOO_CLIENT_SECRET" not in output
    assert sentinel_access not in output
    assert sentinel_refresh not in output
    assert "sentinel-guid" not in output


def test_persist_yahoo_tokens_handles_non_newline_file_and_guid_atomically(tmp_path, monkeypatch):
    from src.api import yahoo_credentials

    env_path = tmp_path / ".env"
    env_path.write_text("UNRELATED=value", encoding="utf-8")
    monkeypatch.setattr(yahoo_credentials.time, "time", lambda: 4444)

    yahoo_credentials.persist_yahoo_tokens(
        "access-token",
        "refresh-token",
        3600,
        env_path=env_path,
        guid="guid-value",
    )

    assert env_path.read_text(encoding="utf-8") == (
        "UNRELATED=value\n"
        "YAHOO_ACCESS_TOKEN=access-token\n"
        "YAHOO_REFRESH_TOKEN=refresh-token\n"
        "YAHOO_TOKEN_TIME=4444\n"
        "YAHOO_GUID=guid-value\n"
    )


def test_persist_yahoo_tokens_replace_failure_preserves_original_and_cleans_temp(tmp_path, monkeypatch):
    from src.api import yahoo_credentials

    env_path = tmp_path / ".env"
    original = "UNRELATED=value\nYAHOO_ACCESS_TOKEN=old\n"
    env_path.write_text(original, encoding="utf-8")

    def fail_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(yahoo_credentials.os, "replace", fail_replace)

    with pytest.raises(OSError):
        yahoo_credentials.persist_yahoo_tokens("new", "refresh", 3600, env_path=env_path)

    assert env_path.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".*.env.*")) == []


def test_persist_yahoo_tokens_concurrent_writers_leave_one_complete_yahoo_record(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("UNRELATED=value", encoding="utf-8")
    ctx = multiprocessing.get_context("spawn")
    processes = [ctx.Process(target=_persist_tokens_worker, args=((env_path, i),)) for i in range(4)]

    for process in processes:
        process.start()
    for process in processes:
        process.join(10)

    assert [process.exitcode for process in processes] == [0, 0, 0, 0]
    content = env_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert "UNRELATED=value" in lines
    for key in ("YAHOO_ACCESS_TOKEN", "YAHOO_REFRESH_TOKEN", "YAHOO_TOKEN_TIME", "YAHOO_GUID"):
        matches = [line for line in lines if line.startswith(f"{key}=")]
        assert len(matches) == 1
    assert any(line in {f"YAHOO_GUID=guid-{i}" for i in range(4)} for line in lines)


def test_refresh_utility_has_no_dead_mcp_config_or_env_compatibility_apis():
    from utils import refresh_yahoo_token

    assert not hasattr(refresh_yahoo_token, "update_claude_config")
    assert not hasattr(refresh_yahoo_token, "update_env_file")


def test_setup_module_import_has_no_interactive_side_effects(monkeypatch):
    monkeypatch.setenv("YAHOO_CONSUMER_KEY", "key")
    monkeypatch.setenv("YAHOO_CONSUMER_SECRET", "secret")
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=AssertionError("import prompted")))
    sys.modules.pop("utils.setup_yahoo_auth", None)

    module = importlib.import_module("utils.setup_yahoo_auth")

    assert hasattr(module, "main")


def test_manual_setup_provisioning_failure_returns_false_without_success_message(monkeypatch, capsys):
    module = importlib.import_module("utils.setup_yahoo_auth")
    monkeypatch.setattr("builtins.input", lambda prompt="": "verification-code")
    monkeypatch.setattr(module.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(
        module,
        "exchange_verification_code_for_tokens",
        lambda code, client_id, client_secret: {
            "access_token": "sentinel-access-token",
            "refresh_token": "sentinel-refresh-token",
            "expires_in": 3600,
        },
    )
    monkeypatch.setattr(module, "update_env_file_with_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "preflight_fantasy_access", lambda access_token: False)

    assert module.manual_oauth_flow("client-id", "client-secret") is False

    output = capsys.readouterr().out
    assert "MCP server can now use this token" not in output
    assert "sentinel-access-token" not in output
    assert "sentinel-refresh-token" not in output


def test_reauth_provisioning_failure_returns_false_without_saving_or_success(monkeypatch, capsys):
    from utils import reauth_yahoo

    class Response:
        def __init__(self, status_code, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

    monkeypatch.setattr(reauth_yahoo, "get_yahoo_consumer_credentials", lambda: ("client", "secret"))
    monkeypatch.setattr(reauth_yahoo.webbrowser, "open", lambda url: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "auth-code")
    monkeypatch.setattr(
        reauth_yahoo.requests,
        "post",
        lambda url, data: Response(
            200,
            {
                "access_token": "sentinel-access-token",
                "refresh_token": "sentinel-refresh-token",
                "expires_in": 3600,
            },
        ),
    )
    monkeypatch.setattr(
        reauth_yahoo.requests,
        "get",
        lambda url, headers, timeout=30: Response(
            403,
            text='{"error":{"description":"This application is not authorized to perform this action."}}',
        ),
    )
    save_tokens = MagicMock()
    monkeypatch.setattr(reauth_yahoo, "save_tokens", save_tokens)

    assert reauth_yahoo.reauth_yahoo() is False

    save_tokens.assert_not_called()
    output = capsys.readouterr().out
    assert "Authentication complete" not in output
    assert "sentinel-access-token" not in output
    assert "sentinel-refresh-token" not in output


class _AuthResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _AuthSession:
    def __init__(self, response):
        self.response = response
        self.post_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def post(self, *args, **kwargs):
        self.post_calls += 1
        return self.response


def test_yahoo_auth_persists_only_through_credential_seam_without_json_store(tmp_path, monkeypatch, capsys):
    yahoo_auth = _load_yahoo_auth_module()

    cache_dir = tmp_path / "cache"
    settings = SimpleNamespace(
        yahoo_client_id="client-id",
        yahoo_client_secret="client-secret",
        yahoo_callback_host="localhost",
        yahoo_callback_port=8090,
        cache_dir=cache_dir,
    )
    persist_calls = []
    monkeypatch.setattr(
        yahoo_auth,
        "persist_yahoo_tokens",
        lambda access, refresh, expires, **kwargs: persist_calls.append((access, refresh, expires, kwargs)),
        raising=False,
    )
    auth = yahoo_auth.YahooAuth(settings)
    auth.tokens = yahoo_auth.YahooTokens(
        access_token="sentinel-access-token",
        refresh_token="sentinel-refresh-token",
        expires_at=datetime.now() + timedelta(seconds=3600),
    )

    auth._save_tokens()

    assert persist_calls
    assert not (cache_dir / "yahoo_tokens.json").exists()
    output = capsys.readouterr().out + capsys.readouterr().err
    assert "sentinel-access-token" not in output
    assert "sentinel-refresh-token" not in output


def test_yahoo_auth_refresh_attempts_once_not_three_times(tmp_path, monkeypatch):
    yahoo_auth = _load_yahoo_auth_module()

    settings = SimpleNamespace(
        yahoo_client_id="client-id",
        yahoo_client_secret="client-secret",
        yahoo_callback_host="localhost",
        yahoo_callback_port=8090,
        cache_dir=tmp_path / "cache",
    )
    auth = yahoo_auth.YahooAuth(settings)
    auth.tokens = yahoo_auth.YahooTokens(
        access_token="old-access",
        refresh_token="old-refresh",
        expires_at=datetime.now() - timedelta(seconds=1),
    )
    session = _AuthSession(_AuthResponse(500, {"error_description": "temporary"}))
    monkeypatch.setattr(yahoo_auth.aiohttp, "ClientSession", lambda: session)

    with pytest.raises(yahoo_auth.YahooTokenExpiredError):
        asyncio.run(auth.refresh_tokens())

    assert session.post_calls == 1
