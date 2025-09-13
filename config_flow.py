import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .api import VodarenskaAPI

_LOGGER = logging.getLogger(__name__)


class VodarenskaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VAS Vodárenská."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        self._username = None
        self._password = None
        self._client_id = None
        self._client_secret = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._username = user_input["username"]
            self._password = user_input["password"]
            self._client_id = user_input["client_id"]
            self._client_secret = user_input["client_secret"]

            # Ověření API přístupu
            try:
                api = VodarenskaAPI(
                    self._username, self._password, self._client_id, self._client_secret
                )
                # zavoláme hello_world pro test spojení
                await self.hass.async_add_executor_job(api.hello_world)

                return self.async_create_entry(
                    title=f"VAS Vodárenská ({self._username})",
                    data={
                        "username": self._username,
                        "password": self._password,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                )

            except Exception as e:
                _LOGGER.error("Cannot connect to VAS API: %s", e)
                errors["base"] = "cannot_connect"

        # Formulář pro zadání přihlašovacích údajů
        data_schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Required("client_id"): str,
                vol.Required("client_secret"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
