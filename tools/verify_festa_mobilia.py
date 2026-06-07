# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Verify the Tabula Festorum Mobilium (f58 Julian / f59 Gregorian) against computus.

Movable feasts are fixed day-offsets from Easter (identical in both calendars):
    Septuagesima = Pascha - 63   (Sunday)
    Estomihi/Quinquagesima = Pascha - 49
    Ascensio = Pascha + 39
    Pentecostes = Pascha + 49
So independent of how the manuscript indexes the rows, every row must satisfy these
offsets. We parse the reconstructed Titan grid, read each feast's (month, day), and
count how many rows satisfy each offset — a structural verification of the table.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MON = {"januar": 1, "febr": 2, "februar": 2, "mart": 3, "martij": 3, "april": 4,
       "may": 5, "maij": 5, "junij": 6, "junius": 6, "novemb": 11, "novem": 11,
       "decemb": 12, "decem": 12}
CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]  # non-leap, day-of-year


def doy(m: int, d: int) -> int:
    return CUM[m - 1] + d


def parse_day(tok: str):
    """Return (month_or_None, day_or_None) from a messy cell like '1. May', '23.', 'Febr:'."""
    if not tok:
        return None, None
    low = tok.lower()
    mon = None
    for name, mm in MON.items():
        if name in low:
            mon = mm
            break
    nums = re.findall(r"\d+", tok)
    day = int(nums[0]) if nums else None
    return mon, day


def column_dates(grid, col, init_month):
    """Walk a column top→bottom, rolling the month forward; return {row_index: doy}."""
    out = {}
    cur = init_month
    for i, row in enumerate(grid):
        tok = row["cells"][col] if col < len(row["cells"]) else ""
        mon, day = parse_day(tok)
        if mon is not None:
            cur = mon
        if day is not None and 1 <= day <= 31:
            out[i] = doy(cur, day)
    return out


def verify(path, cols, names):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    grid = data["grid"]
    # columns: dict name -> (col_index, init_month)
    series = {n: column_dates(grid, c, m) for n, (c, m) in cols.items()}
    pascha = series["Pascha"]
    checks = {"Septuagesima": -63, "Estomihi": -49, "Ascensio": +39, "Pentecostes": +49}
    print(f"\n=== {path} ===")
    tot_ok = tot = 0
    for feast, off in checks.items():
        s = series.get(feast, {})
        ok = n = 0
        for i, e in pascha.items():
            if i in s:
                n += 1
                # account for possible year wrap (Septuagesima may be prev year doy)
                exp = e + off
                if abs(s[i] - exp) == 0:
                    ok += 1
        print(f"  {feast:13s} = Pascha {off:+d}:  {ok}/{n} řádků sedí")
        tot_ok += ok
        tot += n
    print(f"  CELKEM: {tot_ok}/{tot} ({100*tot_ok//max(tot,1)} %)")
    return tot_ok, tot


if __name__ == "__main__":
    # column index + initial (header) month per table, from the reconstructed grids
    F58 = {"Septuagesima": (2, 1), "Estomihi": (3, 2), "Pascha": (5, 3),
           "Ascensio": (6, 4), "Pentecostes": (7, 5)}
    F59 = {"Septuagesima": (2, 1), "Estomihi": (3, 2), "Pascha": (4, 3),
           "Ascensio": (6, 4), "Pentecostes": (7, 5)}
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "work/orloj1587/transkribus_pull/titan")
    verify(base / "0058.grid.json", F58, "f58")
    verify(base / "0059.grid.json", F59, "f59")
