"""CO/DHW setpoints and restart hysteresis, written locally through the USR-W600 (allow_write: true)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NUMBERS
from .listener import HeikoListener


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    if discovery_info is None:
        return
    listener = hass.data[DOMAIN]
    async_add_entities([HeikoSettingNumber(listener, index) for index in NUMBERS])


class HeikoSettingNumber(NumberEntity):
    _attr_should_poll = False
    _attr_mode = NumberMode.BOX

    def __init__(self, listener: HeikoListener, index: int) -> None:
        key, name, lo, hi, step, unit = NUMBERS[index]
        self._l = listener
        self._index = index
        self._attr_name = f"Heiko {name}"
        self._attr_unique_id = f"heiko_thermal_{key}"
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = "mdi:thermometer" if unit == "°C" else "mdi:arrow-expand-vertical"
        listener.register(self)

    @property
    def available(self) -> bool:
        return self._l.settings_available

    @property
    def native_value(self) -> float | None:
        return self._l.setting(self._index)

    @property
    def extra_state_attributes(self):
        return {"parametr": f"p{self._index:03d}"}

    async def async_set_native_value(self, value: float) -> None:
        await self._l.async_write_setting(self._index, float(value))
        self.async_write_ha_state()
