"""Sensors for the Heiko Thermal heat pump (USR-W600 push frames)."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .listener import LIVE_FIELDS, HeikoListener

_LOGGER = logging.getLogger(__name__)

# not identified yet but changing (40, 41) or 0/1 flags (pumps, valve, heaters?) - kept visible to learn them
RAW_ENABLED = {0, 1, 3, 4, 14, 15, 17, 18, 19, 20, 40, 41}
# discrete fields (mode, flags, pumps, defrost, firmware) are published as int, so states are "1", not "1.0"
INT_FIELDS = {0, 1, 2, 3, 4, 14, 15, 16, 17, 18, 19, 20, 33, 34, 35, 36, 38}

_T = ("°C", "temperature", "measurement")
_P = ("bar", "pressure", "measurement")

# index -> (key, name, unit, device_class, state_class), matched against the pump display
LIVE_MAP: dict[int, tuple[str, str, str | None, str | None, str | None]] = {
    # working mode: 0 = standby, 1 = DHW, 2 = space heating (from flag log, Oct-Nov 2026)
    2: ("dhw_mode", "Tryb pracy", None, None, None),
    5: ("tuo", "Tuo woda wyjście", *_T),
    6: ("tui", "Tui woda wejście", *_T),
    7: ("tup", "Tup woda za skraplaczem", *_T),
    8: ("tw", "TW zasobnik CWU", *_T),
    9: ("tc", "Tc bufor", *_T),
    # circulation pump: 13 = control signal (0/100 when idle, ~28-35 while compressor runs), 16 = running (idle: ~1 min every ~6 min)
    13: ("circ_pump_signal", "Pompa obiegowa sygnał", None, None, "measurement"),
    16: ("circ_pump", "Pompa obiegowa praca", None, None, None),
    10: ("tv1", "Tv1 obieg 1", *_T),
    11: ("tv2", "Tv2 obieg 2", *_T),
    12: ("tr", "Temperatura pokojowa", *_T),
    21: ("compressor_hz", "Sprężarka częstotliwość", "Hz", "frequency", "measurement"),
    22: ("eev", "Zawór rozprężny otwarcie", "P", None, "measurement"),
    23: ("pd", "Pd ciśnienie tłoczenia", *_P),
    24: ("ps", "Ps ciśnienie ssania", *_P),
    25: ("ambient", "Temperatura zewnętrzna", *_T),
    26: ("td", "Td temperatura tłoczenia", *_T),
    27: ("ts", "Ts temperatura ssania", *_T),
    28: ("tp", "Tp temperatura parownika", *_T),
    29: ("fan1", "Wentylator 1", "rpm", None, "measurement"),
    30: ("fan2", "Wentylator 2", "rpm", None, "measurement"),
    31: ("compressor_a", "Sprężarka prąd", "A", "current", "measurement"),
    32: ("voltage", "Napięcie zasilania", "V", "voltage", "measurement"),
    # 1 only with compressor running in frost -> defrost cycle
    33: ("defrost", "Odszranianie", None, None, None),
    34: ("pump_p0", "Pompa P0", None, None, None),
    35: ("pump_p1", "Pompa P1", None, None, None),
    # set point of the current mode: DHW set (e.g. 50) while heating DHW, Tc set (e.g. 29) otherwise
    37: ("set_temp", "Temperatura zadana (bieżący tryb)", *_T[:2], None),
    38: ("software", "Wersja oprogramowania", None, None, None),
    39: ("compressor_calc", "Sprężarka prędkość obliczona", None, None, "measurement"),
    # heater run-time counters (MyHeatPump: AH / HWTBH / HBH Working Time) - growth = heater ran
    42: ("ah_minutes", "Grzałka AH czas pracy", "min", "duration", "total_increasing"),
    43: ("hwtbh_minutes", "Grzałka HWTBH czas pracy", "min", "duration", "total_increasing"),
    44: ("hbh_minutes", "Grzałka HBH czas pracy", "min", "duration", "total_increasing"),
}

async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    if discovery_info is None:
        _LOGGER.error("heiko_thermal: przenieś konfigurację z 'sensor: - platform: heiko_thermal' do sekcji 'heiko_thermal:'")
        return
    listener: HeikoListener = hass.data[DOMAIN]
    entities: list[SensorEntity] = [HeikoLiveSensor(listener, i) for i in range(LIVE_FIELDS)]
    entities.append(HeikoSettingsSensor(listener))
    async_add_entities(entities)


class HeikoLiveSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(self, listener: HeikoListener, index: int) -> None:
        self._l, self._i = listener, index
        key, name, unit, dclass, sclass = LIVE_MAP.get(index, (f"pole_{index:02d}", f"Pole {index:02d}", None, None,
                                                             "measurement" if index in (40, 41) else None))
        self._attr_name = f"Heiko {name}"
        self._attr_unique_id = f"heiko_thermal_{key}"
        # unidentified fields stay available but hidden from the UI by default
        self._attr_entity_registry_enabled_default = index in LIVE_MAP or index in RAW_ENABLED
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dclass
        self._attr_state_class = sclass
        listener.register(self)

    @property
    def available(self) -> bool:
        return self._l.available and len(self._l.live) > self._i

    @property
    def native_value(self):
        if len(self._l.live) <= self._i:
            return None
        v = self._l.live[self._i]
        return int(round(v)) if self._i in INT_FIELDS else round(v, 2)


class HeikoSettingsSensor(SensorEntity):
    """Settings frame as attributes (changes rarely)."""

    _attr_should_poll = False
    _attr_name = "Heiko ustawienia"
    _attr_unique_id = "heiko_thermal_settings"
    _attr_icon = "mdi:tune"

    def __init__(self, listener: HeikoListener) -> None:
        self._l = listener
        listener.register(self)

    @property
    def available(self) -> bool:
        return self._l.settings_available

    @property
    def native_value(self):
        return len(self._l.settings) if self._l.settings else None

    @property
    def extra_state_attributes(self):
        return {f"p{i:03d}": round(v, 2) for i, v in enumerate(self._l.settings)}
