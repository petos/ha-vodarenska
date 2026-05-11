from datetime import datetime
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .api import VodarenskaAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Running async_setup_entry")

    data = hass.data[DOMAIN][entry.entry_id]

    api = data["api"]
    hello_coordinator = data["hello_coordinator"]
    meters_coordinator = data["meters_coordinator"]

    sensors = []

    sensors.append(
        VasHelloWorldSensor(hello_coordinator, api)
    )

    meter_data_all = meters_coordinator.data or {}

    for meter_id, meter_data in meter_data_all.items():
        if not meter_id:
            continue


        sensors.append(
            VodarenskaMeterSensor(meters_coordinator, api, meter_data or {})
        )
        sensors.append(
            VodarenskaInstalledSensor(meters_coordinator, api, meter_data or {})
        )
        sensors.append(
            VodarenskaTemperatureSensor(meters_coordinator, api, meter_data or {})
        )

    _LOGGER.debug("Adding total %d sensors", len(sensors))
    async_add_entities(sensors, True)

class VodarenskaBaseEntity(CoordinatorEntity):
    def __init__(self, coordinator, meter_id):
        super().__init__(coordinator)
        self._meter_id = meter_id

    def _entry(self):
        return (self.coordinator.data or {}).get(
            self._meter_id,
            {},
        )

    def _profile(self):
        return self._entry().get("profile", {})

    def _meter(self):
        return self._entry().get("meter", {})

    def _customer(self):
        return self._entry().get("customer", {})

    @property
    def extra_state_attributes(self):
        profile = self._profile()
        meter = self._meter()
        customer = self._customer()

        return {
            "customer_id": customer.get("CP_ID"),
            "city": customer.get("CP_ADRESS", {}).get("CITY"),
            "city_part": customer.get("CP_ADRESS", {}).get("CITYPART"),
            "street": customer.get("CP_ADRESS", {}).get("STREET"),
            "house_number": customer.get("CP_ADRESS", {}).get("HOUSENUM"),
            "technical_number1": customer.get("TECHNUM1"),
            "technical_number2": customer.get("TECHNUM2"),
            "meter_date_from": meter.get("METER_DATE_FROM"),
            "meter_date_to": meter.get("METER_DATE_TO"),
            "radio_number": meter.get("RADIO_NUMBER"),
            "radio_date_from": meter.get("RADIO_DATE_FROM"),
            "radio_date_to": meter.get("RADIO_DATE_TO"),
            "mp_type": meter.get("MP_TYPE"),
            "last_update": profile.get("_api_last_update")
                or profile.get("DATE"),
            "last_seen": datetime.now().isoformat(),
        }

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, str(self._meter_id))
            },
            "name": f"VAS vodoměr {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "serial_number": self._meter_number,
            "model": self._meter().get(
                "MP_TYPE",
                "VAS Smart Water Meter",
            ),
        }

class VasHelloWorldSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "VAS HelloWorld"
    _attr_unique_id = "vas_helloworld"
    _attr_icon = "mdi:hand-wave"

    def __init__(self, coordinator: DataUpdateCoordinator, api):
        super().__init__(coordinator)
        self._api = api

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("response")

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "last_update": data.get("last_update") or datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }

class VodarenskaMeterSensor(VodarenskaBaseEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = "m³"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:water"
    _attr_has_entity_name = True

    def __init__(self, coordinator, api, meter_data):
        meter = meter_data.get("meter", {})
        super().__init__(coordinator,meter.get("METER_ID"))
        self._api = api
        self._meter_number = meter.get("METER_NUMBER",str(self._meter_id))
        self._attr_unique_id = f"{self._meter_id}"

    @property
    def native_value(self):
        last = self._profile()
        if last and "STATE" in last:
            try:
                return float(last["STATE"])
            except (ValueError, TypeError):
                return None
        return None

    @property
    def translation_placeholders(self):
        return {"meter_id": self._meter_id}

class VodarenskaInstalledSensor(VodarenskaBaseEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_translation_key = "installed"
    _attr_has_entity_name = True

    def __init__(self, coordinator, api, meter_data):
        meter = meter_data.get("meter", {})
        super().__init__(coordinator,meter.get("METER_ID"))
        self._meter_number = meter.get("METER_NUMBER",str(self._meter_id))
        self._attr_unique_id = (f"{self._meter_id}_installed")

    @property
    def is_on(self) -> bool:
        last = self._profile()
        date_to = (last or {}).get("METER_DATE_TO")
        return date_to in (None, "None", "null")

    @property
    def translation_placeholders(self):
        return {"meter_id": self._meter_id}

class VodarenskaTemperatureSensor(VodarenskaBaseEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"
    _attr_translation_key = "temperature"
    _attr_has_entity_name = True

    def __init__(self, coordinator, api, meter_data):
        meter = meter_data.get("meter", {})
        super().__init__(coordinator,meter.get("METER_ID"))
        self._meter_number = meter.get("METER_NUMBER",str(self._meter_id))
        self._attr_unique_id = (f"{self._meter_id}_temperature")

    @property
    def native_value(self):
        last = self._profile()
        if last and "HEAT" in last:
            try:
                return float(last["HEAT"])
            except (ValueError, TypeError):
                return None
        return None

    @property
    def translation_placeholders(self):
        return {"meter_id": self._meter_id}
