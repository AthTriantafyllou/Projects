import requests
from datetime import datetime, timedelta
from db import get_connection
from main import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN_URL

def google_refresh_access_token(refresh_token: str):
    """
    Refreshes Google Calendar access token.
    """
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    resp = requests.post(GOOGLE_TOKEN_URL, data=data)
    if resp.status_code != 200:
        print("❌ Failed to refresh Google token:", resp.text)
        return None, None

    json_resp = resp.json()
    return json_resp.get("access_token"), json_resp.get("expires_in")


def refresh_google_access_token(refresh_token: str):
    """
    Refresh Gmail access token.
    """
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    resp = requests.post(GOOGLE_TOKEN_URL, data=data)

    if resp.status_code != 200:
        print("Failed refresh:", resp.text)
        return None, None

    json_resp = resp.json()
    return json_resp.get("access_token"), json_resp.get("expires_in")
