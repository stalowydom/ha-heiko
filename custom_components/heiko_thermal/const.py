"""Constants for the Heiko Thermal integration."""

DOMAIN = "heiko_thermal"
CONF_ALLOW_WRITE = "allow_write"

# settings frame (type 2) parameters confirmed by capturing MyHeatPump commands (2026-11-15)
P_POWER = 0  # 0 = standby, 1 = on
P_MODE = 3  # working mode
MODE_HEATING = 1.0
MODE_COOLING = 2.0
MODE_DHW = 3.0  # hot water only
MODE_AUTO = 4.0  # heating + DHW ("Auto" in the app)

# temperature settings; index = MyHeatPump web field "parN" minus 1 (checked against the web panel 2026-11-22)
P_HEAT_SET = 37  # par38 "Set temp. for Heating (without heating curve)", deg C
P_HEAT_RESTART = 20  # par21 "Heating/Cooling Restarts Based on Water dT", K
P_DHW_SET = 54  # par55 "Setpoint DHW", deg C
P_DHW_RESTART = 55  # par56 "DHW Restart dT Setting", K

# only these may be written; anything else would need a new capture first
WRITABLE = {
    P_POWER: {0.0, 1.0},
    P_MODE: {MODE_HEATING, MODE_COOLING, MODE_DHW, MODE_AUTO},
}

# numeric settings: index -> (key, name, min, max, step, unit); writes outside the range are refused
NUMBERS = {
    P_HEAT_SET: ("temp_co", "temperatura CO", 20.0, 55.0, 1.0, "°C"),
    P_HEAT_RESTART: ("histereza_co", "histereza CO", 2.0, 10.0, 1.0, "K"),
    P_DHW_SET: ("temp_cwu", "temperatura CWU", 35.0, 55.0, 1.0, "°C"),
    P_DHW_RESTART: ("histereza_cwu", "histereza CWU", 2.0, 15.0, 1.0, "K"),
}


def is_writable(index: int, value: float) -> bool:
    """True for whitelisted discrete values and for whole numbers inside a NUMBERS range."""
    if value in WRITABLE.get(index, set()):
        return True
    if index in NUMBERS:
        _key, _name, lo, hi, step, _unit = NUMBERS[index]
        return lo <= value <= hi and abs(round(value / step) * step - value) < 1e-6
    return False
