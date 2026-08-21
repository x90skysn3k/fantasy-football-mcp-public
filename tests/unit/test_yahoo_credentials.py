"""Unit tests for checkout-scoped Yahoo credential custody."""

import os
import stat
from pathlib import Path

import pytest

from src.api import yahoo_credentials
from src.api.yahoo_credentials import (
    get_yahoo_consumer_credentials,
    load_project_environment,
    persist_yahoo_tokens,
)


def test_load_project_environment_uses_checkout_env_not_process_cwd(tmp_path, monkeypatch):
    project_env = tmp_path / "project" / ".env"
    cwd_env = tmp_path / "elsewhere" / ".env"
    project_env.parent.mkdir()
    cwd_env.parent.mkdir()
    project_env.write_text(
        "YAHOO_CONSUMER_KEY=checkout-key\n"
        "YAHOO_CONSUMER_SECRET=checkout-secret\n"
        "YAHOO_ACCESS_TOKEN=checkout-token\n",
        encoding="utf-8",
    )
    cwd_env.write_text(
        "YAHOO_CONSUMER_KEY=cwd-key\n"
        "YAHOO_CONSUMER_SECRET=cwd-secret\n"
        "YAHOO_ACCESS_TOKEN=cwd-token\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(cwd_env.parent)
    for key in ("YAHOO_CONSUMER_KEY", "YAHOO_CONSUMER_SECRET", "YAHOO_ACCESS_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(yahoo_credentials, "PROJECT_ENV_PATH", project_env)

    loaded_path = load_project_environment()

    assert loaded_path == project_env
    assert os.environ["YAHOO_CONSUMER_KEY"] == "checkout-key"
    assert os.environ["YAHOO_CONSUMER_SECRET"] == "checkout-secret"
    assert os.environ["YAHOO_ACCESS_TOKEN"] == "checkout-token"


def test_consumer_credentials_require_canonical_names(monkeypatch):
    monkeypatch.setenv("YAHOO_CLIENT_ID", "legacy-id")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "legacy-secret")
    monkeypatch.delenv("YAHOO_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("YAHOO_CONSUMER_SECRET", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        get_yahoo_consumer_credentials()

    message = str(excinfo.value)
    assert "YAHOO_CONSUMER_KEY" in message
    assert "YAHOO_CONSUMER_SECRET" in message
    assert "legacy-id" not in message
    assert "legacy-secret" not in message


def test_persist_yahoo_tokens_is_atomic_mode_0600_and_preserves_unrelated_lines(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# keep this comment\n"
        "UNRELATED=value\n"
        "YAHOO_ACCESS_TOKEN=old-access\n"
        "YAHOO_REFRESH_TOKEN=old-refresh\n"
        "YAHOO_TOKEN_TIME=111\n"
        "YAHOO_GUID=keep-guid\n",
        encoding="utf-8",
    )
    env_path.chmod(0o644)
    monkeypatch.setattr(yahoo_credentials.time, "time", lambda: 2222)
    original_replace = yahoo_credentials.os.replace
    replace_calls = []

    def spy_replace(src, dst):
        replace_calls.append((Path(src), Path(dst)))
        original_replace(src, dst)

    monkeypatch.setattr(yahoo_credentials.os, "replace", spy_replace)

    persist_yahoo_tokens(
        "sentinel-new-access-token",
        "sentinel-new-refresh-token",
        3600,
        env_path=env_path,
    )

    assert len(replace_calls) == 1
    assert replace_calls[0][1] == env_path
    content = env_path.read_text(encoding="utf-8")
    assert "# keep this comment\n" in content
    assert "UNRELATED=value\n" in content
    assert "YAHOO_GUID=keep-guid\n" in content
    assert "YAHOO_ACCESS_TOKEN=sentinel-new-access-token\n" in content
    assert "YAHOO_REFRESH_TOKEN=sentinel-new-refresh-token\n" in content
    assert "YAHOO_TOKEN_TIME=2222\n" in content
    assert "old-access" not in content
    assert "old-refresh" not in content
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


def test_persist_yahoo_tokens_adds_missing_token_fields(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("UNRELATED=value\n", encoding="utf-8")
    monkeypatch.setattr(yahoo_credentials.time, "time", lambda: 3333)

    persist_yahoo_tokens("access-token", "refresh-token", 3600, env_path=env_path)

    assert env_path.read_text(encoding="utf-8") == (
        "UNRELATED=value\n"
        "YAHOO_ACCESS_TOKEN=access-token\n"
        "YAHOO_REFRESH_TOKEN=refresh-token\n"
        "YAHOO_TOKEN_TIME=3333\n"
    )


def test_credential_errors_and_output_do_not_include_token_values(tmp_path, capsys, caplog, monkeypatch):
    sentinel_access = "sentinel-access-token-that-must-not-leak"
    sentinel_refresh = "sentinel-refresh-token-that-must-not-leak"
    monkeypatch.setenv("YAHOO_ACCESS_TOKEN", sentinel_access)
    monkeypatch.setenv("YAHOO_REFRESH_TOKEN", sentinel_refresh)
    monkeypatch.delenv("YAHOO_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("YAHOO_CONSUMER_SECRET", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        get_yahoo_consumer_credentials()

    captured = capsys.readouterr()
    combined = str(excinfo.value) + captured.out + captured.err + caplog.text
    assert sentinel_access not in combined
    assert sentinel_refresh not in combined
