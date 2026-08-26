"""Checkout-scoped Yahoo credential loading and token persistence."""

import os
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv
from filelock import FileLock

PROJECT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_ACCESS_FORM_URL = "https://sports.yahoo.com/developer/access/"
_TOKEN_ENV_KEYS = {
    "YAHOO_ACCESS_TOKEN",
    "YAHOO_REFRESH_TOKEN",
    "YAHOO_TOKEN_TIME",
}
_YAHOO_MUTATION_KEYS = _TOKEN_ENV_KEYS | {"YAHOO_GUID"}
_PROVISIONING_MARKERS = (
    'oauth_problem="additional_authorization_required"',
    "This application is not authorized to perform this action.",
)


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
    guid: Optional[str] = None,
) -> None:
    """Persist Yahoo-owned fields to .env with a locked atomic mode-0600 replacement."""
    if not access_token or not refresh_token:
        raise YahooCredentialError("Yahoo token response did not include required token fields")
    if expires_in <= 0:
        raise YahooCredentialError("Yahoo token response did not include a valid expiry")

    token_time = str(int(time.time()))
    replacements = {
        "YAHOO_ACCESS_TOKEN": access_token,
        "YAHOO_REFRESH_TOKEN": refresh_token,
        "YAHOO_TOKEN_TIME": token_time,
    }
    if guid:
        replacements["YAHOO_GUID"] = guid

    _mutate_yahoo_env(Path(env_path), replacements)

    for key, value in replacements.items():
        os.environ[key] = value


def is_yahoo_provisioning_failure(status: int, text: str) -> bool:
    """Return True for Yahoo Fantasy app-not-provisioned responses."""
    return status in (401, 403) and any(marker in text for marker in _PROVISIONING_MARKERS)


def is_yahoo_token_rejected(status: int, text: str) -> bool:
    """Return True only for Yahoo rejected access-token oauth_problem responses."""
    return status == 401 and (
        'oauth_problem="token_rejected"' in text or "oauth_problem=token_rejected" in text
    )


def _mutate_yahoo_env(env_path: Path, replacements: dict[str, str]) -> None:
    if not replacements:
        return
    unexpected_keys = set(replacements) - _YAHOO_MUTATION_KEYS
    if unexpected_keys:
        raise YahooCredentialError(
            "Unsupported Yahoo credential fields: " + ", ".join(sorted(unexpected_keys))
        )

    env_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = env_path.with_name(f"{env_path.name}.lock")
    with FileLock(str(lock_path), timeout=30):
        existing_lines = _read_env_lines(env_path)
        new_lines, seen = _replace_yahoo_lines(existing_lines, replacements)
        missing_keys = [key for key in replacements if key not in seen]
        if missing_keys:
            _ensure_append_separator(new_lines)
            for key in missing_keys:
                new_lines.append(f"{key}={replacements[key]}\n")
        _atomic_write_env(env_path, new_lines)


def _read_env_lines(env_path: Path) -> list[str]:
    if not env_path.exists():
        return []
    return env_path.read_text(encoding="utf-8").splitlines(keepends=True)


def _replace_yahoo_lines(
    lines: Iterable[str], replacements: dict[str, str]
) -> tuple[list[str], set[str]]:
    new_lines = []
    seen = set()
    for line in lines:
        key = _env_line_key(line)
        if key in replacements:
            new_lines.append(f"{key}={replacements[key]}\n")
            seen.add(key)
        else:
            new_lines.append(line)
    return new_lines, seen


def _ensure_append_separator(lines: list[str]) -> None:
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] = lines[-1] + "\n"


def _atomic_write_env(env_path: Path, lines: list[str]) -> None:
    temp_path = None
    fd = -1
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{env_path.name}.", dir=str(env_path.parent))
        temp_path = Path(temp_name)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.writelines(lines)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, env_path)
        os.chmod(env_path, 0o600)
        _fsync_directory(env_path.parent)
    finally:
        if fd != -1:
            os.close(fd)
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _fsync_directory(path: Path) -> None:
    try:
        dir_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def _env_line_key(line: str) -> Optional[str]:
    stripped = line.lstrip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip()
    if key.startswith("export "):
        key = key[len("export ") :].strip()
    return key or None
