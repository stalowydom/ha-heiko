"""Frames captured from the MyHeatPump cloud on 2026-11-15 (MAC replaced by an example one) must be rebuilt byte for byte."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "heiko_thermal"))
from protocol import build_command, build_write, crc16_modbus  # noqa: E402

MAC = bytes.fromhex("0a1b2c3d4e5f")  # example MAC (frames re-encoded from a capture)
CAPTURED = {
    (3, 4.0): "55 aa 01 0a 1b 2c 3d 4e 5f 01 07 00 05 03 00 00 00 80 40 18 16 3a",  # Auto
    (3, 1.0): "55 aa 01 0a 1b 2c 3d 4e 5f 01 07 00 05 03 00 00 00 80 3f 59 f6 3a",  # Heating
    (3, 2.0): "55 aa 01 0a 1b 2c 3d 4e 5f 01 07 00 05 03 00 00 00 00 40 79 d6 3a",  # Cooling
    (3, 3.0): "55 aa 01 0a 1b 2c 3d 4e 5f 01 07 00 05 03 00 00 00 40 40 48 16 3a",  # DHW only
    (0, 0.0): "55 aa 01 0a 1b 2c 3d 4e 5f 01 07 00 05 00 00 00 00 00 00 78 15 3a",  # Standby
    (0, 1.0): "55 aa 01 0a 1b 2c 3d 4e 5f 01 07 00 05 00 00 00 00 80 3f 59 c5 3a",  # On
}


def test_writes():
    for (idx, val), hexs in CAPTURED.items():
        assert build_write(MAC, idx, val) == bytes.fromhex(hexs), (idx, val)


def test_acks():
    assert build_command(MAC, 3) == bytes.fromhex("55aa010a1b2c3d4e5f01010003f9983a")
    assert build_command(MAC, 4) == bytes.fromhex("55aa010a1b2c3d4e5f01010004b85a3a")
    hello = bytes.fromhex("55aa0000000000000001010006d6da3a")  # sent by the cloud on connect, byte 2 = 00
    assert crc16_modbus(hello[2:-3]) == int.from_bytes(hello[-3:-1], "little")


if __name__ == "__main__":
    test_writes(); test_acks(); print("OK", crc16_modbus(b"123456789") == 0x4B37)


def test_cloud_acks_rebuild_byte_exact():
    """Acknowledgements the cloud sends after live (03) and settings (04) frames."""
    mac = bytes.fromhex("0a1b2c3d4e5f")
    for cmd in (3, 4):
        frame = build_command(mac, cmd)
        assert frame[:2] == b"\x55\xaa" and frame[-1] == 0x3A and frame[12] == cmd
        assert frame[10:12] == b"\x01\x00"
        assert int.from_bytes(frame[13:15], "little") == crc16_modbus(frame[2:13])
