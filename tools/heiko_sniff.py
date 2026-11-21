#!/usr/bin/env python3
"""Podgląd ramek z pompy Heiko przez moduł USR-W600 (tylko odczyt, nic nie wysyła).

Użycie:
  python3 heiko_sniff.py 192.168.1.50            # tabela pól ramki live (typ 1), odświeżana co ramkę
  python3 heiko_sniff.py 192.168.1.50 --changes  # tylko pola, które się zmieniły
  python3 heiko_sniff.py 192.168.1.50 --settings # ramka ustawień (typ 2, co 60 s)
  python3 heiko_sniff.py 192.168.1.50 --csv live.csv  # zapis każdej ramki live do CSV

Przydaje się do sprawdzenia mapowania pól: porównaj wartości z wyświetlaczem pompy
albo z portalem MyHeatPump w tej samej chwili.
"""
import argparse
import csv
import datetime
import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "heiko_thermal"))
from protocol import extract_frames  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("host")
p.add_argument("--port", type=int, default=8899)
p.add_argument("--changes", action="store_true")
p.add_argument("--settings", action="store_true")
p.add_argument("--csv")
a = p.parse_args()
sys.stdout.reconfigure(line_buffering=True)

want = 2 if a.settings else 1
prev = None
writer = None
if a.csv:
    f = open(a.csv, "a", newline="")
    writer = csv.writer(f)

s = socket.create_connection((a.host, a.port), timeout=120)
print(f"połączono z {a.host}:{a.port}, czekam na ramki (live co 10 s, ustawienia co 60 s)…")
buf = bytearray()
while True:
    data = s.recv(4096)
    if not data:
        sys.exit("moduł zamknął połączenie")
    buf += data
    for ftype, v in extract_frames(buf):
        if ftype != want:
            continue
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if writer:
            writer.writerow([now] + [round(x, 2) for x in v])
            f.flush()
        if a.changes and prev:
            ch = [f"{i}: {prev[i]:g} -> {x:g}" for i, x in enumerate(v) if round(x, 2) != round(prev[i], 2)]
            print(now, " | ".join(ch) if ch else "(bez zmian)")
        else:
            print(f"\n{now}  typ {ftype}, {len(v)} pól")
            for i in range(0, len(v), 6):
                print("  ".join(f"{j:3d}:{v[j]:8.2f}" for j in range(i, min(i + 6, len(v)))))
        prev = v
