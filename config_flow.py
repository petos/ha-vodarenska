# config_flow.py
from homeassistant import config_entries
from .const import DOMAIN
import voluptuous as vol

DATA_SCHEMA = vol.Schema({
    vol.Required("username"): str,
    vol.Required("password"): str,
    vol.Required("client_id"): str,
    vol.Required("client_secret"): str,
})

class HaVodarenskaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Vodárenská (VAS API)", data=user_input)
            print("ha_vodarenska config_flow")

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
