import logging
from datetime import date, datetime, timedelta

from homeassistant.components.recorder.models import StatisticMeanType,StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfTemperature, UnitOfVolume
from homeassistant.core import HomeAssistant,ServiceCall
from homeassistant.util.unit_conversion import TemperatureConverter, VolumeConverter
from homeassistant.util import dt as dt_util

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

def import_meter_profile_statistics(
    hass: HomeAssistant,
    meter_id: str,
    profile_history: list[dict],
) -> None:
    """Import hourly water meter and temperature statistics."""

    if not profile_history:
        return

    meter_statistic_id = get_meter_statistic_id(meter_id)
    temperature_statistic_id = get_temperature_statistic_id(meter_id)

    # Use Home Assistant's configured time zone for API timestamps
    # that do not contain an explicit time zone.
    from homeassistant.util import dt as dt_util

    timezone = dt_util.get_time_zone(hass.config.time_zone)
    hourly_data: dict[datetime, dict] = {}

    for entry in profile_history:
        date_value = entry.get("DATE")
        if not date_value:
            continue

        try:
            timestamp = datetime.fromisoformat(date_value)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "Invalid DATE in profile for meter %s: %s",
                meter_id,
                date_value,
            )
            continue

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone)

        hour = timestamp.replace(minute=0, second=0, microsecond=0)

        # Sort-independent selection: keep the newest record in each hour.
        existing = hourly_data.get(hour)
        if existing is None or timestamp > existing["_timestamp"]:
            hourly_data[hour] = {
                "_timestamp": timestamp,
                "entry": entry,
            }

    meter_stats = []
    temperature_stats = []

    for hour, data in sorted(hourly_data.items()):
        entry = data["entry"]

        try:
            state = float(entry["STATE"])
        except (KeyError, TypeError, ValueError):
            state = None

        if state is not None:
            meter_stats.append(
                {
                    "start": hour,
                    "state": state,
                    "sum": state,
                }
            )

        try:
            temperature = float(entry["HEAT"])
        except (KeyError, TypeError, ValueError):
            temperature = None

        if temperature is not None:
            temperature_stats.append(
                {
                    "start": hour,
                    "mean": temperature,
                }
            )

    if meter_stats:
        meter_metadata: StatisticMetaData = {
            "has_sum": True,
            "mean_type": StatisticMeanType.NONE,
            "name": f"Vodoměr {meter_id}",
            "source": DOMAIN,
            "statistic_id": meter_statistic_id,
            "unit_class": VolumeConverter.UNIT_CLASS,
            "unit_of_measurement": UnitOfVolume.CUBIC_METERS,
        }

        async_add_external_statistics(hass, meter_metadata, meter_stats)

    if temperature_stats:
        temperature_metadata: StatisticMetaData = {
            "has_sum": False,
            "mean_type": StatisticMeanType.ARITHMETIC,
            "name": f"Teplota vodoměru {meter_id}",
            "source": DOMAIN,
            "statistic_id": temperature_statistic_id,
            "unit_class": TemperatureConverter.UNIT_CLASS,
            "unit_of_measurement": UnitOfTemperature.CELSIUS,
        }

        async_add_external_statistics(
            hass,
            temperature_metadata,
            temperature_stats,
        )

    _LOGGER.debug(
        "Imported profile statistics for meter %s: water=%d, temperature=%d",
        meter_id,
        len(meter_stats),
        len(temperature_stats),
    )

async def async_import_full_history(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Import complete available history in 30-day batches."""

    entries = hass.config_entries.async_entries(DOMAIN)

    for config_entry in entries:
        data = hass.data[DOMAIN].get(config_entry.entry_id)
        if not data:
            continue

        api = data["api"]
        meters = data["meters_coordinator"].data
        date_to = dt_util.now().date()

        for meter_id, meter_data in meters.items():
            meter = meter_data.get("meter", {})
            date_from_value = meter.get("METER_DATE_FROM")

            if not date_from_value:
                _LOGGER.warning(
                    "Cannot import full history for meter %s: "
                    "METER_DATE_FROM is missing",
                    meter_id,
                )
                continue

            try:
                # METER_DATE_FROM may contain a date or a timestamp.
                date_from = date.fromisoformat(
                    str(date_from_value)[:10]
                )

                if date_from > date_to:
                    _LOGGER.warning(
                        "Cannot import full history for meter %s: "
                        "start date %s is in the future",
                        meter_id,
                        date_from,
                    )
                    continue

                _LOGGER.info(
                    "Starting full history import for meter %s: %s to %s",
                    meter_id,
                    date_from,
                    date_to,
                )

                batch_start = date_from
                total_records = 0

                while batch_start <= date_to:
                    # Each batch covers at most 30 days.
                    batch_end = min(
                        batch_start + timedelta(days=29),
                        date_to,
                    )

                    _LOGGER.info(
                        "Importing meter %s, batch %s to %s",
                        meter_id,
                        batch_start,
                        batch_end,
                    )

                    profile_data = await hass.async_add_executor_job(
                        api.get_smartdata_profile,
                        str(meter_id),
                        batch_start.isoformat(),
                        batch_end.isoformat(),
                        180,
                    )

                    if profile_data:
                        import_meter_profile_statistics(
                            hass,
                            str(meter_id),
                            profile_data,
                        )
                        total_records += len(profile_data)
                    else:
                        _LOGGER.warning(
                            "Full history import returned an empty result for meter %s, "
                            "period %s to %s",
                            meter_id,
                            batch_start,
                            batch_end,
                        )

                    if batch_end >= date_to:
                        break

                    # The boundary date is included in both requests.
                    # Re-importing the same statistic timestamp is safe.
                    batch_start = batch_end

                _LOGGER.info(
                    "Full history import submitted for meter %s: %d records",
                    meter_id,
                    total_records,
                )

            except Exception:
                _LOGGER.exception(
                    "Full history import failed for meter %s",
                    meter_id,
                )
