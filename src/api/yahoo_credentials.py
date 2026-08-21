"""Checkout-scoped Yahoo credential loading and token persistence."""

import os
import tempfile
import time
from pathlib import Path
from typing import Iterable, Optional, Tuple

from dotenv import load_dotenv

PROJECT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_ACCESS_FORM_URL = "https://sports.yahoo.com/developer/access/"
_TOKEN_ENV_KEYS = {
    "YAHOO_ACCESS_TOKEN",
    "YAHOO_REFRESH_TOKEN",
    "YAHOO_TOKEN_TIME",
}


class YahooProvisioningError(Exception):
    """Raised when a Yahoo app is not provisioned for Fantasy Sports API access."""


class YahooCredentialError(RuntimeError):
    """Raised when required Yahoo credentials are missing."""


YAHOO_PROVISIONING_MESSAGE = (
    "Your Yahoo app is authenticated but not provisioned for the Fantasy Sports API. "
    "Refreshing tokens will not help. Apply for Fantasy Sports API access at "
    f"{_ACCESS_FORM_URL} and include your existing Yahoo app/consumer key."
)


def load_project_environment() -> Path:
    """Load the repository-root .env file regardless of the process working directory."""
    load_dotenv(dotenv_path=PROJECT_ENV_PATH, override=True)
    return PROJECT_ENV_PATH


def get_yahoo_consumer_credentials() -> Tuple[str, str]:
    """Return canonical Yahoo OAuth consumer credentials from the environment."""
    consumer_key = os.getenv("YAHOO_CONSUMER_KEY")
    consumer_secret = os.getenv("YAHOO_CONSUMER_SECRET")
    missing = [
        name
        for name, value in (
            ("YAHOO_CONSUMER_KEY", consumer_key),
            ("YAHOO_CONSUMER_SECRET", consumer_secret),
        )
        if not value
    ]
    if missing:
        raise YahooCredentialError(
            "Missing Yahoo OAuth credentials in environment: " + ", ".join(missing)
        )
    return consumer_key or "", consumer_secret or ""


def persist_yahoo_tokens(
    access_token: str,
    refresh_token: str,
    expires_in: int,
    *,
    env_path: Path = PROJECT_ENV_PATH,
) -> None:
    """Atomically persist Yahoo token fields to .env with mode 0600."""
    if not access_token or not refresh_token:
        raise YahooCredentialError("Yahoo token response did not include required token fields")
    if expires_in <= 0:
        raise YahooCredentialError("Yahoo token response did not include a valid expiry")

    env_path = Path(env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    token_time = str(int(time.time()))
    replacements = {
        "YAHOO_ACCESS_TOKEN": access_token,
        "YAHOO_REFRESH_TOKEN": refresh_token,
        "YAHOO_TOKEN_TIME": token_time,
    }

    existing_lines = _read_env_lines(env_path)
    new_lines, seen = _replace_token_lines(existing_lines, replacements)
    for key in ("YAHOO_ACCESS_TOKEN", "YAHOO_REFRESH_TOKEN", "YAHOO_TOKEN_TIME"):
        if key not in seen:
            new_lines.append(f"{key}={replacements[key]}\n")

    temp_path = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{env_path.name}.", dir=str(env_path.parent))
        temp_path = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.writelines(new_lines)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, env_path)
        os.chmod(env_path, 0o600)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    os.environ["YAHOO_ACCESS_TOKEN"] = access_token
    os.environ["YAHOO_REFRESH_TOKEN"] = refresh_token
    os.environ["YAHOO_TOKEN_TIME"] = token_time


def _read_env_lines(env_path: Path) -> list[str]:
    if not env_path.exists():
        return []
    return env_path.read_text(encoding="utf-8").splitlines(keepends=True)


def _replace_token_lines(
    lines: Iterable[str], replacements: dict[str, str]
) -> tuple[list[str], set[str]]:
    new_lines = []
    seen = set()
    for line in lines:
        key = _env_line_key(line)
        if key in _TOKEN_ENV_KEYS:
            new_lines.append(f"{key}={replacements[key]}\n")
            seen.add(key)
        else:
            new_lines.append(line)
    return new_lines, seen


def _env_line_key(line: str) -> Optional[str]:
    stripped = line.lstrip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip()
    if key.startswith("export "):
        key = key[len("export ") :].strip()
    return key or None
