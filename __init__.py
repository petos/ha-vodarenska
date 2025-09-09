from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
from .api import VodarenskaAPI
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    # Log warning jen pokud je YAML konfigurace opravdu přítomna
    if DOMAIN in config:
        _LOGGER.error("YAML setup is deprecated. Please use the UI config flow or ha_vodarenska config entry.")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("ha_vodarenska entry setup started")
    conf = entry.data
    api = VodarenskaAPI(
        conf["username"], conf["password"], conf["client_id"], conf["client_secret"]
    )

    # Uložíme API instance do hass.data pro sdílení s ostatními částmi integrace
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["api"] = api
    hass.data[DOMAIN]["date_from"] = conf.get("date_from")
    hass.data[DOMAIN]["date_to"] = conf.get("date_to")

    
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    _LOGGER.debug("ha_vodarenska entry setup complete")

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Unload sensor entities
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    if unload_ok:
        hass.data.pop(DOMAIN, None)
        _LOGGER.debug("ha_vodarenska entry unloaded")

    return unload_ok
