"""Heiko Thermal heat pump over the USR-W600 module (Socket A, local).

Reads the frames the pump pushes. With allow_write: true it can also switch the pump on/off and change
the working mode, using the same write frames the MyHeatPump cloud sends (captured 2026-11-15).
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ALLOW_WRITE, DOMAIN
from .listener import HeikoListener

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=8899): cv.port,
                vol.Optional(CONF_ALLOW_WRITE, default=False): cv.boolean,
                # answer pump frames like the MyHeatPump cloud (needed for writes without the cloud)
                vol.Optional("emulate_cloud", default=True): cv.boolean,
                # optional daily statistic kWh per kelvin (energy meter + indoor/outdoor temperature)
                vol.Optional("efficiency"): vol.Schema(
                    {
                        vol.Required("energy"): cv.entity_id,
                        vol.Required("indoor"): cv.entity_id,
                        vol.Required("outdoor"): cv.entity_id,
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    conf = config.get(DOMAIN)
    if conf is None:
        return True
    listener = HeikoListener(
        hass, conf[CONF_HOST], conf[CONF_PORT], conf[CONF_ALLOW_WRITE], conf["emulate_cloud"]
    )
    hass.data[DOMAIN] = listener
    platforms = [Platform.SENSOR]
    if conf[CONF_ALLOW_WRITE]:
        platforms += [Platform.SELECT, Platform.SWITCH]
    for platform in platforms:
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {}, config))
    listener.start()
    if "efficiency" in conf:
        from .efficiency import async_setup_efficiency

        async_setup_efficiency(hass, conf["efficiency"])
    return True
