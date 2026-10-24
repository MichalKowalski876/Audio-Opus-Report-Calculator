from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from core import paths


CREDENTIALS_FILE = Path(
    paths.data_path(
        "Integrations",
        "Gmail",
        "Config",
        "credentials.json"
    )
)

TOKEN_FILE = Path(
    paths.data_path(
        "Integrations",
        "Gmail",
        "Config",
        "token.json"
    )
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


def get_gmail_credentials_path():
    return CREDENTIALS_FILE


def get_gmail_token_path():
    return TOKEN_FILE


def has_gmail_credentials():
    return CREDENTIALS_FILE.is_file()


def _load_saved_credentials():
    if not TOKEN_FILE.is_file():
        return None

    try:
        return Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )
    except Exception:
        return None


def _save_credentials(credentials):
    TOKEN_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8"
    )


def _refresh_credentials(credentials):
    if not credentials:
        return None

    if credentials.valid:
        return credentials

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _save_credentials(credentials)
            return credentials
        except Exception:
            return None

    return None


def has_gmail_authorization():
    credentials = _load_saved_credentials()

    if not credentials:
        return False

    return bool(
        credentials.valid
        or credentials.refresh_token
    )


def authorize_gmail():
    if not has_gmail_credentials():
        raise FileNotFoundError(
            "Brakuje konfiguracji Google OAuth."
        )

    credentials = _load_saved_credentials()

    if credentials:
        refreshed = _refresh_credentials(credentials)

        if refreshed and refreshed.valid:
            return refreshed

    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_FILE,
        SCOPES
    )

    credentials = flow.run_local_server(
        port=0
    )

    _save_credentials(credentials)

    return credentials


def get_gmail_service():
    credentials = _load_saved_credentials()

    if not credentials:
        raise RuntimeError(
            "Brak autoryzacji Gmail. Połącz konto Google ponownie."
        )

    if not credentials.valid:
        credentials = _refresh_credentials(credentials)

    if not credentials or not credentials.valid:
        raise RuntimeError(
            "Sesja Gmail wygasła i nie udało się jej odświeżyć. "
            "Połącz konto Google ponownie."
        )

    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False
    )
