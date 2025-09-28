import logging
import os
import shutil
import filecmp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN
from .api import VodarenskaAPI
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

def copy_blueprints(hass: HomeAssistant):
    src = os.path.join(os.path.dirname(__file__), "blueprints", "automation", DOMAIN)
    dest = os.path.join(hass.config.path("blueprints", "automation", DOMAIN))

    if not os.path.exists(src):
        return  # žádné blueprinty k dispozici

    changed = False

    if not os.path.exists(dest):
        shutil.copytree(src, dest)
        changed = True
    else:
        # zkopíruj nové soubory a aktualizuj změněné
        for file_name in os.listdir(src):
            src_file = os.path.join(src, file_name)
            dest_file = os.path.join(dest, file_name)

            if not os.path.exists(dest_file) or not filecmp.cmp(src_file, dest_file, shallow=False):
                shutil.copy2(src_file, dest_file)
                changed = True

    # pokud se něco změnilo, reload blueprintů
    if changed:
        hass.async_create_task(hass.services.async_call("blueprint", "reload"))

async def async_setup(hass: HomeAssistant, config: dict):
    
    """Zpracování případného YAML setupu (deprecated)."""
    if DOMAIN in config:
        _LOGGER.warning(
            "YAML setup for ha_vodarenska is deprecated. Please use the UI config flow."
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Zpristupnit blueprint"""
    copy_blueprints(hass)
    hass.async_create_task(hass.services.async_call("blueprint", "reload"))
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
