import requests
import time

BASE_URL = "https://crm.vodarenska.cz:65000"
BASE_URL_CONNECT = f"{BASE_URL}/connect"
BASE_URL_API = f"{BASE_URL}/api"


class VodarenskaAPI:
    """Klient pro VAS API."""

    def __init__(self, username: str, password: str, client_id: str, client_secret: str):
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = None
        self._token_expiry = 0

    def _get_token(self) -> str:
        """Získá a uloží access token."""
        now = time.time()
        if self._token and now < self._token_expiry:
            return self._token

        url = f"{BASE_URL_CONNECT}/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expiry = now + payload.get("expires_in", 3600) - 30
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def hello_world(self) -> str:
        """Test HelloWorld endpoint s autentizací."""
        url = f"{BASE_URL_API}/HelloWorld"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.text
