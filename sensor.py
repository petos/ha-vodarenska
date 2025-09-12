from datetime import datetime
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .api import VodarenskaAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("Running async_setup_entry")
    api = hass.data[DOMAIN].get("api")
    if not api:
        _LOGGER.error("API instance not found in hass.data[DOMAIN]")
        return

    sensors = []

    # HelloWorld sensor
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
        for customer in customer_data_list:
            for meter in customer.get("INSTALLED_METERS", []):
                if meter.get("METER_ID"):
                    meter_sensor = VodarenskaMeterSensor(api, meter, customer)
                    installed_sensor = VodarenskaInstalledSensor(api, meter, customer)

                    sensors.append(meter_sensor)
                    sensors.append(installed_sensor)

                    _LOGGER.debug("Meter sensor prepared: %s", meter_sensor._attr_unique_id)
                    _LOGGER.debug("Installed sensor prepared: %s", installed_sensor._attr_unique_id)

    _LOGGER.debug("Adding total %d sensors", len(sensors))
    async_add_entities(sensors, True)


class VasHelloWorldSensor(SensorEntity):
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


class VodarenskaMeterSensor(SensorEntity):
    """Representation of a water meter sensor."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = "m³"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:water"

    def __init__(self, api: VodarenskaAPI, meter_data: dict, customer_data: dict):
        self._api = api
        self._meter_id = meter_data["METER_ID"]
        self._meter_number = meter_data.get("METER_NUMBER", str(self._meter_id))

        # základní identifikace
        self._attr_name = f"VAS Vodomer {self._meter_id}"
        self._attr_unique_id = f"ha_vodarenska_{self._meter_id}"

        # hlavní hodnota
        self._state: float | None = None

        # metadata jako atributy
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

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs

    @property
    def device_info(self):
        """Group meter sensors under one device per METER_ID."""
        return {
            "identifiers": {(DOMAIN, str(self._meter_id))},
            "name": f"VAS Vodomer {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "model": self._attrs.get("mp_type", "Unknown"),
            "serial_number": self._meter_number,
        }

    async def async_update(self):
        try:
            date_from_str = self._attrs.get("meter_date_from")
            date_to_str = datetime.now().date().isoformat() if self._attrs.get("meter_date_to") in (None, "null") else self._attrs.get("meter_date_to")

            profile_data = await self.hass.async_add_executor_job(
                self._api.get_smartdata_profile,
                self._meter_id,
                date_from_str,
                date_to_str,
            )
            if profile_data:
                last = profile_data[-1]
                raw_value = last.get("STATE")

                try:
                    self._state = float(raw_value) if raw_value is not None else None
                except (TypeError, ValueError):
                    _LOGGER.warning("Invalid value for meter %s: %s", self._meter_id, raw_value)
                    self._state = None

                self._attrs["last_update"] = datetime.now().isoformat()
                self._attrs["last_timestamp"] = last.get("DATE") or None
                _LOGGER.debug(
                    "Updated meter %s: value=%s, last_update=%s, last_timestamp=%s",
                    self._meter_id,
                    self._state,
                    self._attrs["last_update"],
                    self._attrs["last_timestamp"],
                )
        except Exception as e:
            _LOGGER.error("Error updating meter %s: %s", self._meter_id, e)


class VodarenskaInstalledSensor(BinarySensorEntity):
    """Sensor that shows whether the meter is still installed."""

    _attr_icon = "mdi:water-check"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, api: VodarenskaAPI, meter_data: dict, customer_data: dict):
        self._api = api
        self._meter_id = meter_data["METER_ID"]
        self._attr_name = f"VAS Vodomer {self._meter_id} Installed"
        self._attr_unique_id = f"ha_vodarenska_{self._meter_id}_installed"

        self._meter_number = meter_data.get("METER_NUMBER", str(self._meter_id))
        self._meter_date_to = meter_data.get("METER_DATE_TO")
        self._state = self._meter_date_to in (None, "None", "null")
        self._attr_is_on = self._meter_date_to in (None, "None", "null")

    @property
    def is_on(self):
        return self._state

    @property
    def icon(self):
        return "mdi:water-check" if self._state else "mdi:water-off"

    @property
    def device_info(self):
        """Same device group as the main meter sensor."""
        return {
            "identifiers": {(DOMAIN, str(self._meter_id))},
            "name": f"VAS Vodomer {self._meter_id}",
            "manufacturer": "VAS Vodárenská a.s.",
            "model": "Installed flag",
            "serial_number": self._meter_number,
        }

    async def async_update(self):
        try:
            customer_data_list = await self.hass.async_add_executor_job(self._api.get_smartdata_customer)
            for customer in customer_data_list or []:
                for meter in customer.get("INSTALLED_METERS", []):
                    if meter.get("METER_ID") == self._meter_id:
                        self._meter_date_to = meter.get("METER_DATE_TO")
                        self._state = self._meter_date_to in (None, "None", "null")
                        _LOGGER.debug(
                            "Updated installed sensor for meter %s: installed=%s (METER_DATE_TO=%s)",
                            self._meter_id,
                            self._state,
                            self._meter_date_to,
                        )
                        return
        except Exception as e:
            _LOGGER.error("Error updating Installed sensor for meter %s: %s", self._meter_id, e)
