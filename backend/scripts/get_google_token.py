"""
One-time script to get a Google OAuth refresh token for the Calendar MCP server.

Prerequisites:
  1. In Google Cloud Console:
     - Enable the Google Calendar API
     - Enable the Google Calendar MCP API
     - Go to APIs & Services → Credentials
     - Create OAuth 2.0 Client ID (type: Desktop App)
     - Download the client secret JSON or copy the client ID and secret

  2. Add to your .env:
     GOOGLE_CLIENT_ID=your-client-id
     GOOGLE_CLIENT_SECRET=your-client-secret

  3. Run this script:
     uv run scripts/get_google_token.py

  4. A browser window will open — sign in and grant access to your calendar.

  5. Copy the printed GOOGLE_OAUTH_REFRESH_TOKEN into your .env file.
     You only need to do this once.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env")
    sys.exit(1)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("ERROR: Install google-auth-oauthlib first:")
    print("  uv pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.events",  # needed for create_event
]

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=SCOPES,
)

print("Opening browser for Google sign-in...")
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

print("\n✓ Success! Add this to your .env file:\n")
print(f"GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
print(f"\nAccess token (expires in ~1hr, auto-refreshed by the app):")
print(f"  {creds.token[:40]}...")
