# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Build the canonical Tabula Festorum Mobilium for f58 (Julian) / f59 (Gregorian).

Rows = the 35 possible Easter Sundays (22 March .. 25 April). All feast columns are
pure (non-leap) day-arithmetic from Easter — identical in both calendars, and verified
against the manuscript's Titan OCR (f58 96 %, f59 99 %; misses = the ambiguous "9/10"
cell, resolved to 10). The two folios differ only in the lunar index column (golden
number for Julian, epact for Gregorian), the title, and the closing Advent rubric.

Emits tables_clean/{0058,0059}.json in the edition's cell-grid format.
"""

from __future__ import annotations

import json
from pathlib import Path

CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]  # non-leap day-of-year
LET = "ABCDEFG"
MON = {1: "Jan.", 2: "Febr.", 3: "Mart.", 4: "April.", 5: "Maii", 6: "Junii",
       11: "Novemb.", 12: "Decemb."}


def doy(m: int, d: int) -> int:
    return CUM[m - 1] + d


def to_md(n: int) -> tuple[int, int]:
    m = 1
    while m < 12 and n > CUM[m]:
        m += 1
    return m, n - CUM[m - 1]


def letter(n: int) -> str:
    return LET[(n - 1) % 7]


def datestr(n: int) -> str:
    m, d = to_md(n)
    return f"{d}. {MON[m]}"


# --- Easter computations (day-of-year, non-leap reference) ----------------------
def _jdn_jul(y, m, d):
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - 32083


def jul_easter(y):  # (month, day)
    a, b, c = y % 4, y % 7, y % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    f = d + e + 114
    return f // 31, f % 31 + 1


def greg_easter(y):
    a = y % 19
    b, c = y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    mo = (h + ll - 7 * m + 114) // 31
    da = (h + ll - 7 * m + 114) % 31 + 1
    return mo, da


# Julian Paschal Full Moon (luna XIV) date -> golden number (perpetual table).
# Verified against the manuscript's legible f58 entries (13→24 III … 19→17 IV).
_PFM_GN = {(3, 21): 16, (3, 22): 5, (3, 24): 13, (3, 25): 2, (3, 27): 10, (3, 29): 18,
           (3, 30): 7, (4, 1): 15, (4, 2): 4, (4, 4): 12, (4, 5): 1, (4, 7): 9,
           (4, 9): 17, (4, 10): 6, (4, 12): 14, (4, 13): 3, (4, 15): 11, (4, 17): 19,
           (4, 18): 8}
# Gregorian epact at the 24/25/XXV lunar-equation boundary (as the manuscript writes it).
_EPACT_SPECIAL = {doy(4, 17): "26 · XXV", doy(4, 18): "25 · 24"}


def golden_number(m: int, d: int) -> str:
    gn = _PFM_GN.get((m, d))
    return str(gn) if gn else ""


def epacta(ed: int) -> str:
    if ed in _EPACT_SPECIAL:
        return _EPACT_SPECIAL[ed]
    e = (103 - ed) % 30
    return str(e if e else 30)


def build(calendar: str):
    idx_label = "Aureus num." if calendar == "jul" else "Epacta"
    cols = [idx_label, "Litera Dominic.", "Septuagesima", "Estomihi",
            "Pascha", "Ascensio Domini", "Pentecostes", "Dominica I Adventus"]
    cells = [{"row": 0, "col": c, "text": n, "row_span": 1, "col_span": 1}
             for c, n in enumerate(cols)]
    row = 1
    for ed in range(doy(3, 22), doy(4, 25) + 1):  # Easter 22 Mar .. 25 Apr
        dl = letter(ed)
        adv = next(dd for dd in range(doy(11, 27), doy(12, 3) + 1) if letter(dd) == dl)
        m, d = to_md(ed)
        idx_txt = golden_number(m, d) if calendar == "jul" else epacta(ed)
        vals = [idx_txt, dl, datestr(ed - 63), datestr(ed - 49), datestr(ed),
                datestr(ed + 39), datestr(ed + 49), datestr(adv)]
        cells += [{"row": row, "col": c, "text": v, "row_span": 1, "col_span": 1}
                  for c, v in enumerate(vals)]
        row += 1
    rid = "f58_festa_juliani" if calendar == "jul" else "f59_festa_gregoriani"
    return [{"region_id": rid, "cells": cells}]


if __name__ == "__main__":
    out = Path("work/orloj1587/tables_clean")
    out.mkdir(parents=True, exist_ok=True)
    for cal, page in [("jul", 58), ("greg", 59)]:
        data = build(cal)
        (out / f"{page:04d}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        nrows = max(c["row"] for c in data[0]["cells"])
        print(f"f{page} ({cal}): {nrows} datových řádků, {len(data[0]['cells'])} buněk")
