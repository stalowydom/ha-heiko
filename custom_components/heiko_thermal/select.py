"""Working mode of the pump (settings parameter p003), written locally through the USR-W600."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN, MODE_AUTO, MODE_COOLING, MODE_DHW, MODE_HEATING, P_MODE
from .listener import HeikoListener

# option label -> p003 value; labels are what automations use in select.select_option
MODES = {
    "Ogrzewanie": MODE_HEATING,
    "Auto (ogrzewanie + CWU)": MODE_AUTO,
    "CWU": MODE_DHW,
    "Chłodzenie": MODE_COOLING,
}


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    if discovery_info is None:
        return
    async_add_entities([HeikoModeSelect(hass.data[DOMAIN])])


class HeikoModeSelect(SelectEntity):
    _attr_should_poll = False
    _attr_name = "Heiko tryb pracy pompy"
    _attr_unique_id = "heiko_thermal_mode_select"
    _attr_icon = "mdi:heat-pump-outline"
    _attr_options = list(MODES)

    def __init__(self, listener: HeikoListener) -> None:
        self._l = listener
        listener.register(self)

    @property
    def available(self) -> bool:
        return self._l.settings_available

    @property
    def current_option(self) -> str | None:
        value = self._l.setting(P_MODE)
        if value is None:
            return None
        return next((name for name, v in MODES.items() if abs(v - value) < 0.01), None)

    @property
    def extra_state_attributes(self):
        return {"p003": self._l.setting(P_MODE)}

    async def async_select_option(self, option: str) -> None:
        await self._l.async_write_setting(P_MODE, MODES[option])
        self.async_write_ha_state()
