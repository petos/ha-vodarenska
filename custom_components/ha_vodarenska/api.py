import logging
import time
import requests
import shlex

from datetime import datetime, timedelta

from .const import BASE_URL_CONNECT, BASE_URL_API

_LOGGER = logging.getLogger(__name__)

def to_curl(url, headers=None, params=None):
    curl = ["curl", "-i", shlex.quote(url)]
    if params:
        # Přidáme query string, pokud už není součástí URL
        from urllib.parse import urlencode, urlsplit, urlunsplit

        split_url = urlsplit(url)
        query = urlencode(params)
        new_url = urlunsplit(split_url._replace(query=query))
        curl = ["curl", "-i", shlex.quote(new_url)]
    if headers:
        for k, v in headers.items():
            curl.extend(["-H", shlex.quote(f"{k}: {v}")])
    return " ".join(curl)

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

        resp = requests.post(url, data=data, timeout=10)

        try:
            resp.raise_for_status()
        except requests.HTTPError:
            _LOGGER.warning(
                "Token request failed: %s %s",
                resp.status_code,
                resp.text,
            )
            raise

        token_data = resp.json()

        self._token = token_data["access_token"]
        self._token_expiry = time.time() + token_data.get("expires_in", 3600) - 60

        return self._token

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_token()}"}

    def hello_world(self) -> dict:
        url = f"{BASE_URL_API}/HelloWorld"
        curl_cmd = to_curl(url, headers=self._headers())
        _LOGGER.debug("Executing API call as cURL: %s", curl_cmd)
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()

        return {
            "response": resp.text,
            "last_update": datetime.now().isoformat(timespec="seconds"),
        }

    def get_smartdata_customer(self):
        url = f"{BASE_URL_API}/SmartData/CustomerData"
        curl_cmd = to_curl(url, headers=self._headers())
        _LOGGER.debug("Executing API call as cURL: %s", curl_cmd)
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_smartdata_profile(self, meter_id: str, date_from: str, date_to: str):
        url = f"{BASE_URL_API}/SmartData/ProfileData"
        params = {
            "METERID": meter_id,
            "dateFrom": date_from,
            "dateTo": date_to,
        }

        resp = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=15,
        )

        curl_cmd = to_curl(url, headers=self._headers(), params=params)
        _LOGGER.debug("Executing API call as cURL: %s", curl_cmd)

        resp.raise_for_status()
        return resp.json()

class VodarenskaIntegration:
    def __init__(self, hass: HomeAssistant, api: VodarenskaAPI):
        self.hass = hass
        self.api = api

    async def async_update_all_meters(self):
        all_data = {}

        try:
            customers = await self.hass.async_add_executor_job(
                self.api.get_smartdata_customer
            )
        except Exception as e:
            _LOGGER.error("Error fetching customers: %s", e)
            return {}

        for customer in customers:
            for meter in customer.get("INSTALLED_METERS", []):
                meter_id = meter.get("METER_ID")
                if not meter_id:
                    continue

                try:
                    date_to = meter.get("METER_DATE_TO") or datetime.now().date().isoformat()
                    date_from = (
                        datetime.strptime(date_to, "%Y-%m-%d").date()
                        - timedelta(days=1)
                    ).isoformat()

                    profile_data = await self.hass.async_add_executor_job(
                        self.api.get_smartdata_profile,
                        meter_id,
                        date_from,
                        date_to,
                    )

                    if profile_data:
                        last_entry = profile_data[-1]
                        last_entry["_api_last_update"] = last_entry.get("DATE")
                        all_data[meter_id] = {
                            "profile": last_entry,
                            "meter": meter,
                            "customer": customer,
                        }
                    else:
                        _LOGGER.warning(
                            "No profile data found for meter %s",
                            meter_id,
                        )
                        all_data[meter_id] = {
                            "profile": {},
                            "meter": meter,
                            "customer": customer,
                        }

                except Exception as e:
                    _LOGGER.error(
                        "Error fetching profile data for meter %s: %s",
                        meter_id,
                        e,
                    )
                    all_data[meter_id] = {}

        return all_data
