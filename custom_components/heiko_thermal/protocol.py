"""Frame parser and command builder for the USR-W600 link (TCP server, port 8899).

Pump -> module (observed):
  AA 55 | 01 | MAC (6) | 01 | length u16 LE | type u8 | 2 bytes | float32 LE * n | 2 bytes | 3A
  total size = length + 15
  type 1: live data every 10 s (45 floats), type 2: settings every 60 s (138 floats)

Cloud -> pump (captured with tools/heiko_cloud_proxy.py, Nov 2026):
  55 AA | 01 | MAC (6) | 01 | length u16 LE | cmd u8 | payload | CRC16 LE | 3A
  CRC-16/MODBUS over the bytes from index 2 (after 55 AA) up to the CRC.
  cmd 05 + param index u16 LE + float32 LE = write one setting (length 7):
    p000 = 0.0 standby / 1.0 on,  p003 = 1.0 heating / 4.0 heating + DHW ("Auto")
  The pump answers a write with an extra settings frame (type 2) after ~3 s.
"""
from __future__ import annotations

import struct

HEADER = b"\xaa\x55"
CMD_HEADER = b"\x55\xaa"
HEADER_LEN = 15
TRAILER_LEN = 3
END = 0x3A
CMD_WRITE = 0x05


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def extract_frames_ex(buf: bytearray) -> list[tuple[int, list[float], bytes]]:
    """Pop complete frames from buf, return (type, values, mac) for each valid one."""
    frames = []
    while True:
        start = buf.find(HEADER)
        if start < 0:
            # keep a possible half header
            del buf[: max(0, len(buf) - 1)]
            return frames
        if start:
            del buf[:start]
        if len(buf) < HEADER_LEN:
            return frames
        total = struct.unpack_from("<H", buf, 10)[0] + HEADER_LEN
        if total < HEADER_LEN + TRAILER_LEN or total > 4096:
            del buf[:2]
            continue
        if len(buf) < total:
            return frames
        frame = bytes(buf[:total])
        del buf[:total]
        body = frame[HEADER_LEN:-TRAILER_LEN]
        if frame[-1] != END or len(body) % 4:
            continue
        values = list(struct.unpack(f"<{len(body) // 4}f", body))
        frames.append((frame[12], values, frame[3:9]))


def extract_frames(buf: bytearray) -> list[tuple[int, list[float]]]:
    """Pop complete frames from buf, return (type, values) for each valid one."""
    return [(t, v) for t, v, _mac in extract_frames_ex(buf)]


def build_command(mac: bytes, cmd: int, payload: bytes = b"") -> bytes:
    if len(mac) != 6:
        raise ValueError("MAC must be 6 bytes")
    body = b"\x01" + mac + b"\x01" + struct.pack("<H", 1 + len(payload)) + bytes([cmd]) + payload
    return CMD_HEADER + body + struct.pack("<H", crc16_modbus(body)) + bytes([END])


def build_write(mac: bytes, index: int, value: float) -> bytes:
    """Command writing one setting (same frame the MyHeatPump cloud sends)."""
    return build_command(mac, CMD_WRITE, struct.pack("<Hf", index, value))
