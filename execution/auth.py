"""OAuth 2.0 helper for Google Slides and Drive APIs."""

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


def get_credentials() -> Credentials:
    """Load cached credentials, refresh if expired, or run OAuth flow.

    Expects credentials.json in the project root (downloaded from Google Cloud Console).
    Caches the token to token.json for subsequent runs.
    """
    creds = None

    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not _CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"credentials.json not found at {_CREDENTIALS_PATH}\n"
                "Download it from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(_CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)

    # Save for next run
    with open(_TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    return creds


def build_slides_service():
    """Return an authorized Google Slides API v1 resource."""
    return build("slides", "v1", credentials=get_credentials())


def build_drive_service():
    """Return an authorized Google Drive API v3 resource."""
    return build("drive", "v3", credentials=get_credentials())
