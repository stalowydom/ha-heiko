"""Pump on / standby (settings parameter p000), written locally through the USR-W600."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN, P_POWER
from .listener import HeikoListener


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    if discovery_info is None:
        return
    async_add_entities([HeikoPowerSwitch(hass.data[DOMAIN])])


class HeikoPowerSwitch(SwitchEntity):
    _attr_should_poll = False
    _attr_name = "Heiko pompa włączona"
    _attr_unique_id = "heiko_thermal_power"
    _attr_icon = "mdi:power"

    def __init__(self, listener: HeikoListener) -> None:
        self._l = listener
        listener.register(self)

    @property
    def available(self) -> bool:
        return self._l.settings_available

    @property
    def is_on(self) -> bool | None:
        value = self._l.setting(P_POWER)
        return None if value is None else value > 0.5

    async def async_turn_on(self, **kwargs) -> None:
        await self._l.async_write_setting(P_POWER, 1.0)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._l.async_write_setting(P_POWER, 0.0)
        self.async_write_ha_state()
