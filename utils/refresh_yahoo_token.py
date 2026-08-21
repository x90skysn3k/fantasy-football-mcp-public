#!/usr/bin/env python3
"""
Refresh Yahoo Fantasy Sports OAuth2 Token.
"""

import os
from pathlib import Path

import requests

from src.api.yahoo_credentials import (
    PROJECT_ENV_PATH,
    YAHOO_PROVISIONING_MESSAGE,
    YahooCredentialError,
    get_yahoo_consumer_credentials,
    is_yahoo_provisioning_failure,
    load_project_environment,
    persist_yahoo_tokens,
)

ENV_FILE_PATH = PROJECT_ENV_PATH
load_project_environment()


def refresh_yahoo_token():
    """Refresh the Yahoo access token using canonical credentials and the token seam."""
    try:
        client_id, client_secret = get_yahoo_consumer_credentials()
    except YahooCredentialError as error:
        print(f"Missing credentials in .env file: {error}")
        return False

    refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")
    if not refresh_token:
        print("Missing YAHOO_REFRESH_TOKEN in .env file")
        return False

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    print("Refreshing Yahoo token...")
    try:
        response = requests.post("https://api.login.yahoo.com/oauth2/get_token", data=data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token", refresh_token)
            expires_in = int(token_data.get("expires_in", 3600))
            persist_yahoo_tokens(access_token, new_refresh_token, expires_in, env_path=ENV_FILE_PATH)
            print("Token refreshed successfully and saved to the project .env file.")
            return True

        print(f"Failed to refresh token: {response.status_code}")
        if response.status_code in (400, 401):
            print("Refresh token was rejected. Reauthorize with: python utils/setup_yahoo_auth.py")
        return False
    except Exception:
        print("Error refreshing token. Reauthorize if this persists.")
        return False




def test_new_token():
    """Test if the new token works without printing token values."""
    load_project_environment()
    access_token = os.getenv("YAHOO_ACCESS_TOKEN")
    if not access_token:
        print("No access token found")
        return False

    url = "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1?format=json"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("Token test successful! API is accessible.")
            return True
        if is_yahoo_provisioning_failure(response.status_code, response.text):
            print(YAHOO_PROVISIONING_MESSAGE)
            return False
        print(f"Token test failed: {response.status_code}")
        return False
    except Exception:
        print("Token test error")
        return False


def _print_failure_troubleshooting():
    print("\n" + "=" * 60)
    print("Token refresh failed")
    print("=" * 60)
    print("\nTroubleshooting:")
    print("1. Check your internet connection")
    print("2. Verify YAHOO_CONSUMER_KEY/YAHOO_CONSUMER_SECRET in .env")
    print("3. If refresh token is expired, run: python utils/setup_yahoo_auth.py")
    print("4. Check Yahoo Developer App provisioning")


def main():
    print("=" * 60)
    print("Yahoo Fantasy Sports Token Refresh")
    print("=" * 60)
    print()

    if not refresh_yahoo_token():
        _print_failure_troubleshooting()
        return 1

    print("\nTesting new token...")
    if not test_new_token():
        print("\n" + "=" * 60)
        print("Token verification failed")
        print("=" * 60)
        return 1

    print("\n" + "=" * 60)
    print("Token refresh complete!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
