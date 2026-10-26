
import logging

from homeassistant.components.recorder.models import (
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
)
from homeassistant.const import UnitOfTemperature, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import TemperatureConverter, VolumeConverter

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_meter_statistic_id(meter_id: str) -> str:
    """Return the external statistic ID for a water meter."""
    return f"{DOMAIN}:vas_vodomer_{meter_id}_vodomer"


def get_temperature_statistic_id(meter_id: str) -> str:
    """Return the external statistic ID for meter temperature."""
    return f"{DOMAIN}:vas_vodomer_{meter_id}_teplota"


def register_meter_statistic(hass: HomeAssistant, meter_id: str) -> None:
    """Register external statistics sources for a water meter and its temperature."""

    meter_metadata: StatisticMetaData = {
        "has_sum": True,
        "mean_type": StatisticMeanType.NONE,
        "name": f"Vodoměr {meter_id}",
        "source": DOMAIN,
        "statistic_id": get_meter_statistic_id(meter_id),
        "unit_class": VolumeConverter.UNIT_CLASS,
        "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
    }

    temperature_metadata: StatisticMetaData = {
        "has_sum": False,
        "mean_type": StatisticMeanType.ARITHMETIC,
        "name": f"Teplota vodoměru {meter_id}",
        "source": DOMAIN,
        "statistic_id": get_temperature_statistic_id(meter_id),
        "unit_class": TemperatureConverter.UNIT_CLASS,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
    }

    async_add_external_statistics(hass, meter_metadata, [])
    async_add_external_statistics(hass, temperature_metadata, [])

    _LOGGER.debug(
        "Registered external statistics sources: %s, %s",
        meter_metadata["statistic_id"],
        temperature_metadata["statistic_id"],
    )
