"""OAuth 2.0 helper for Google Slides and Drive APIs."""

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Both scopes needed: Slides for creating/editing, Drive for copying templates
SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CREDENTIALS_PATH = _PROJECT_ROOT / "credentials.json"
_TOKEN_PATH = _PROJECT_ROOT / "token.json"


def get_credentials(server_mode: bool = False) -> Credentials:
    """Load cached credentials, refresh if expired, or run OAuth flow.

    Args:
        server_mode: If True, use GOOGLE_TOKEN_JSON env var and never open
                     a browser. Raises RuntimeError if no valid token exists.

    Expects credentials.json in the project root (downloaded from Google Cloud Console).
    Caches the token to token.json for subsequent runs.
    """
    creds = None

    # Cloud deploy: load token from env var
    token_json_env = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json_env:
        creds = Credentials.from_authorized_user_info(json.loads(token_json_env), SCOPES)

    # Local: load from file
    if not creds and _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if server_mode:
            raise RuntimeError(
                "No valid Google credentials available in server mode.\n"
                "Set GOOGLE_TOKEN_JSON env var with the contents of a valid token.json,\n"
                "or run the CLI locally first to generate token.json."
            )
        if not _CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"credentials.json not found at {_CREDENTIALS_PATH}\n"
                "Download it from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(_CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)

    # Save for next run (skip if running from env var only)
    if not token_json_env:
        with open(_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def build_slides_service(server_mode: bool = False):
    """Return an authorized Google Slides API v1 resource."""
    return build("slides", "v1", credentials=get_credentials(server_mode))


def build_drive_service(server_mode: bool = False):
    """Return an authorized Google Drive API v3 resource."""
    return build("drive", "v3", credentials=get_credentials(server_mode))
