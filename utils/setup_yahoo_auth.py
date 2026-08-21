#!/usr/bin/env python3
"""
One-time Yahoo Fantasy API Authentication Setup
Run this script once to authenticate and save your token.
"""

import os
import sys
import webbrowser
import base64
import requests
from pathlib import Path

from src.api.yahoo_credentials import (
    PROJECT_ENV_PATH,
    YahooCredentialError,
    get_yahoo_consumer_credentials,
    load_project_environment,
    persist_yahoo_tokens,
)

PROJECT_ROOT = PROJECT_ENV_PATH.parent
ENV_FILE_PATH = PROJECT_ENV_PATH
load_project_environment()

print("=" * 70)
print("🏈 YAHOO FANTASY API - ONE-TIME AUTHENTICATION SETUP")
print("=" * 70)
print()

try:
    CLIENT_ID, CLIENT_SECRET = get_yahoo_consumer_credentials()
except YahooCredentialError as error:
    print("ERROR: Yahoo credentials not found in .env file")
    print(f"Required: {error}")
    sys.exit(1)

print("Found Yahoo credentials.")
print()

def preflight_fantasy_access(access_token):
    """Verify the app is actually provisioned for the Fantasy Sports API.

    A successful token exchange does NOT mean Fantasy API access: Yahoo no
    longer self-serve provisions the Fantasy Sports API, so an app can hold
    perfectly valid tokens that every fantasysports.yahooapis.com call rejects
    with oauth_problem="additional_authorization_required". Catch that here,
    at setup time, instead of letting the first real tool call fail later.
    """
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
    if (response.status_code == 401 and "additional_authorization_required" in response.text) or (
        response.status_code == 403
        and "This application is not authorized to perform this action." in response.text
    ):
        print("❌ Your tokens are VALID, but your Yahoo app is NOT provisioned for")
        print("   the Fantasy Sports API. This is not a token problem - re-running")
        print("   this setup, refreshing tokens, or recreating the app will not fix it.")
        print()
        print("   Apply for access at: https://sports.yahoo.com/developer/access/")
        print("   Include your existing Client ID so approval attaches to this app.")
        print("   Approval is a manual review with no published turnaround time;")
        print("   every Fantasy API call will keep returning authorization failures until it lands.")
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
    
    # Create Basic Auth header
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "redirect_uri": "oob",
        "code": verification_code
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        return token_data
    except requests.exceptions.RequestException as e:
        print("Error exchanging code for tokens")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print("   Yahoo returned an error response")
            except:
                print("   Yahoo returned an error response")
        return None

def update_env_file_with_tokens(access_token, refresh_token, env_file_path, guid=None, expires_in=3600):
    """Persist OAuth tokens through the shared credential seam."""
    persist_yahoo_tokens(access_token, refresh_token, int(expires_in), env_path=Path(env_file_path))
    if guid:
        _persist_guid(guid)
    print(f"Updated {Path(env_file_path)} with Yahoo token metadata")


def _persist_guid(guid):
    lines = []
    if ENV_FILE_PATH.exists():
        lines = ENV_FILE_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("YAHOO_GUID="):
            new_lines.append(f"YAHOO_GUID={guid}\n")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"YAHOO_GUID={guid}\n")
    ENV_FILE_PATH.write_text("".join(new_lines), encoding="utf-8")
    ENV_FILE_PATH.chmod(0o600)

def manual_oauth_flow(client_id, client_secret):
    """Handle the manual OAuth flow (Method 2)."""
    print("METHOD 2: Manual OAuth Flow")
    print("-" * 40)
    print()
    
    # Build authorization URL
    auth_url = (
        "https://api.login.yahoo.com/oauth2/request_auth?"
        f"client_id={client_id}&"
        "redirect_uri=oob&"
        "response_type=code&"
        "language=en-us"
    )
    
    print("Manual authentication steps:")
    print()
    print("1. Copy this URL and open it in your browser:")
    print()
    print(auth_url)
    print()
    print("2. Login to Yahoo and click 'Agree'")
    print("3. Yahoo will show you a verification code")
    print("4. Come back here and paste that code")
    print()
    
    # Try to open browser automatically
    try:
        webbrowser.open(auth_url)
        print("✅ Browser opened automatically")
    except:
        print("⚠️  Could not open browser automatically")
        print("   Please copy the URL above and open it manually")
    
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
    
    # Update .env file with tokens
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    if access_token and refresh_token:
        update_env_file_with_tokens(
            access_token,
            refresh_token,
            ENV_FILE_PATH,
            expires_in=token_data.get("expires_in", 3600),
        )
    else:
        print("⚠️  Could not extract tokens from token_data to update .env")
    
    print("   The MCP server can now use this token!")
    print()

    # Verify the app can actually reach the Fantasy API (provisioning check)
    preflight_fantasy_access(token_data.get('access_token'))

    return True

# Method 1: Using yfpy (Recommended)
print("METHOD 1: Using yfpy Library (Recommended)")
print("-" * 40)

try:
    from yfpy import YahooFantasySportsQuery
    
    print("This will:")
    print("1. Open your browser to Yahoo login")
    print("2. You login and click 'Agree' to authorize")
    print("3. Yahoo will show a verification code")
    print("4. Come back here and paste that code")
    print()
    
    input("Press Enter to start the authentication process...")
    print()
    
    # Create token directory
    token_dir = Path(".tokens")
    token_dir.mkdir(exist_ok=True)
    
    print("🌐 Opening browser for Yahoo authorization...")
    print()
    
    # Initialize - this will trigger OAuth flow
    try:
        query = YahooFantasySportsQuery(
            league_id="",  # Empty to get all leagues
            game_code="nfl",
            YAHOO_CLIENT_ID=CLIENT_ID,
            YAHOO_CLIENT_SECRET=CLIENT_SECRET,
            browser_callback=True,  # Opens browser automatically
            env_file_location=ENV_FILE_PATH,
            save_token_data_to_env_file=False,
        )
        
        print()
        print("✅ Authentication successful!")
        print()
        
        # Test by getting user leagues
        print("Testing connection by fetching your leagues...")
        try:
            # Get user info to verify connection
            current_game = query.get_current_game_metadata()
            nfl_game_key = discover_yfpy_nfl_game_key(current_game)
            print(f"✅ Connected! Current NFL game key: {nfl_game_key}")
            user_leagues = query.get_user_leagues_by_game_key(nfl_game_key)
            if user_leagues:
                print(f"✅ Found {len(user_leagues)} leagues:")
                for i, league in enumerate(user_leagues, 1):
                    league_name = getattr(league, 'name', 'Unknown')
                    league_id = getattr(league, 'league_id', 'Unknown')
                    print(f"   {i}. {league_name} (ID: {league_id})")
            
            # Save token for MCP server use
            if hasattr(query, 'oauth') and hasattr(query.oauth, 'token_data'):
                token_data = query.oauth.token_data

                # Update .env file with tokens
                access_token = token_data.get('access_token') or token_data.get('yahoo_access_token')
                refresh_token = token_data.get('refresh_token') or token_data.get('yahoo_refresh_token')
                if access_token and refresh_token:
                    update_env_file_with_tokens(
                        access_token,
                        refresh_token,
                        ENV_FILE_PATH,
                        expires_in=token_data.get("expires_in", 3600),
                    )
                    # Verify the app can actually reach the Fantasy API
                    preflight_fantasy_access(access_token)
                else:
                    print("⚠️  Could not extract tokens from token_data to update .env")
                    print(f"   Token data keys: {list(token_data.keys())}")

                print("   The MCP server can now use this token!")
            
        except Exception:
            print("Connection test failed.")
            print("   But authentication may still be successful.")
            
    except Exception:
        print("\nAuthentication failed.")
        print()
        print("Falling back to Method 2...")
        print()
        
        # Method 2: Manual OAuth flow
        manual_oauth_flow(CLIENT_ID, CLIENT_SECRET)
        
except ImportError:
    print("❌ yfpy not installed")
    print("Install with: pip install yfpy")
    print()
    print("Falling back to Method 2...")
    print()
    
    # Method 2: Manual OAuth flow
    manual_oauth_flow(CLIENT_ID, CLIENT_SECRET)

print()
print("=" * 70)
print("NEXT STEPS")
print("=" * 70)
print()
print("Once authenticated:")
print("1. The token is saved to the project .env file")
print("2. MCP clients should not store Yahoo token values in their configs")
print("3. Token will auto-refresh as needed")
print()
print("To use with MCP:")
print("1. Configure your MCP client to run this server from the checkout")
print("2. The server will load the saved token from the checkout .env")
print("3. Start making Fantasy Football API calls!")
print()
print("Need help? Check YAHOO_AUTH_REALITY.md for more details.")