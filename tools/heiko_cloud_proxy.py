#!/usr/bin/env python3
"""Przezroczysty pośrednik między USR-W600 (Socket B) a chmurą MyHeatPump. Loguje ruch w obie strony.

Cel: podejrzeć ramki, które chmura wysyła do pompy, gdy w aplikacji zmieniasz tryb albo temperaturę.
Pośrednik niczego nie zmienia i niczego sam nie wysyła. Przekazuje bajty 1:1, więc aplikacja i portal działają normalnie.

Użycie (na komputerze/serwerze w sieci lokalnej, np. 192.168.1.10):
  python3 heiko_cloud_proxy.py                         # słucha na :18899, przekazuje do www.myheatpump.com:18899
  python3 heiko_cloud_proxy.py --log ruch.log

Potem w panelu USR-W600 ustaw Socket B: TCP Client -> 192.168.1.10 : 18899 (zamiast www.myheatpump.com).
Zapisz stare ustawienia, żeby je przywrócić po zebraniu danych.

W logu:
  UP   = moduł -> chmura (ramki live/ustawień, znane)
  DOWN = chmura -> moduł (komendy z aplikacji, tego szukamy)
Zmieniaj w aplikacji jedną rzecz naraz i zapisz godzinę, np. 15:02 Auto -> Heating, 15:05 Heating -> Auto.
"""
import argparse
import asyncio
import datetime
import struct
import sys

p = argparse.ArgumentParser()
p.add_argument("--listen", default="0.0.0.0")
p.add_argument("--port", type=int, default=18899)
p.add_argument("--cloud", default="www.myheatpump.com")
p.add_argument("--cloud-port", type=int, default=18899)
p.add_argument("--log", default="heiko_cloud_proxy.log")
a = p.parse_args()

log = open(a.log, "a", encoding="utf-8")


def out(line: str) -> None:
    print(line, flush=True)
    log.write(line + "\n")
    log.flush()


def describe(data: bytes) -> str:
    """Opis ramki AA 55: typ i (gdy da się) liczby float32."""
    if len(data) >= 15 and data[:2] == b"\xaa\x55":
        ln = struct.unpack_from("<H", data, 10)[0]
        body = data[15:-3]
        info = f"ramka AA55 typ={data[12]} dl={ln}"
        if 0 < len(body) <= 64 and len(body) % 4 == 0:
            info += " float=" + ",".join(f"{x:g}" for x in struct.unpack(f"<{len(body)//4}f", body))
        return info
    return ""


async def pipe(reader, writer, tag: str, verbose_up: bool) -> None:
    try:
        while data := await reader.read(4096):
            writer.write(data)
            await writer.drain()
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d = describe(data)
            # UP: live (typ 1) co 10 s i ustawienia (typ 2) skracamy, żeby nie zalać logu
            if tag == "UP" and not verbose_up and len(data) > 64:
                out(f"{now} UP   {len(data)} B {d}")
            else:
                out(f"{now} {tag:4s} {len(data)} B {d}\n    {data.hex(' ')}")
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()


async def handle(m_reader, m_writer) -> None:
    peer = m_writer.get_extra_info("peername")
    out(f"--- moduł połączony z {peer}, łączę z {a.cloud}:{a.cloud_port}")
    try:
        c_reader, c_writer = await asyncio.wait_for(asyncio.open_connection(a.cloud, a.cloud_port), 15)
    except Exception as err:  # noqa: BLE001
        out(f"--- brak połączenia z chmurą: {err}")
        m_writer.close()
        return
    await asyncio.gather(pipe(m_reader, c_writer, "UP", False), pipe(c_reader, m_writer, "DOWN", True))
    out("--- rozłączono")


async def main() -> None:
    srv = await asyncio.start_server(handle, a.listen, a.port)
    out(f"słucham na {a.listen}:{a.port}, przekazuję do {a.cloud}:{a.cloud_port}, log: {a.log}")
    async with srv:
        await srv.serve_forever()


try:
    asyncio.run(main())
except KeyboardInterrupt:
    sys.exit(0)
