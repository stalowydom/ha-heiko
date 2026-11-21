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

# only these may be written; anything else would need a new capture first
WRITABLE = {
    P_POWER: {0.0, 1.0},
    P_MODE: {MODE_HEATING, MODE_COOLING, MODE_DHW, MODE_AUTO},
}
