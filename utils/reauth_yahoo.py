#!/usr/bin/env python3
"""Re-authenticate Yahoo Fantasy Sports tokens."""

import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import requests

from src.api.yahoo_credentials import (
    PROJECT_ENV_PATH,
    YAHOO_PROVISIONING_MESSAGE,
    YahooCredentialError,
    YahooProvisioningError,
    get_yahoo_consumer_credentials,
    is_yahoo_provisioning_failure,
    load_project_environment,
    persist_yahoo_tokens,
)

PROJECT_ROOT = PROJECT_ENV_PATH.parent
ENV_FILE_PATH = PROJECT_ENV_PATH
load_project_environment()

auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""

    def do_GET(self):
        """Handle GET request with auth code."""
        global auth_code
        query = urlparse(self.path).query
        params = parse_qs(query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authorization successful!</h1>"
                b"<p>You can close this window.</p></body></html>"
            )
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress server logs."""
        pass


def run_callback_server(port=8000):
    """Run the callback server in a thread."""
    server = HTTPServer(("localhost", port), CallbackHandler)
    server.handle_request()


def reauth_yahoo():
    """Complete re-authentication flow."""
    print("=" * 60)
    print("Yahoo Fantasy Sports Re-Authentication")
    print("=" * 60)
    print()

    try:
        client_id, client_secret = get_yahoo_consumer_credentials()
    except YahooCredentialError as error:
        print(f"Missing Yahoo credentials in .env: {error}")
        return False

    auth_url = "https://api.login.yahoo.com/oauth2/request_auth"
    token_url = "https://api.login.yahoo.com/oauth2/get_token"
    redirect_uri = "oob"

    print(f"📌 Using redirect URI: {redirect_uri}")
    print()
    print("⚠️  IMPORTANT: Make sure this matches your Yahoo App settings!")
    print()

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "language": "en-us",
    }
    auth_url_full = (
        auth_url + "?" + "&".join([f"{key}={value}" for key, value in auth_params.items()])
    )

    print("🔗 Opening browser for Yahoo login...")
    print()
    if not webbrowser.open(auth_url_full):
        print("Browser did not open. Retry from a browser-capable shell.")
        return False

    print("⏳ Waiting for authorization code...")
    print("   (For 'oob' flow, copy the code from the browser)")
    auth_code_value = input("\nEnter the authorization code from Yahoo: ").strip()

    if not auth_code_value:
        print("❌ No authorization code received. Timeout or user cancelled.")
        return False

    print("✅ Authorization code received!")
    print()
    print("🔄 Exchanging code for tokens...")

    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": auth_code_value,
        "grant_type": "authorization_code",
    }

    try:
        response = requests.post(token_url, data=token_data)
        if response.status_code != 200:
            print(f"Failed to get tokens: {response.status_code}")
            return False

        tokens = response.json()
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)
        if not access_token or not refresh_token:
            print("Token response did not include required token fields.")
            return False

        print("Tokens received successfully.")
        print(f"   Token expires in: {expires_in} seconds ({expires_in/3600:.1f} hours)")
        print()

        try:
            guid = get_user_guid(access_token)
        except YahooProvisioningError as error:
            print(f"❌ {error}")
            return False
        except Exception:
            print("Could not verify Yahoo Fantasy API access.")
            return False

        save_tokens(access_token, refresh_token, guid, expires_in)
        print("Authentication complete.")
        print("Tokens saved only to the project .env file.")
        return True
    except Exception:
        print("Error getting tokens")
        return False


def get_user_guid(access_token):
    """Get the user's Yahoo GUID after classifying provisioning failures."""
    url = "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1?format=json"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 200:
        data = response.json()
        users = data.get("fantasy_content", {}).get("users", {})
        if "0" in users:
            user = users["0"]["user"]
            if isinstance(user, list) and len(user) > 0:
                guid = user[0].get("guid")
                if guid:
                    print("Found Yahoo user GUID.")
                    return guid
        raise RuntimeError("Yahoo GUID missing from user response")

    if is_yahoo_provisioning_failure(response.status_code, response.text):
        raise YahooProvisioningError(YAHOO_PROVISIONING_MESSAGE)
    raise RuntimeError(f"Yahoo user GUID request failed: {response.status_code}")


def save_tokens(access_token, refresh_token, guid=None, expires_in=3600):
    """Save tokens and GUID through the shared credential seam."""
    persist_yahoo_tokens(
        access_token,
        refresh_token,
        int(expires_in),
        env_path=ENV_FILE_PATH,
        guid=guid,
    )


if __name__ == "__main__":
    raise SystemExit(0 if reauth_yahoo() else 1)
