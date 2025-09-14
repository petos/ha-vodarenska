from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed, CoordinatorEntity

from .const import DOMAIN
from .api import VodarenskaAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Running async_setup_entry")
    api: VodarenskaAPI = hass.data[DOMAIN].get("api")
    if not api:
        _LOGGER.error("API instance not found in hass.data[DOMAIN]")
        return

    sensors = []

    # HelloWorld sensor – jednoduchý sensor, žádný coordinator
    hello_sensor = VasHelloWorldSensor(api)
    sensors.append(hello_sensor)
    _LOGGER.debug("HelloWorld sensor prepared: %s", hello_sensor._attr_unique_id)

    try:
        customer_data_list = await hass.async_add_executor_job(api.get_smartdata_customer)
        _LOGGER.debug("Customer data list fetched: %s", customer_data_list)
    except Exception as e:
        _LOGGER.error("Error fetching customer data: %s", e)
        customer_data_list = []

    if not customer_data_list:
        _LOGGER.debug("No customer data available, only HelloWorld sensor will be added")
    else:
        for customer in customer_data_list:
            for meter in customer.get("INSTALLED_METERS", []):
                meter_id = meter.get("METER_ID")
                if not meter_id:
                    continue

                # Vytvoříme coordinator pro každý meter, update se bude provádět asynchronně
                async def async_update_data(meter_id=meter_id, meter=meter):
                    try:
                        date_to = meter.get("METER_DATE_TO") or datetime.now().date().isoformat()
                        date_from = (datetime.strptime(date_to, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
                        #date_from = meter.get("METER_DATE_FROM").split("T")[0]
                        profile_data = await hass.async_add_executor_job(
                            api.get_smartdata_profile, meter_id, date_from, date_to
                        )
                        if profile_data:
                            last_entry = profile_data[-1]
                            # uložíme DATE z API jako last_update
                            last_entry["_api_last_update"] = last_entry.get("DATE")
                            return last_entry
                        return None
                    except Exception as e:
                        raise UpdateFailed(f"Error fetching profile data for meter {meter_id}: {e}")

                coordinator = DataUpdateCoordinator(
                    hass,
                    _LOGGER,
                    name=f"meter_{meter_id}",
                    update_method=async_update_data,
                    update_interval=timedelta(minutes=5),
                )

                # nevykonáváme await coordinator.async_refresh() – necháme HA provést první update
                meter_sensor = VodarenskaMeterSensor(coordinator, api, meter, customer)
                installed_sensor = VodarenskaInstalledSensor(coordinator, api, meter, customer)
                temperature_sensor = VodarenskaTemperatureSensor(coordinator, api, meter, customer)

                sensors.append(meter_sensor)
                sensors.append(installed_sensor)
                sensors.append(temperature_sensor)

                _LOGGER.debug("Meter sensor prepared: %s", meter_sensor._attr_unique_id)
                _LOGGER.debug("Installed sensor prepared: %s", installed_sensor._attr_unique_id)
                _LOGGER.debug("Temperature sensor prepared: %s", temperature_sensor._attr_unique_id)

    _LOGGER.debug("Adding total %d sensors", len(sensors))
    async_add_entities(sensors, True)


class VasHelloWorldSensor(SensorEntity):
    entity_registry_enabled_default = False

    def __init__(self, api: VodarenskaAPI):
        self._api = api
        self._attr_name = "VAS HelloWorld"
        self._attr_unique_id = "vas_helloworld"
        self._state = None
        self._attrs = {}
        self._attr_icon = "mdi:hand-wave"

    @property
    def native_value(self):
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


class VodarenskaMeterSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = "m³"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:water"

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
        self._attr_name = f"VAS Vodomer {self._meter_id}"
        self._attr_unique_id = f"ha_vodarenska_{self._meter_id}"


    @property
    def native_value(self):
        """Vrací poslední stav z coordinátora"""
        last = self.coordinator.data
        if last and "STATE" in last:
            try:
                return float(last["STATE"])
            except (ValueError, TypeError):
                return None
        return None

    @property
    def extra_state_attributes(self):
        attrs = dict(self._attrs)
        if self.coordinator.data:
            attrs["last_seen"] = datetime.now().isoformat()
            attrs["last_update"] = self.coordinator.data.get("_api_last_update")
        return attrs

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self._meter_id))},
            "name": f"VAS Vodomer {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "model": self._attrs.get("mp_type", "Unknown"),
            "serial_number": self._meter_number,
        }


class VodarenskaInstalledSensor(CoordinatorEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, coordinator: DataUpdateCoordinator, api: VodarenskaAPI, meter_data: dict, customer_data: dict):
        super().__init__(coordinator)
        self._api = api
        self._meter_id = meter_data["METER_ID"]
        self._meter_number = meter_data.get("METER_NUMBER", str(self._meter_id))
        self._attr_name = f"VAS Vodomer {self._meter_id} Installed"
        self._attr_unique_id = f"ha_vodarenska_{self._meter_id}_installed"
        # přidáme self._attrs
        self._attrs = {
            "customer_id": customer_data.get("CP_ID"),
            "meter_date_from": meter_data.get("METER_DATE_FROM"),
            "meter_date_to": meter_data.get("METER_DATE_TO"),
            "radio_number": meter_data.get("RADIO_NUMBER"),
        }

    @property
    def is_on(self) -> bool:
        """Vrací True, pokud meter stále nainstalován (METER_DATE_TO je None)"""
        last_meter_data = self.coordinator.data
        if not last_meter_data:
            return False
        date_to = last_meter_data.get("METER_DATE_TO")
        return date_to in (None, "None", "null")

    @property
    def extra_state_attributes(self):
        attrs = dict(self._attrs)
        if self.coordinator.data:
            attrs["last_seen"] = datetime.now().isoformat()
            attrs["last_update"] = self.coordinator.data.get("_api_last_update")
        return attrs

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self._meter_id))},
            "name": f"VAS Vodomer {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "model": "Installed flag",
            "serial_number": self._meter_number,
        }


class VodarenskaTemperatureSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"

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
        self._attr_name = f"VAS Vodomer {self._meter_id} Temperature"
        self._attr_unique_id = f"ha_vodarenska_{self._meter_id}_temperature"

    @property
    def native_value(self):
        """Vrací HEAT hodnotu (teplota) z coordinátora"""
        last = self.coordinator.data
        if last and "HEAT" in last:
            try:
                return float(last["HEAT"])
            except (ValueError, TypeError):
                return None
        return None

    @property
    def extra_state_attributes(self):
        attrs = dict(self._attrs)
        if self.coordinator.data:
            attrs["last_seen"] = datetime.now().isoformat()
            attrs["last_update"] = self.coordinator.data.get("_api_last_update")
        return attrs

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self._meter_id))},
            "name": f"VAS Vodomer {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "model": "Temperature sensor",
            "serial_number": self._meter_number,
        }
