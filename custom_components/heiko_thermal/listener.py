"""TCP link to the USR-W600 (Socket A): reads pushed frames, optionally writes confirmed settings."""
from __future__ import annotations

import asyncio
import logging
import os
import time

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util

from .const import WRITABLE
from .protocol import build_command, build_write, extract_frames_ex

# The MyHeatPump cloud answers every pump frame with a short acknowledgement:
# cmd 03 after a live frame (type 1), cmd 04 after a settings frame (type 2).
# Without them (cloud down, or cloud disconnected on purpose) the pump stops accepting
# writes, so the listener can send the same acknowledgements itself.
ACK_CMD = {1: 0x03, 2: 0x04}

_LOGGER = logging.getLogger(__name__)

LIVE_FIELDS = 45
WRITE_INTERVAL = 30  # s, frames come every 10 s
STALE_AFTER = 90  # s without frames -> unavailable
CONFIRM_TIMEOUT = 15  # s; the pump answers a write with a settings frame after ~3 s

# unknown 0/1 flags: every change is appended to CHANGE_LOG with context, to identify them later
UNKNOWN_FLAGS = (0, 1, 3, 4, 14, 15, 17, 18, 19, 20)
CHANGE_LOG = "heiko_flag_changes.csv"
LOG_CONTEXT = {"hz": 21, "tuo": 5, "tui": 6, "tw": 8, "tc": 9, "amb": 25, "dhw": 2, "set": 37, "f40": 40, "f41": 41}


class HeikoListener:
    """Keeps a TCP connection to the USR-W600. Sends only whitelisted setting writes, and only if allowed."""

    def __init__(
        self, hass: HomeAssistant, host: str, port: int, allow_write: bool = False, emulate_cloud: bool = True
    ) -> None:
        self.hass, self.host, self.port, self.allow_write = hass, host, port, allow_write
        self.emulate_cloud = emulate_cloud
        self.live: list[float] = []
        self.settings: list[float] = []
        self.mac: bytes | None = None
        self.last_frame = 0.0
        self.last_settings = 0.0
        self._last_write = 0.0
        self._entities: list[Entity] = []
        self._task: asyncio.Task | None = None
        self._watchdog_handle: asyncio.TimerHandle | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._write_lock = asyncio.Lock()
        self._settings_event = asyncio.Event()

    # ---------- flag log ----------
    def _log_flag_changes(self, old: list[float], new: list[float]) -> None:
        changes = [(i, old[i], new[i]) for i in UNKNOWN_FLAGS if old[i] != new[i]]
        if not changes:
            return
        stamp = dt_util.now().isoformat(timespec="seconds")
        ctx = ";".join(f"{k}={round(new[i], 1)}" for k, i in LOG_CONTEXT.items())
        lines = "".join(f"{stamp},pole_{i:02d},{a:g},{b:g},{ctx}\n" for i, a, b in changes)
        self.hass.async_add_executor_job(self._append, lines)

    def _append(self, lines: str) -> None:
        path = self.hass.config.path(CHANGE_LOG)
        new_file = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if new_file:
                f.write("czas,pole,bylo,jest,kontekst\n")
            f.write(lines)

    # ---------- lifecycle ----------
    def register(self, entity: Entity) -> None:
        self._entities.append(entity)

    def start(self) -> None:
        self._task = self.hass.async_create_background_task(self._run(), "heiko_thermal_listener")
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._stop)
        self._watchdog()

    @callback
    def _stop(self, _event) -> None:
        if self._task:
            self._task.cancel()
        if self._watchdog_handle:
            self._watchdog_handle.cancel()
            self._watchdog_handle = None

    @callback
    def _watchdog(self, _now=None) -> None:
        # marks entities unavailable when frames stop
        self._push_states(force=True)
        self._watchdog_handle = self.hass.loop.call_later(STALE_AFTER / 3, self._watchdog)

    @property
    def available(self) -> bool:
        return self.last_frame > 0 and time.monotonic() - self.last_frame < STALE_AFTER

    @property
    def settings_available(self) -> bool:
        return bool(self.settings) and time.monotonic() - self.last_settings < 3 * STALE_AFTER

    async def _run(self) -> None:
        delay = 5
        while True:
            writer = None
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 10)
                _LOGGER.info("Connected to %s:%s", self.host, self.port)
                self._writer = writer
                delay = 5
                buf = bytearray()
                while True:
                    data = await asyncio.wait_for(reader.read(4096), STALE_AFTER)
                    if not data:
                        raise ConnectionError("connection closed")
                    buf += data
                    for ftype, values, mac in extract_frames_ex(buf):
                        self.mac = mac
                        self._handle(ftype, values)
                        if self.emulate_cloud and ftype in ACK_CMD:
                            writer.write(build_command(mac, ACK_CMD[ftype]))
                    if self.emulate_cloud:
                        await writer.drain()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Heiko connection problem (%s), retry in %ss", err, delay)
            finally:
                self._writer = None
                if writer:
                    writer.close()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 300)

    @callback
    def _handle(self, ftype: int, values: list[float]) -> None:
        if ftype == 1 and len(values) >= LIVE_FIELDS:
            if len(self.live) >= LIVE_FIELDS:
                self._log_flag_changes(self.live, values)
            self.live = values
            self.last_frame = time.monotonic()
            self._push_states()
        elif ftype == 2:
            self.settings = values
            self.last_settings = time.monotonic()
            self._settings_event.set()
            self._push_states(force=True)

    @callback
    def _push_states(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_write < WRITE_INTERVAL:
            return
        self._last_write = now
        for ent in self._entities:
            if ent.hass is not None:
                ent.async_write_ha_state()

    # ---------- writing ----------
    def setting(self, index: int) -> float | None:
        if not self.settings_available or len(self.settings) <= index:
            return None
        return self.settings[index]

    async def async_write_setting(self, index: int, value: float) -> None:
        """Write one setting the same way the MyHeatPump cloud does, then wait for the pump to confirm it."""
        if not self.allow_write:
            raise HomeAssistantError("Zapis wyłączony: ustaw allow_write: true w konfiguracji heiko_thermal")
        if value not in WRITABLE.get(index, set()):
            raise HomeAssistantError(f"Parametr p{index:03d} = {value} nie jest na liście dozwolonych zapisów")
        async with self._write_lock:
            for attempt in (1, 2):
                if self._writer is None or self.mac is None:
                    raise HomeAssistantError("Brak połączenia z modułem USR-W600")
                self._settings_event.clear()
                frame = build_write(self.mac, index, value)
                _LOGGER.info("Write p%03d = %s (attempt %s): %s", index, value, attempt, frame.hex(" "))
                self._writer.write(frame)
                await self._writer.drain()
                deadline = time.monotonic() + CONFIRM_TIMEOUT
                while (left := deadline - time.monotonic()) > 0:
                    try:
                        await asyncio.wait_for(self._settings_event.wait(), left)
                    except asyncio.TimeoutError:
                        break
                    self._settings_event.clear()
                    if len(self.settings) > index and abs(self.settings[index] - value) < 0.01:
                        _LOGGER.info("Pump confirmed p%03d = %s", index, value)
                        return
            raise HomeAssistantError(f"Pompa nie potwierdziła zapisu p{index:03d} = {value}")
