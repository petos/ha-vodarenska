import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .api import VodarenskaAPI
from .api import VodarenskaIntegration

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    if DOMAIN in config:
        _LOGGER.warning(
            "YAML setup for ha_vodarenska is deprecated. "
            "Please use the UI config flow."
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    conf = entry.data

    api = VodarenskaAPI(
        username=conf.get("username"),
        password=conf.get("password"),
        client_id=conf.get("client_id"),
        client_secret=conf.get("client_secret"),
    )

    hello_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="helloworld",
        update_method=lambda: hass.async_add_executor_job(api.hello_world),
        update_interval=timedelta(minutes=5),
    )

    integration = VodarenskaIntegration(hass, api)

    meters_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="meters_all",
        update_method=integration.async_update_all_meters,
        update_interval=timedelta(minutes=5),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "hello_coordinator": hello_coordinator,
        "meters_coordinator": meters_coordinator,
    }

    try:
        await hello_coordinator.async_config_entry_first_refresh()
        await meters_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Initialization failed: {err}") from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
