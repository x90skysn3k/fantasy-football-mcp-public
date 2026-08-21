#!/usr/bin/env python3
"""
Re-authenticate with Yahoo Fantasy Sports
Full OAuth2 flow when refresh token expires
"""

import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
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

# Global to store the auth code
auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""

    def do_GET(self):
        global auth_code

        # Parse the callback URL
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            success_html = """
            <html>
            <head><title>Success!</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: green;">✅ Authentication Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <script>window.setTimeout(function(){window.close();}, 3000);</script>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
        else:
            # Error response
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            error_html = """
            <html>
            <head><title>Error</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: red;">❌ Authentication Failed</h1>
                <p>No authorization code received.</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def run_callback_server(port=8000):
    """Run the callback server in a thread."""
    server = HTTPServer(("localhost", port), CallbackHandler)
    server.timeout = 60  # 60 second timeout
    server.handle_request()  # Handle one request then stop


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

    # OAuth URLs
    auth_url = "https://api.login.yahoo.com/oauth2/request_auth"
    token_url = "https://api.login.yahoo.com/oauth2/get_token"

    # Callback configuration
    callback_port = 8000
    # redirect_uri = f"https://localhost:{callback_port}/callback"
    redirect_uri = "oob"

    print(f"📌 Using redirect URI: {redirect_uri}")
    print()
    print("⚠️  IMPORTANT: Make sure this matches your Yahoo App settings!")
    print()

    # For "oob" redirect, we don't need a callback server
    # If using callback server in the future, uncomment:
    # print(f"🌐 Starting callback server on port {callback_port}...")
    # server_thread = threading.Thread(target=run_callback_server, args=(callback_port,))
    # server_thread.daemon = True
    # server_thread.start()

    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "language": "en-us",
    }

    auth_url_full = auth_url + "?" + "&".join([f"{k}={v}" for k, v in auth_params.items()])

    print("🔗 Opening browser for Yahoo login...")
    print()
    print("If browser doesn't open, manually visit:")
    print(auth_url_full)
    print()

    # Open browser
    webbrowser.open(auth_url_full)

    # Wait for callback - for "oob" flow, get code manually
    print("⏳ Waiting for authorization code...")
    print("   (For 'oob' flow, you'll need to copy the code from the browser)")

    # For "oob" redirect, manually input the code
    auth_code = input("\nEnter the authorization code from Yahoo: ").strip()

    if not auth_code:
        print("❌ No authorization code received. Timeout or user cancelled.")
        return False

    print(f"✅ Authorization code received!")
    print()

    # Exchange code for tokens
    print("🔄 Exchanging code for tokens...")

    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": auth_code,
        "grant_type": "authorization_code",
    }

    try:
        response = requests.post(token_url, data=token_data)

        if response.status_code == 200:
            tokens = response.json()

            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in", 3600)

            print("Tokens received successfully.")
            print(f"   Token expires in: {expires_in} seconds ({expires_in/3600:.1f} hours)")
            print()

            # Get user GUID
            guid = get_user_guid(access_token)

            save_tokens(access_token, refresh_token, guid, expires_in)

            print("Authentication complete.")
            print("Tokens saved only to the project .env file.")

            return True

        else:
            print(f"Failed to get tokens: {response.status_code}")
            return False

    except Exception:
        print("Error getting tokens")
        return False


def get_user_guid(access_token):
    """Get the user's Yahoo GUID."""

    url = "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1?format=json"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()

            # Navigate the response to find GUID
            users = data.get("fantasy_content", {}).get("users", {})
            if "0" in users:
                user = users["0"]["user"]
                if isinstance(user, list) and len(user) > 0:
                    guid = user[0].get("guid")
                    if guid:
                        print("Found Yahoo user GUID.")
                        return guid
    except:
        pass

    return None



def save_tokens(access_token, refresh_token, guid=None, expires_in=3600):
    """Save tokens through the shared credential seam."""
    persist_yahoo_tokens(access_token, refresh_token, int(expires_in), env_path=ENV_FILE_PATH)
    if guid:
        _persist_guid(guid)


def _persist_guid(guid):
    """Persist Yahoo GUID without touching token fields or MCP client configs."""
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


if __name__ == "__main__":
    reauth_yahoo()
