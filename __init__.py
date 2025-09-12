import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .api import VodarenskaAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Zpracování případného YAML setupu (deprecated)."""
    if DOMAIN in config:
        _LOGGER.warning(
            "YAML setup for ha_vodarenska is deprecated. Please use the UI config flow."
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Nastavení integrace přes Config Entry (UI)."""
    conf = entry.data

    # Inicializace API klienta
    api = VodarenskaAPI(
        username=conf.get("username"),
        password=conf.get("password"),
        client_id=conf.get("client_id"),
        client_secret=conf.get("client_secret"),
    )

    # Uložíme API instance do hass.data pro sdílení s ostatními částmi integrace
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["api"] = api

    # Forward entry setups na sensor platformu
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    _LOGGER.debug("ha_vodarenska entry setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Odstranění integrace při unloadu entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data.pop(DOMAIN, None)
        _LOGGER.debug("ha_vodarenska entry unloaded")
    return unload_ok
