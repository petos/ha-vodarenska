import logging
import math
import requests
from datetime import date, datetime, timedelta

from homeassistant.components.recorder.models import StatisticMeanType,StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfTemperature, UnitOfVolume
from homeassistant.core import HomeAssistant,ServiceCall
from homeassistant.util.unit_conversion import TemperatureConverter, VolumeConverter
from homeassistant.util import dt as dt_util

from homeassistant.components import persistent_notification
_NOTIFICATION_ID = "ha_vodarenska_full_history_import"

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_full_history_import_running = False


_TIMEOUT_HTTP_STATUS_CODES = {408, 499, 504}


def _is_timeout_error(exc: Exception) -> bool:
    """Return True for network timeouts and timeout-like HTTP responses."""

    if isinstance(exc, requests.Timeout):
        return True

    if isinstance(exc, requests.HTTPError):
        response = exc.response
        return (
            response is not None
            and response.status_code in _TIMEOUT_HTTP_STATUS_CODES
        )

    return False


async def _async_import_profile_range(
    hass,
    api,
    meter_id: str,
    date_from: date,
    date_to: date,
    batch_days: int,
) -> int:
    """Import profile data, reducing batch size after timeout."""

    pending = []
    current_start = date_from

    # Create the initial batches. The next batch starts at the previous
    # batch's end to preserve the existing one-day overlap.
    while current_start <= date_to:
        current_end = min(
            current_start + timedelta(days=batch_days - 1),
            date_to,
        )
        pending.append((current_start, current_end, batch_days))

        if current_end >= date_to:
            break

        current_start = current_end

    total_records = 0

    while pending:
        batch_start, batch_end, current_batch_days = pending.pop(0)

        actual_batch_days = (batch_end - batch_start).days + 1
        effective_batch_days = min(current_batch_days, actual_batch_days)

        try:
            profile_data = await hass.async_add_executor_job(
                api.get_smartdata_profile,
                str(meter_id),
                batch_start.isoformat(),
                batch_end.isoformat(),
                180,
            )

        except Exception as exc:
            if not _is_timeout_error(exc):
                raise

            if effective_batch_days <= 4:
                _LOGGER.error(
                    "Profile import failed for meter %s, date range %s..%s. "
                    "Timeout persists at minimum batch size (%s days).",
                    meter_id,
                    batch_start,
                    batch_end,
                    effective_batch_days,
                )
                raise

            next_batch_days = max(
                4,
                math.ceil(effective_batch_days / 2),
            )

            _LOGGER.warning(
                "Timeout importing meter %s, date range %s..%s "
                "with batch size %s days. Retrying with %s-day batches.",
                meter_id,
                batch_start,
                batch_end,
                effective_batch_days,
                next_batch_days,
            )

            # Split only the failed range. Keep the one-day overlap.
            smaller_batches = []
            sub_start = batch_start

            while sub_start <= batch_end:
                sub_end = min(
                    sub_start + timedelta(days=next_batch_days - 1),
                    batch_end,
                )
                smaller_batches.append(
                    (sub_start, sub_end, next_batch_days)
                )

                if sub_end >= batch_end:
                    break

                sub_start = sub_end

            # Process the smaller batches before the remaining queue.
            pending[0:0] = smaller_batches
            continue

        if profile_data:
            import_meter_profile_statistics(
                hass,
                str(meter_id),
                profile_data,
            )
            total_records += len(profile_data)
        else:
            _LOGGER.warning(
                "No profile data found for meter %s, date range %s..%s",
                meter_id,
                batch_start,
                batch_end,
            )

    return total_records

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
    """Start full history import in the background."""

    global _full_history_import_running

    if _full_history_import_running:
        _LOGGER.warning(
            "Full history import is already running; ignoring new request"
        )
        persistent_notification.async_create(
            hass,
            message="Import historie vodoměrů právě probíhá, nepouštím další.",
            title="Vodárenská integrace",
            notification_id=_NOTIFICATION_ID,
        )
        return

    _full_history_import_running = True

    async def run_import():
        global _full_history_import_running

        try:
            await _async_run_full_history_import(hass, call)
        except Exception:
            _LOGGER.exception("Full history import failed")
            persistent_notification.async_create(
                hass,
                message="Import historie vodoměrů selhal. Podrobnosti jsou v logu Home Assistantu.",
                title="Vodárenská integrace - chyba importu",
                notification_id=_NOTIFICATION_ID,
            )
        else:
            persistent_notification.async_create(
                hass,
                message="Import historie všech vodoměrů úspěšně doběhl.",
                title="Vodárenská integrace",
                notification_id=_NOTIFICATION_ID,
            )
        finally:
            _full_history_import_running = False

    hass.async_create_task(run_import())

async def _async_run_full_history_import(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Import complete available history in configurable batches."""

    entries = hass.config_entries.async_entries(DOMAIN)

    from_value = call.data.get("from")
    to_value = call.data.get("to")

    date_to = (
        date.fromisoformat(str(to_value))
        if to_value
        else dt_util.now().date()
    )

    for config_entry in entries:
        data = hass.data[DOMAIN].get(config_entry.entry_id)
        if not data:
            continue

        api = data["api"]
        meters = data["meters_coordinator"].data

        for meter_id, meter_data in meters.items():
            meter = meter_data.get("meter", {})
            date_from_value = meter.get("METER_DATE_FROM")

            if not from_value and not date_from_value:
                _LOGGER.warning(
                    "Cannot import full history for meter %s: "
                    "METER_DATE_FROM is missing",
                    meter_id,
                )
                continue

            try:
                # METER_DATE_FROM may contain a date or a timestamp.
                date_from = (
                    date.fromisoformat(str(from_value))
                    if from_value
                    else date.fromisoformat(str(date_from_value)[:10])
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

                batch_days = int(call.data.get("batch_days", 28))

                if batch_days < 4:
                    raise ValueError(
                        f"Invalid batch_days value: {batch_days}. "
                        "Minimum allowed value is 4."
                    )

                _LOGGER.info(
                    "Starting full history import for meter %s: %s to %s "
                    "(initial batch size: %d days)",
                    meter_id,
                    date_from,
                    date_to,
                    batch_days,
                )

                total_records = 0
                batch_start = date_from

                while batch_start <= date_to:
                    batch_end = min(
                        batch_start + timedelta(days=batch_days - 1),
                        date_to,
                    )

                    total_records += await _async_import_profile_range(
                        hass,
                        api,
                        str(meter_id),
                        batch_start,
                        batch_end,
                        batch_days,
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
