from typing import Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the ha_vodarenska integration via YAML."""
    conf = config.get(DOMAIN, {})
    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN] = {
        "username": conf.get("username"),
        "password": conf.get("password"),
        "client_id": conf.get("client_id"),
        "client_secret": conf.get("client_secret"),
    }

    # Asynchronně načteme platformu sensor
    hass.async_create_task(
        async_load_platform(hass, "sensor", DOMAIN, {}, config)
    )

    return True
