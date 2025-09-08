from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
from .api import VodarenskaAPI


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up HelloWorld sensor."""
    conf = hass.data[DOMAIN]
    api = VodarenskaAPI(
        conf["username"],
        conf["password"],
        conf["client_id"],
        conf["client_secret"],
    )
    async_add_entities([VasHelloWorldSensor(api)], True)


class VasHelloWorldSensor(SensorEntity):
    """Sensor zobrazující odpověď z HelloWorld endpointu."""

    def __init__(self, api: VodarenskaAPI):
        self._api = api
        self._attr_name = "VAS HelloWorld"
        self._attr_unique_id = "vas_helloworld"
        self._state = None

    @property
    def state(self):
        return self._state

    async def async_update(self):
        self._state = await self.hass.async_add_executor_job(self._api.hello_world)
