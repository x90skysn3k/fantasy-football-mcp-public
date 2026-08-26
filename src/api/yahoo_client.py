"""Yahoo Fantasy Sports API client with rate limiting and token refresh."""

import os
import socket
from typing import Dict

import aiohttp

from src.api.yahoo_credentials import (
    YAHOO_PROVISIONING_MESSAGE,
    YahooCredentialError,
    YahooProvisioningError,
    get_yahoo_consumer_credentials,
    is_yahoo_provisioning_failure,
    is_yahoo_token_rejected,
    load_project_environment,
    persist_yahoo_tokens,
)
from src.api.yahoo_utils import rate_limiter, response_cache

load_project_environment()

# Module-level token cache
_YAHOO_ACCESS_TOKEN = os.getenv("YAHOO_ACCESS_TOKEN")
YAHOO_API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"


def get_access_token() -> str:
    """Get the current access token."""
    global _YAHOO_ACCESS_TOKEN
    if _YAHOO_ACCESS_TOKEN is None:
        _YAHOO_ACCESS_TOKEN = os.getenv("YAHOO_ACCESS_TOKEN")
    return _YAHOO_ACCESS_TOKEN or ""


def set_access_token(token: str) -> None:
    """Update the access token (used after refresh)."""
    global _YAHOO_ACCESS_TOKEN
    _YAHOO_ACCESS_TOKEN = token
    os.environ["YAHOO_ACCESS_TOKEN"] = token


async def yahoo_api_call(
    endpoint: str, retry_on_auth_fail: bool = True, use_cache: bool = True
) -> Dict:
    """Make Yahoo API request with rate limiting, caching, and automatic token refresh.

    Args:
        endpoint: Yahoo API endpoint (e.g., "users;use_login=1/games")
        retry_on_auth_fail: If True, will attempt token refresh on 401 errors
        use_cache: If True, will check cache before making API call

    Returns:
        dict: JSON response from Yahoo API

    Raises:
        Exception: On API errors or authentication failures
    """
    # Check cache first (if enabled)
    if use_cache:
        cached_response = await response_cache.get(endpoint)
        if cached_response is not None:
            return cached_response

    # Apply rate limiting
    await rate_limiter.acquire()

    access_token = get_access_token()
    url = f"{YAHOO_API_BASE}/{endpoint}?format=json"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                # Cache successful response
                if use_cache:
                    await response_cache.set(endpoint, data)
                return data
            elif response.status == 401:
                text = await response.text()
                if _is_provisioning_failure(response.status, text):
                    raise YahooProvisioningError(YAHOO_PROVISIONING_MESSAGE)
                if retry_on_auth_fail and _is_token_rejected(response.status, text):
                    refresh_result = await refresh_yahoo_token()
                    if refresh_result.get("status") == "success":
                        return await yahoo_api_call(
                            endpoint, retry_on_auth_fail=False, use_cache=use_cache
                        )
                    raise Exception(
                        "Yahoo API auth failed; refresh token was rejected. "
                        "Reauthorize Yahoo with utils/setup_yahoo_auth.py."
                    )
                if retry_on_auth_fail:
                    raise Exception(
                        f"Yahoo API error {response.status}: {_safe_response_excerpt(text)}"
                    )
                raise Exception("Yahoo API error 401 after token refresh")
            elif response.status == 403:
                text = await response.text()
                if _is_provisioning_failure(response.status, text):
                    raise YahooProvisioningError(YAHOO_PROVISIONING_MESSAGE)
                raise Exception(
                    f"Yahoo API error {response.status}: {_safe_response_excerpt(text)}"
                )
            else:
                text = await response.text()
                raise Exception(
                    f"Yahoo API error {response.status}: {_safe_response_excerpt(text)}"
                )


async def refresh_yahoo_token() -> Dict:
    """Refresh the Yahoo access token using the refresh token.

    Returns:
        dict: Status message with refresh result
            - {"status": "success", "message": "...", "expires_in": 3600}
            - {"status": "error", "message": "...", "details": "..."}
    """
    try:
        client_id, client_secret = get_yahoo_consumer_credentials()
    except YahooCredentialError as error:
        return {"status": "error", "message": str(error)}
    refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")

    if not refresh_token:
        return {"status": "error", "message": "Missing Yahoo refresh token in environment"}

    token_url = "https://api.login.yahoo.com/oauth2/get_token"

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
            async with session.post(token_url, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    new_access_token = token_data.get("access_token")
                    new_refresh_token = token_data.get("refresh_token", refresh_token)
                    expires_in = int(token_data.get("expires_in", 3600))

                    persist_yahoo_tokens(new_access_token, new_refresh_token, expires_in)
                    set_access_token(new_access_token)
                    os.environ["YAHOO_REFRESH_TOKEN"] = new_refresh_token

                    return {
                        "status": "success",
                        "message": "Token refreshed successfully",
                        "expires_in": expires_in,
                        "expires_in_hours": round(expires_in / 3600, 1),
                    }
                return {
                    "status": "error",
                    "message": (
                        f"Failed to refresh token: {response.status}. "
                        "Reauthorize Yahoo with utils/setup_yahoo_auth.py."
                    ),
                }
    except YahooCredentialError as error:
        return {"status": "error", "message": str(error)}
    except Exception:
        return {
            "status": "error",
            "message": "Error refreshing token. Reauthorize Yahoo if this persists.",
        }


def _is_provisioning_failure(status: int, text: str) -> bool:
    return is_yahoo_provisioning_failure(status, text)


def _is_token_rejected(status: int, text: str) -> bool:
    return is_yahoo_token_rejected(status, text)


def _safe_response_excerpt(text: str) -> str:
    if not text:
        return ""
    return "response body omitted"
