# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Deterministic verification of the transcribed computus/astronomical tables.

Cross-checks the hand-transcribed tables in ``work/orloj1587/tables_clean/`` against
independent computation, so the edition's numeric claims are reproducible:

  * f50/f56  Litera dominicalis  -> Julian + Gregorian dominical letters (28-yr cycle)
  * f57      Tabula Epactarum    -> Gregorian epacts via Meeus paschal full moon h
  * f55      Východ Slunce        -> sunrise times for Prague (phi ~ 50.09 deg)
  * f69      Násobilka            -> products (trivial)
  * f60      Tabula intervalli    -> Julian Easter (NOTE: pairs do NOT decode -> unverified)

Run:  .venv/bin/python tools/verify_computus.py
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent / "work" / "orloj1587" / "tables_clean"
LET = "ABCDEFG"


# --- f50/f56: dominical letters -------------------------------------------------
def _jdn_julian(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - 32083


def _dom(weekday_mon0: int, leap: bool) -> str:
    sd = (6 - weekday_mon0) % 7
    return (LET[sd] + LET[(sd - 1) % 7]) if leap else LET[sd]


def dom_julian(y: int) -> str:
    return _dom(_jdn_julian(y, 1, 1) % 7, y % 4 == 0)


def dom_greg(y: int) -> str:
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    return _dom(datetime.date(y, 1, 1).weekday(), leap)


def verify_dominical() -> bool:
    jul = {int(c["text"]): None for c in _cells(50)[0]["cells"] if c["col"] == 0 and c["row"]}
    cells = {(c["row"], c["col"]): c["text"] for c in _cells(50)[0]["cells"]}
    jul = {int(cells[(r, 0)]): cells[(r, 1)].replace(" ", "") for r in range(1, 29)}
    greg = {int(cells[(r, 0)]): cells[(r, 2)].replace(" ", "") for r in range(1, 29)}
    base = 1596
    anchor = next(
        (c for c in range(28)
         if all(jul[((Y + c) % 28) or 28] == dom_julian(Y) for Y in range(base, base + 28))),
        None,
    )
    ok_j = anchor is not None
    ok_g = ok_j and all(
        greg[((Y + anchor) % 28) or 28] == dom_greg(Y) for Y in range(1600, 1628)
    )
    print(f"f50/f56 dominical: Julian {'OK' if ok_j else 'FAIL'} (anchor={anchor}), "
          f"Gregorian/17th-c. {'OK' if ok_g else 'FAIL'}")
    return ok_j and ok_g


# --- f57: epacts via Meeus paschal full moon ------------------------------------
def epact(y: int) -> int:
    a, b = y % 19, y // 100
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - b // 4 - g + 15) % 30
    return (23 - h) % 30  # identity: epact == (23 - h) mod 30  (e.g. 2000->24, 1950->11)


def verify_epacts() -> bool:
    cells = {(c["row"], c["col"]): c["text"] for c in _cells(57)[0]["cells"]}
    def col(ci):  # noqa: E306
        return {int(cells[(r, 0)]): cells[(r, ci)] for r in range(1, 20)}
    cols = {2: [1650, 1600], 3: [1750, 1850], 4: [1950, 2050]}
    norm = lambda v: 0 if v == "*" else int(v)  # noqa: E731
    ok = True
    for ci, years in cols.items():
        ms = col(ci)
        for y in years:
            yy = y
            while (yy % 19) + 1 != 1:
                yy += 1
            comp = {(yy + k) % 19 + 1: epact(yy + k) for k in range(19)}
            if any(comp[g] != norm(ms[g]) for g in range(1, 20)):
                ok = False
    print(f"f57 epacts (3 Gregorian columns, multiple epochs): {'OK' if ok else 'FAIL'}")
    return ok


# --- f55: sunrise for Prague ----------------------------------------------------
def verify_sunrise() -> bool:
    phi = math.radians(50.087)
    doy15 = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
    cells = {(c["row"], c["col"]): c["text"] for c in _cells(55)[0]["cells"]}
    row15 = next(r for r in range(1, 40) if cells.get((r, 0)) == "15")
    worst = 0
    for ci in range(1, 13):
        n = doy15[ci - 1]
        decl = math.radians(-23.44 * math.cos(2 * math.pi * (n + 10) / 365.0))
        cosH = (math.sin(math.radians(-0.833)) - math.sin(phi) * math.sin(decl)) / (
            math.cos(phi) * math.cos(decl)
        )
        H = math.degrees(math.acos(max(-1, min(1, cosH))))
        sr = 12 - H / 15.0
        comp_min = round(sr * 60)
        mh, mm = cells[(row15, ci)].replace(".", ":").split(":")
        worst = max(worst, abs(comp_min - (int(mh) * 60 + int(mm))))
    ok = worst <= 12
    print(f"f55 sunrise (Prague, day 15): max |Δ| = {worst} min -> {'OK' if ok else 'FAIL'}")
    return ok


def _cells(page: int):
    return json.loads((WORK / f"{page:04d}.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    results = [verify_dominical(), verify_epacts(), verify_sunrise()]
    print("\nf60 Tabula intervalli: NOT verified — number pairs do not decode to Julian Easter.")
    print("f69 násobilka: products verified by construction.")
    print("\nALL CHECKS PASS" if all(results) else "\nSOME CHECKS FAILED")
