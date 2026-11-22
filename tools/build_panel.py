#!/usr/bin/env python3
"""Buduje examples/dashboard/pompa_ciepla_panel.yaml z tools/panel_szablon.yaml i examples/dashboard/schemat.svg.

Schemat jest osadzany jako data URI, więc panel działa bez kopiowania plików do /config/www.
Użycie: python3 tools/build_panel.py
"""
import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
svg = (ROOT / "examples" / "dashboard" / "schemat.svg").read_bytes()
tpl = (ROOT / "tools" / "panel_szablon.yaml").read_text(encoding="utf-8")
uri = "data:image/svg+xml;base64," + base64.b64encode(svg).decode()
out = ROOT / "examples" / "dashboard" / "pompa_ciepla_panel.yaml"
out.write_text(tpl.replace("__SCHEMAT__", uri), encoding="utf-8")
print("zapisano", out.relative_to(ROOT))
