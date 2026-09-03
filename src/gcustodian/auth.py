"""OAuth credential loading and one-time authorization flow for Google APIs.

Add a service's scopes to SCOPES as it's wired up (Gmail now, Photos/Drive later)
and re-run `python -m gcustodian.auth` to re-consent when scopes change.
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

CREDENTIALS_DIR = Path(__file__).resolve().parent.parent.parent / "credentials"
CLIENT_SECRET_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]


def get_credentials() -> Credentials:
    """Load cached credentials, refreshing if needed. Raises if never authorized."""
    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "No credentials found. Run `python -m gcustodian.auth` first to authorize."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return creds


def main() -> None:
    """Interactive one-time (or re-run after scope changes) consent flow."""
    if not CLIENT_SECRET_FILE.exists():
        raise SystemExit(
            f"Missing {CLIENT_SECRET_FILE}. Download an OAuth Desktop client "
            "from Google Cloud Console and save it there as credentials.json."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Authorized. Token saved to {TOKEN_FILE}")


if __name__ == "__main__":
    main()
