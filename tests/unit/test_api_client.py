"""Unit tests for src/api/yahoo_client.py - Yahoo API client functionality."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.yahoo_client import (
    YahooProvisioningError,
    get_access_token,
    refresh_yahoo_token,
    set_access_token,
    yahoo_api_call,
)


class MockResponse:
    def __init__(self, status, *, payload=None, text=""):
        self.status = status
        self._payload = payload or {}
        self._text = text

    async def json(self):
        return self._payload

    async def text(self):
        return self._text


class MockRequestContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *args):
        return None


class MockSession:
    def __init__(self, *, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.get_calls = []
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return MockRequestContext(self.get_responses.pop(0))

    def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        return MockRequestContext(self.post_responses.pop(0))


class TestTokenManagement:
    """Test token get/set operations."""

    def test_get_access_token_from_env(self, mock_env_vars):
        """Test getting access token from environment."""
        from src.api import yahoo_client

        yahoo_client._YAHOO_ACCESS_TOKEN = None
        token = get_access_token()
        assert token == "test_access_token_12345"

    def test_set_access_token(self, mock_env_vars):
        """Test setting new access token."""
        new_token = "new_test_token_99999"
        set_access_token(new_token)
        assert get_access_token() == new_token
        assert os.environ["YAHOO_ACCESS_TOKEN"] == new_token

    def test_get_access_token_when_none(self, monkeypatch):
        """Test getting access token when not set returns empty string."""
        monkeypatch.delenv("YAHOO_ACCESS_TOKEN", raising=False)
        from src.api import yahoo_client

        yahoo_client._YAHOO_ACCESS_TOKEN = None
        token = get_access_token()
        assert token == ""


class TestYahooApiCall:
    """Test Yahoo API call functionality."""

    @pytest.mark.asyncio
    async def test_yahoo_api_call_success(
        self, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """Test successful Yahoo API call."""
        session = MockSession(get_responses=[MockResponse(200, payload={"test": "data"})])

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            result = await yahoo_api_call("test/endpoint")

        assert result == {"test": "data"}
        mock_rate_limiter.acquire.assert_called_once()
        mock_response_cache.set.assert_called_once_with("test/endpoint", {"test": "data"})

    @pytest.mark.asyncio
    async def test_yahoo_api_call_uses_cache(
        self, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """Test that cached responses are returned without API call."""
        cached_data = {"cached": "response"}
        mock_response_cache.get = AsyncMock(return_value=cached_data)

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
        ):
            result = await yahoo_api_call("test/endpoint")

        assert result == cached_data
        mock_response_cache.get.assert_called_once_with("test/endpoint")
        mock_rate_limiter.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_yahoo_api_call_401_token_rejected_refreshes_once_and_retries_once(
        self, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """401 token_rejected refreshes exactly once before retrying the API call."""
        session = MockSession(
            get_responses=[
                MockResponse(401, text='oauth_problem="token_rejected"'),
                MockResponse(200, payload={"success": "data"}),
            ]
        )
        refresh = AsyncMock(return_value={"status": "success"})

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
            patch("src.api.yahoo_client.refresh_yahoo_token", refresh),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            result = await yahoo_api_call("test/endpoint")

        assert result == {"success": "data"}
        assert len(session.get_calls) == 2
        refresh.assert_awaited_once()

    @pytest.mark.parametrize(
        "status, body",
        [
            (401, 'oauth_problem="additional_authorization_required"'),
            (403, '{"error":{"description":"This application is not authorized to perform this action."}}'),
        ],
    )
    @pytest.mark.asyncio
    async def test_provisioning_failure_never_refreshes(
        self, status, body, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """Provisioning failures explain the Yahoo access form and never refresh tokens."""
        session = MockSession(get_responses=[MockResponse(status, text=body)])
        refresh = AsyncMock(return_value={"status": "success"})

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
            patch("src.api.yahoo_client.refresh_yahoo_token", refresh),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            with pytest.raises(YahooProvisioningError) as excinfo:
                await yahoo_api_call("test/endpoint")

        message = str(excinfo.value)
        assert "https://sports.yahoo.com/developer/access/" in message
        assert "refresh" in message.lower()
        refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failed_refresh_requires_reauthorization_without_leaking_tokens(
        self, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """A rejected access token with failed refresh tells the user to reauthorize safely."""
        sentinel = "sentinel-refresh-secret-must-not-leak"
        session = MockSession(get_responses=[MockResponse(401, text='oauth_problem="token_rejected"')])
        refresh = AsyncMock(
            return_value={
                "status": "error",
                "message": "Yahoo refresh token was rejected; reauthorize Yahoo.",
                "details": sentinel,
            }
        )

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
            patch("src.api.yahoo_client.refresh_yahoo_token", refresh),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            with pytest.raises(Exception) as excinfo:
                await yahoo_api_call("test/endpoint")

        message = str(excinfo.value)
        assert "reauthorize" in message.lower()
        assert sentinel not in message
        refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_second_401_after_refresh_does_not_loop(
        self, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """A second 401 after a successful refresh does not recursively refresh forever."""
        session = MockSession(
            get_responses=[
                MockResponse(401, text='oauth_problem="token_rejected"'),
                MockResponse(401, text='oauth_problem="token_rejected"'),
            ]
        )
        refresh = AsyncMock(return_value={"status": "success"})

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
            patch("src.api.yahoo_client.refresh_yahoo_token", refresh),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            with pytest.raises(Exception, match="after token refresh"):
                await yahoo_api_call("test/endpoint")

        assert len(session.get_calls) == 2
        refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_401_does_not_refresh(
        self, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """Only oauth_problem=token_rejected triggers refresh; arbitrary 401s do not."""
        session = MockSession(get_responses=[MockResponse(401, text='oauth_problem="invalid_scope"')])
        refresh = AsyncMock(return_value={"status": "success"})

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
            patch("src.api.yahoo_client.refresh_yahoo_token", refresh),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            with pytest.raises(Exception, match="Yahoo API error 401"):
                await yahoo_api_call("test/endpoint")

        refresh.assert_not_awaited()

    @pytest.mark.parametrize("status", [429, 500, 503])
    @pytest.mark.asyncio
    async def test_operational_errors_do_not_refresh(
        self, status, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """429 and 5xx responses keep the existing operational-error semantics."""
        session = MockSession(get_responses=[MockResponse(status, text="temporary failure")])
        refresh = AsyncMock(return_value={"status": "success"})

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
            patch("src.api.yahoo_client.refresh_yahoo_token", refresh),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            with pytest.raises(Exception, match=f"Yahoo API error {status}"):
                await yahoo_api_call("test/endpoint")

        refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_yahoo_api_call_cache_disabled(
        self, mock_env_vars, mock_rate_limiter, mock_response_cache
    ):
        """Test API call with caching disabled."""
        session = MockSession(get_responses=[MockResponse(200, payload={"test": "data"})])

        with (
            patch("src.api.yahoo_client.rate_limiter", mock_rate_limiter),
            patch("src.api.yahoo_client.response_cache", mock_response_cache),
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            result = await yahoo_api_call("test/endpoint", use_cache=False)

        assert result == {"test": "data"}
        mock_response_cache.get.assert_not_called()
        mock_response_cache.set.assert_not_called()


class TestRefreshYahooToken:
    """Test Yahoo OAuth token refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_token_success_persists_tokens_atomically(self, mock_env_vars):
        """Test successful token refresh persists new tokens through the credential seam."""
        session = MockSession(
            post_responses=[
                MockResponse(
                    200,
                    payload={
                        "access_token": "new_access_token",
                        "refresh_token": "new_refresh_token",
                        "expires_in": 3600,
                    },
                )
            ]
        )

        with (
            patch("src.api.yahoo_client.persist_yahoo_tokens") as persist_tokens,
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            result = await refresh_yahoo_token()

        assert result["status"] == "success"
        assert result["expires_in"] == 3600
        assert result["expires_in_hours"] == 1.0
        assert get_access_token() == "new_access_token"
        assert os.environ["YAHOO_REFRESH_TOKEN"] == "new_refresh_token"
        persist_tokens.assert_called_once_with("new_access_token", "new_refresh_token", 3600)

    @pytest.mark.asyncio
    async def test_refresh_token_missing_canonical_credentials(self, monkeypatch):
        """Refresh requires canonical Yahoo consumer environment variables."""
        monkeypatch.delenv("YAHOO_CONSUMER_KEY", raising=False)
        monkeypatch.delenv("YAHOO_CONSUMER_SECRET", raising=False)
        monkeypatch.setenv("YAHOO_CLIENT_ID", "legacy-id")
        monkeypatch.setenv("YAHOO_CLIENT_SECRET", "legacy-secret")
        monkeypatch.setenv("YAHOO_REFRESH_TOKEN", "refresh-token")

        result = await refresh_yahoo_token()

        assert result["status"] == "error"
        assert "YAHOO_CONSUMER_KEY" in result["message"]
        assert "YAHOO_CONSUMER_SECRET" in result["message"]
        assert "legacy-id" not in result["message"]
        assert "legacy-secret" not in result["message"]

    @pytest.mark.asyncio
    async def test_refresh_token_rejection_requires_reauthorization_without_secret_output(
        self, mock_env_vars
    ):
        """Refresh-token rejection reports reauthorization without echoing Yahoo response bodies."""
        sentinel = "sentinel-refresh-token-value"
        session = MockSession(post_responses=[MockResponse(400, text=f"invalid {sentinel}")])

        with (
            patch("aiohttp.TCPConnector"),
            patch("aiohttp.ClientSession", return_value=session),
        ):
            result = await refresh_yahoo_token()

        assert result["status"] == "error"
        assert "reauthorize" in result["message"].lower()
        assert sentinel not in str(result)

    @pytest.mark.asyncio
    async def test_refresh_token_network_error_is_secret_safe(self, mock_env_vars):
        """Network exceptions are classified without stringifying potentially sensitive context."""
        with patch("aiohttp.ClientSession", side_effect=Exception("sentinel-secret-in-exception")):
            result = await refresh_yahoo_token()

        assert result["status"] == "error"
        assert "Error refreshing token" in result["message"]
        assert "sentinel-secret-in-exception" not in str(result)
