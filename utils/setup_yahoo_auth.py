#!/usr/bin/env python3
"""One-time Yahoo Fantasy Sports OAuth setup."""

import base64
import sys
import webbrowser
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

PROJECT_ROOT = PROJECT_ENV_PATH.parent
ENV_FILE_PATH = PROJECT_ENV_PATH


def preflight_fantasy_access(access_token):
    """Verify the app is provisioned for the Fantasy Sports API."""
    print()
    print("🔎 Preflight: checking Fantasy Sports API provisioning...")
    try:
        response = requests.get(
            "https://fantasysports.yahooapis.com/fantasy/v2/game/nfl?format=json",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=30,
        )
    except requests.exceptions.RequestException:
        print("Preflight request failed to send.")
        print("   Could not determine provisioning status.")
        return False

    if response.status_code == 200:
        print("✅ Fantasy Sports API access confirmed - your app is provisioned.")
        return True
    if is_yahoo_provisioning_failure(response.status_code, response.text):
        print(f"❌ {YAHOO_PROVISIONING_MESSAGE}")
        return False
    print(f"Preflight returned status {response.status_code}")
    return False


def _get_yfpy_game_attr(game, *names):
    """Read a Yahoo game attribute from yfpy objects or dict fixtures."""
    for name in names:
        if isinstance(game, dict) and game.get(name) is not None:
            return game[name]
        value = getattr(game, name, None)
        if value is not None:
            return value
    return None


def discover_yfpy_nfl_game_key(game_metadata):
    """Return Yahoo's opaque current NFL game key from yfpy game metadata."""
    code = _get_yfpy_game_attr(game_metadata, "code", "game_code")
    if code != "nfl":
        raise RuntimeError("Yahoo current game metadata is not for NFL")

    game_key = _get_yfpy_game_attr(game_metadata, "game_key")
    if game_key is None:
        raise RuntimeError("Yahoo NFL game metadata is missing game_key")
    return str(game_key)


def exchange_verification_code_for_tokens(verification_code, client_id, client_secret):
    """Exchange Yahoo OAuth verification code for access and refresh tokens."""
    token_url = "https://api.login.yahoo.com/oauth2/get_token"
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "redirect_uri": "oob",
        "code": verification_code,
    }

    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        print("Error exchanging code for tokens")
        print("   Yahoo returned an error response")
        return None


def update_env_file_with_tokens(access_token, refresh_token, env_file_path, guid=None, expires_in=3600):
    """Persist OAuth tokens and optional GUID through the shared credential seam."""
    persist_yahoo_tokens(
        access_token,
        refresh_token,
        int(expires_in),
        env_path=Path(env_file_path),
        guid=guid,
    )
    print(f"Updated {Path(env_file_path)} with Yahoo token metadata")


def manual_oauth_flow(client_id, client_secret):
    """Handle the manual OAuth flow."""
    print("METHOD 2: Manual OAuth Flow")
    print("-" * 40)
    print()

    auth_url = (
        "https://api.login.yahoo.com/oauth2/request_auth?"
        f"client_id={client_id}&"
        "redirect_uri=oob&"
        "response_type=code&"
        "language=en-us"
    )

    print("Manual authentication steps:")
    print()
    print("1. The browser will open Yahoo's authorization page.")
    print("2. Login to Yahoo and click 'Agree'")
    print("3. Yahoo will show you a verification code")
    print("4. Come back here and paste that code")
    print()

    try:
        if not webbrowser.open(auth_url):
            print("⚠️  Could not open browser automatically; retry from a browser-capable shell.")
            return False
        print("✅ Browser opened automatically")
    except Exception:
        print("⚠️  Could not open browser automatically; retry from a browser-capable shell.")
        return False

    print()
    print("-" * 40)
    verification_code = input("Enter the verification code from Yahoo: ").strip()

    if not verification_code:
        print("❌ No verification code provided. Exiting.")
        return False

    print()
    print("🔄 Exchanging verification code for tokens...")
    token_data = exchange_verification_code_for_tokens(verification_code, client_id, client_secret)

    if not token_data:
        print("❌ Failed to exchange code for tokens.")
        return False

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token or not refresh_token:
        print("⚠️  Could not extract tokens from token_data to update .env")
        return False

    if not preflight_fantasy_access(access_token):
        return False

    update_env_file_with_tokens(
        access_token,
        refresh_token,
        ENV_FILE_PATH,
        expires_in=token_data.get("expires_in", 3600),
    )
    print("   The MCP server can now use this token!")
    print()
    return True


def _run_yfpy_flow(client_id, client_secret):
    print("METHOD 1: Using yfpy Library (Recommended)")
    print("-" * 40)
    try:
        from yfpy import YahooFantasySportsQuery
    except ImportError:
        print("❌ yfpy not installed")
        print("Install with: pip install yfpy")
        print()
        print("Falling back to Method 2...")
        print()
        return manual_oauth_flow(client_id, client_secret)

    print("This will:")
    print("1. Open your browser to Yahoo login")
    print("2. You login and click 'Agree' to authorize")
    print("3. Yahoo will show a verification code")
    print("4. Come back here and paste that code")
    print()
    input("Press Enter to start the authentication process...")
    print()

    try:
        query = YahooFantasySportsQuery(
            league_id="",
            game_code="nfl",
            YAHOO_CLIENT_ID=client_id,
            YAHOO_CLIENT_SECRET=client_secret,
            browser_callback=True,
            env_file_location=ENV_FILE_PATH,
            save_token_data_to_env_file=False,
        )

        print()
        print("Authentication with Yahoo completed; checking Fantasy API access...")
        print()

        current_game = query.get_current_game_metadata()
        nfl_game_key = discover_yfpy_nfl_game_key(current_game)
        print(f"✅ Connected! Current NFL game key: {nfl_game_key}")
        user_leagues = query.get_user_leagues_by_game_key(nfl_game_key)
        if user_leagues:
            print(f"✅ Found {len(user_leagues)} leagues:")
            for i, league in enumerate(user_leagues, 1):
                league_name = getattr(league, "name", "Unknown")
                league_id = getattr(league, "league_id", "Unknown")
                print(f"   {i}. {league_name} (ID: {league_id})")

        if hasattr(query, "oauth") and hasattr(query.oauth, "token_data"):
            token_data = query.oauth.token_data
            access_token = token_data.get("access_token") or token_data.get("yahoo_access_token")
            refresh_token = token_data.get("refresh_token") or token_data.get("yahoo_refresh_token")
            if not access_token or not refresh_token:
                print("⚠️  Could not extract tokens from token_data to update .env")
                print(f"   Token data keys: {list(token_data.keys())}")
                return False
            if not preflight_fantasy_access(access_token):
                return False
            update_env_file_with_tokens(
                access_token,
                refresh_token,
                ENV_FILE_PATH,
                expires_in=token_data.get("expires_in", 3600),
            )
            print("   The MCP server can now use this token!")
            return True
        print("⚠️  Could not access token data from yfpy OAuth object")
        return False
    except Exception:
        print("\nAuthentication failed.")
        print()
        print("Falling back to Method 2...")
        print()
        return manual_oauth_flow(client_id, client_secret)


def main():
    load_project_environment()
    print("=" * 70)
    print("🏈 YAHOO FANTASY API - ONE-TIME AUTHENTICATION SETUP")
    print("=" * 70)
    print()

    try:
        client_id, client_secret = get_yahoo_consumer_credentials()
    except YahooCredentialError as error:
        print("ERROR: Yahoo credentials not found in .env file")
        print(f"Required: {error}")
        return False

    print("Found Yahoo credentials.")
    print()
    success = _run_yfpy_flow(client_id, client_secret)

    print()
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print()
    if success:
        print("Once authenticated:")
        print("1. The token is saved to the project .env file")
        print("2. MCP clients should not store Yahoo token values in their configs")
        print("3. Token will auto-refresh as needed")
        print()
        print("To use with MCP:")
        print("1. Configure your MCP client to run this server from the checkout")
        print("2. The server will load the saved token from the checkout .env")
        print("3. Start making Fantasy Football API calls!")
    else:
        print("Authentication did not complete successfully.")
    print()
    return success


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
