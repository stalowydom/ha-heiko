"""Daily efficiency statistic: kWh per kelvin of indoor/outdoor temperature difference.

For every finished day it stores  energy used that day / (mean indoor temp - mean outdoor temp)
as the external statistic  heiko_thermal:kwh_na_stopien, dated on that same day (no bar for today).
Each day gets 24 hourly rows with the same value, so a statistics-graph with period: day and
stat_types: [mean] shows exactly the day's value.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

STATISTIC_ID = "heiko_thermal:kwh_na_stopien"
BACKFILL_DAYS = 120
MIN_DELTA_K = 1.0


def _metadata() -> dict:
    meta = {
        "has_sum": False,
        "name": "Pompa ciepła – kWh na stopień",
        "source": "heiko_thermal",
        "statistic_id": STATISTIC_ID,
        "unit_class": None,
        "unit_of_measurement": "kWh/K",
    }
    try:
        from homeassistant.components.recorder.models import StatisticMeanType

        meta["mean_type"] = StatisticMeanType.ARITHMETIC
    except ImportError:  # older HA
        meta["has_mean"] = True
    return meta


async def _update(hass: HomeAssistant, energy: str, indoor: str, outdoor: str, days: int) -> None:
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import (
        async_add_external_statistics,
        statistics_during_period,
    )

    today = dt_util.start_of_local_day()
    start = today - timedelta(days=days)
    data = await get_instance(hass).async_add_executor_job(
        statistics_during_period, hass, start, today, {energy, indoor, outdoor}, "day", None, {"change", "mean"}
    )

    per_day: dict[float, dict[str, float]] = {}
    for sid, rows in data.items():
        for row in rows:
            value = row.get("change") if sid == energy else row.get("mean")
            if value is not None:
                per_day.setdefault(row["start"], {})[sid] = value

    stats = []
    for ts, vals in sorted(per_day.items()):
        if len(vals) < 3:
            continue
        delta = vals[indoor] - vals[outdoor]
        if delta <= MIN_DELTA_K:
            continue
        value = round(vals[energy] / delta, 3)
        day = dt_util.as_local(datetime.fromtimestamp(ts, dt_util.UTC))
        hour = day
        while hour.date() == day.date() and hour < today:
            stats.append({"start": dt_util.as_utc(hour), "mean": value, "min": value, "max": value})
            hour = dt_util.as_local(dt_util.as_utc(hour) + timedelta(hours=1))

    if stats:
        async_add_external_statistics(hass, _metadata(), stats)
        _LOGGER.debug("kWh/K: wrote %d hourly rows", len(stats))


def async_setup_efficiency(hass: HomeAssistant, conf: dict) -> None:
    energy, indoor, outdoor = conf["energy"], conf["indoor"], conf["outdoor"]

    async def _run(days: int) -> None:
        try:
            await _update(hass, energy, indoor, outdoor, days)
        except Exception:  # noqa: BLE001 - statistics must never break the integration
            _LOGGER.exception("kWh/K statistic update failed")

    async def _daily(_now) -> None:
        await _run(3)

    async def _startup(_now) -> None:
        await _run(BACKFILL_DAYS)

    # hourly statistics for the finished day are compiled a few minutes after midnight
    async_track_time_change(hass, _daily, hour=0, minute=20, second=0)
    async_call_later(hass, 120, _startup)
