from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the ha_vodarenska integration via YAML."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        hass.data[DOMAIN] = config[DOMAIN]

    # správně asynchronně načteme platformu sensor
    hass.async_create_task(
        async_load_platform(hass, "sensor", DOMAIN, {}, config)
    )

    return True

