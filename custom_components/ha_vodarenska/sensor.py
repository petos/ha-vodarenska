from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed, CoordinatorEntity

from .const import DOMAIN
from .api import VodarenskaAPI, VodarenskaIntegration

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Running async_setup_entry")
    api: VodarenskaAPI = hass.data[DOMAIN].get("api")
    if not api:
        _LOGGER.error("API instance not found in hass.data[DOMAIN]")
        return

    sensors = []

    # HelloWorld – vlastní coordinator
    hello_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="helloworld",
        update_method=lambda: hass.async_add_executor_job(api.hello_world),
        update_interval=timedelta(minutes=5),
    )
    await hello_coordinator.async_config_entry_first_refresh()
    hello_sensor = VasHelloWorldSensor(hello_coordinator, api)
    sensors.append(hello_sensor)
    _LOGGER.debug("HelloWorld sensor prepared: %s", hello_sensor._attr_unique_id)

    try:
        customer_data_list = await hass.async_add_executor_job(api.get_smartdata_customer)
        _LOGGER.debug("Customer data list fetched: %s", customer_data_list)
    except Exception as e:
        _LOGGER.error("Error fetching customer data: %s", e)
        customer_data_list = []

    if customer_data_list:
        integration = VodarenskaIntegration(hass, api, customer_data_list)
        meters_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="meters_all",
            update_method=integration.async_update_all_meters,
            update_interval=timedelta(minutes=5),
        )

        await meters_coordinator.async_config_entry_first_refresh()

        for customer in customer_data_list:
            for meter in customer.get("INSTALLED_METERS", []):
                meter_id = meter.get("METER_ID")
                if not meter_id:
                    continue

                meter_sensor = VodarenskaMeterSensor(meters_coordinator, api, meter, customer)
                installed_sensor = VodarenskaInstalledSensor(meters_coordinator, api, meter, customer)
                temperature_sensor = VodarenskaTemperatureSensor(meters_coordinator, api, meter, customer)

                sensors.append(meter_sensor)
                sensors.append(installed_sensor)
                sensors.append(temperature_sensor)

                _LOGGER.debug("Meter sensor prepared: %s", meter_sensor._attr_unique_id)
                _LOGGER.debug("Installed sensor prepared: %s", installed_sensor._attr_unique_id)
                _LOGGER.debug("Temperature sensor prepared: %s", temperature_sensor._attr_unique_id)

    _LOGGER.debug("Adding total %d sensors", len(sensors))
    async_add_entities(sensors, True)


class VasHelloWorldSensor(CoordinatorEntity, SensorEntity):
    entity_registry_enabled_default = False
    _attr_name = "VAS HelloWorld"
    _attr_unique_id = "vas_helloworld"
    _attr_icon = "mdi:hand-wave"

    def __init__(self, coordinator: DataUpdateCoordinator, api):
        super().__init__(coordinator)
        self._api = api
        self._attrs = {}
        self._state = None

    @property
    def native_value(self):
        return self.coordinator.data.get("response") if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        attrs = dict(self._attrs)
        if self.coordinator.data:
            attrs["last_update"] = self.coordinator.data.get("last_update") or datetime.now().isoformat()
            attrs["last_seen"] = datetime.now().isoformat()
        return attrs


class VodarenskaMeterSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = "m³"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:water"
    _attr_translation_key = "meter"
    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, api: VodarenskaAPI, meter_data: dict, customer_data: dict):
        super().__init__(coordinator)
        self._api = api
        self._meter_id = meter_data["METER_ID"]
        self._meter_number = meter_data.get("METER_NUMBER", str(self._meter_id))
        self._attrs = {
            "customer_id": customer_data.get("CP_ID"),
            "city": customer_data.get("CP_ADRESS", {}).get("CITY"),
            "city_part": customer_data.get("CP_ADRESS", {}).get("CITYPART"),
            "street": customer_data.get("CP_ADRESS", {}).get("STREET"),
            "house_number": customer_data.get("CP_ADRESS", {}).get("HOUSENUM"),
            "technical_number1": customer_data.get("TECHNUM1"),
            "technical_number2": customer_data.get("TECHNUM2"),
            "meter_date_from": meter_data.get("METER_DATE_FROM"),
            "meter_date_to": meter_data.get("METER_DATE_TO"),
            "radio_number": meter_data.get("RADIO_NUMBER"),
            "radio_date_from": meter_data.get("RADIO_DATE_FROM"),
            "radio_date_to": meter_data.get("RADIO_DATE_TO"),
            "mp_type": meter_data.get("MP_TYPE"),
        }
        self._attr_unique_id = f"{self._meter_id}"

    @property
    def native_value(self):
        last = self.coordinator.data.get(self._meter_id)
        if last and "STATE" in last:
            try:
                value = float(last["STATE"])
                _LOGGER.debug("Meter %s native_value=%s", self._meter_id, value)
                return value
            except (ValueError, TypeError):
                _LOGGER.warning("Meter %s returned invalid STATE: %s", self._meter_id, last.get("STATE"))
                return None
        _LOGGER.debug("Meter %s has no STATE in coordinator data", self._meter_id)
        return None

    @property
    def extra_state_attributes(self):
        attrs = dict(self._attrs)
        last = self.coordinator.data.get(self._meter_id)
        if last:
            attrs["last_seen"] = datetime.now().isoformat()
            attrs["last_update"] = last.get("_api_last_update") or last.get("DATE")
        return attrs

    @property
    def translation_placeholders(self):
        return {"meter_id": self._meter_id}

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self._meter_id))},
            "name": f"VAS vodoměr {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "model": self._attrs.get("mp_type", "Unknown"),
            "serial_number": self._meter_number,
        }

class VodarenskaInstalledSensor(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_translation_key = "installed"
    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, api: VodarenskaAPI, meter_data: dict, customer_data: dict):
        super().__init__(coordinator)
        self._api = api
        self._meter_id = meter_data["METER_ID"]
        self._meter_number = meter_data.get("METER_NUMBER", str(self._meter_id))
        self._attr_unique_id = f"{self._meter_id}_installed"
        self._attrs = {
            "customer_id": customer_data.get("CP_ID"),
            "meter_date_from": meter_data.get("METER_DATE_FROM"),
            "meter_date_to": meter_data.get("METER_DATE_TO"),
            "radio_number": meter_data.get("RADIO_NUMBER"),
        }

    @property
    def is_on(self) -> bool:
        last = self.coordinator.data.get(self._meter_id)
        date_to = (last.get("METER_DATE_TO") if last else None) or self._attrs.get("meter_date_to")
        return date_to in (None, "None", "null")

    @property
    def extra_state_attributes(self):
        attrs = dict(self._attrs)
        last = self.coordinator.data.get(self._meter_id)
        if last:
            attrs["last_seen"] = datetime.now().isoformat()
            attrs["last_update"] = last.get("_api_last_update") or last.get("DATE")
        return attrs

    @property
    def translation_placeholders(self):
        return {"meter_id": self._meter_id}

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self._meter_id))},
            "name": f"VAS vodoměr {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "model": "Installed flag",
            "serial_number": self._meter_number,
        }

class VodarenskaTemperatureSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"
    _attr_translation_key = "temperature"
    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, api: VodarenskaAPI, meter_data: dict, customer_data: dict):
        super().__init__(coordinator)
        self._api = api
        self._meter_id = meter_data["METER_ID"]
        self._meter_number = meter_data.get("METER_NUMBER", str(self._meter_id))
        self._attrs = {
            "customer_id": customer_data.get("CP_ID"),
            "meter_date_from": meter_data.get("METER_DATE_FROM"),
            "meter_date_to": meter_data.get("METER_DATE_TO"),
            "radio_number": meter_data.get("RADIO_NUMBER"),
        }
        self._attr_unique_id = f"{self._meter_id}_temperature"

    @property
    def translation_placeholders(self):
        return {"meter_id": self._meter_id}

    @property
    def native_value(self):
        last = self.coordinator.data.get(self._meter_id)
        if last and "HEAT" in last:
            try:
                value = float(last["HEAT"])
                _LOGGER.debug("Meter %s native_value=%s (temperature)", self._meter_id, value)
                return value
            except (ValueError, TypeError):
                _LOGGER.warning("Meter %s returned invalid HEAT: %s", self._meter_id, last.get("HEAT"))
                return None
        _LOGGER.debug("Meter %s has no HEAT in coordinator data; last: %s", self._meter_id, last)
        return None

    @property
    def extra_state_attributes(self):
        attrs = dict(self._attrs)
        last = self.coordinator.data.get(self._meter_id)
        if last:
            attrs["last_seen"] = datetime.now().isoformat()
            attrs["last_update"] = last.get("_api_last_update") or last.get("DATE")
        return attrs

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self._meter_id))},
            "name": f"VAS vodoměr {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "model": "Temperature sensor",
            "serial_number": self._meter_number,
        }
