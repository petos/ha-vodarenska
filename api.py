import requests
import time
from datetime import datetime
from .const import BASE_URL_CONNECT, BASE_URL_API
import logging

_LOGGER = logging.getLogger(__name__)

class VodarenskaAPI:
    def __init__(self, username: str, password: str, client_id: str, client_secret: str):
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = None
        self._token_expiry = 0

    def _get_token(self) -> str:
        if self._token and self._token_expiry > time.time():
            return self._token

        url = f"{BASE_URL_CONNECT}/token"
        data = {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        # Bezpečné logování (NEzapisuj heslo ani client_secret)
        _LOGGER.debug(
            "Requesting token at %s (user=%s, client_id=%s)",
            url, self._username, self._client_id
        )

        resp = requests.post(url, data=data, timeout=10)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            _LOGGER.error("Token request failed: %s | body=%s", e, getattr(resp, "text", ""))
            raise

        token_data = resp.json()
        self._token = token_data["access_token"]
        self._token_expiry = time.time() + token_data.get("expires_in", 3600) - 60
        return self._token


    def _headers(self):
        return {"Authorization": f"Bearer {self._get_token()}"}

    def hello_world(self) -> dict:
        """Test HelloWorld endpoint s autentizací."""
        url = f"{BASE_URL_API}/HelloWorld"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return {
            "response": resp.text,
            "last_update": datetime.now().isoformat(timespec="seconds")
        }

    def get_smartdata_customer(self) -> dict:
        """Načte SmartData/CustomerData."""
        url = f"{BASE_URL_API}/SmartData/CustomerData"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_smartdata_profile(self) -> dict:
        """Načte SmartData/ProfileData."""
        url = f"{BASE_URL_API}/SmartData/ProfileData"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_smartdata_alerts(self) -> dict:
        """Načte SmartData/AlertData."""
        url = f"{BASE_URL_API}/SmartData/AlertData"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
