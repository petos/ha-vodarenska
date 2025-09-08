import requests

BASE_URL = "https://crm.vodarenska.cz:65000/api"


class VodarenskaAPI:
    """Jednoduchý klient pro testovací HelloWorld endpoint."""

    def hello_world(self) -> str:
        """Zavolá HelloWorld endpoint a vrátí textovou odpověď."""
        url = f"{BASE_URL}/HelloWorld"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.text

