from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .api import VodarenskaAPI
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Running async_setup_entry")
    api = hass.data[DOMAIN].get("api")
    if not api:
        _LOGGER.error("API instance not found in hass.data[DOMAIN]")
        return

    sensors = []

    # Vždy přidáme HelloWorld sensor
    hello_sensor = VasHelloWorldSensor(api)
    sensors.append(hello_sensor)
    _LOGGER.debug("HelloWorld sensor prepared: %s", hello_sensor._attr_unique_id)

    # načtení SmartData CustomerData (seznam vodoměrů)
    try:
        customer_data_list = await hass.async_add_executor_job(api.get_smartdata_customer)
        _LOGGER.debug("Customer data list fetched: %s", customer_data_list)
    except Exception as e:
        _LOGGER.error("Error fetching customer data: %s", e)
        customer_data_list = []

    if not customer_data_list:
        _LOGGER.debug("No customer data available, only HelloWorld sensor will be added")
    else:
        meters = customer_data_list if isinstance(customer_data_list, list) else []
        for customer in meters:
            for meter in customer.get("INSTALLED_METERS", []):
                meter_id = meter.get("METER_ID")
                if meter_id:
                    meter_sensor = VasMeterSensor(api, meter_id)
                    sensors.append(meter_sensor)
                    _LOGGER.debug("Meter sensor prepared: %s", meter_sensor._attr_unique_id)

    _LOGGER.debug("Adding total %d sensors", len(sensors))
    async_add_entities(sensors, True)


class VasHelloWorldSensor(SensorEntity):
    def __init__(self, api: VodarenskaAPI):
        self._api = api
        self._attr_name = "VAS HelloWorld"
        self._attr_unique_id = "vas_helloworld"
        self._state = None
        self._attrs = {}

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs

    async def async_update(self):
        try:
            data = await self.hass.async_add_executor_job(self._api.hello_world)
            self._state = data.get("response") if isinstance(data, dict) else str(data)
            self._attrs = {
                "last_update": (data.get("last_update") if isinstance(data, dict) else None)
                or datetime.now().isoformat()
            }
            _LOGGER.debug("HelloWorld sensor updated: %s", self._state)
        except Exception as e:
            _LOGGER.error("Error updating HelloWorld sensor: %s", e)


class VasMeterSensor(SensorEntity):
    def __init__(self, api: VodarenskaAPI, meter_id: str):
        self._api = api
        self._meter_id = meter_id
        self._attr_name = f"VAS Vodomer {meter_id}"
        self._attr_unique_id = f"vas_meter_{meter_id}"
        self._state = None
        self._attrs = {}
        self._attr_icon = "mdi:water" 

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs

    async def async_update(self):
        conf = self.hass.data[DOMAIN]
        date_from = conf.get("date_from")
        date_to = conf.get("date_to")

        if not date_from or not date_to:
            self._state = "missing_date_range"
            self._attrs = {"meter_id": self._meter_id}
        else:
            try:
                data = await self.hass.async_add_executor_job(
                    self._api.get_smartdata_profile,
                    self._meter_id,
                    date_from,
                    date_to,
                )
                _LOGGER.debug("Profile data for meter %s: %s", self._meter_id, data)

                if data and isinstance(data, list):
                    last = data[-1]
                    self._state = last.get("STATE")
                    self._attrs = {
                        "timestamp": last.get("DATE"),
                        "meter_id": self._meter_id,
                    }
                else:
                    self._state = "no_data"
                    self._attrs = {"meter_id": self._meter_id}
            except Exception as e:
                _LOGGER.error("Error updating meter %s: %s", self._meter_id, e)
                self._state = "error"
                self._attrs = {"meter_id": self._meter_id}
