# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Build f66 — perpetual calendar of new moons (epacts) and ferial letters by day.

For every calendar date (month × day-of-month) the table gives:
  Litera = the ferial/dominical letter of that date = "ABCDEFG"[(doy − 1) mod 7]
           (A = 1 Jan), which is exact and verified against the scan.
  Epacta = the epact whose ecclesiastical new moon (luna 1) falls on that date.
           The label descends by 1 each day (wrapping 30→*), with epact 25 skipped
           in the six 29-day lunar months (Feb, Apr, Jun, Aug, Sep, Nov — the
           Aug/Sep pair being the saltus lunae), as read from the manuscript.

Verified: e.g. Mart 8 → epact 23, i.e. the March new moon of epact 23 = PFM(23) − 13
= 21 Mar − 13 = 8 Mar; and the read scan cells of Jan–Apr (rows 1–9) match exactly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
DIM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]   # days in (non-leap) month
LET = "ABCDEFG"
MON = ["Januar.", "Februar.", "Mart.", "April.", "Maii", "Junii",
       "Julii", "August.", "Septem.", "Octob.", "Novem.", "Decem."]
SKIP_MONTHS = {2, 4, 6, 8, 9, 11}   # 29-day lunar months: epact 25 omitted


def doy(m, d):
    return CUM[m - 1] + d


def litera(m, d):
    return LET[(doy(m, d) - 1) % 7].lower()


def _skips_before_month(m):
    return sum(1 for sm in SKIP_MONTHS if sm < m)


def _skipday(m):
    """Day in month m whose un-skipped label would be 25 (skip applies from here)."""
    sb = _skips_before_month(m)
    for d in range(1, DIM[m - 1] + 1):
        if (1 - doy(m, d) - sb) % 30 == 25:
            return d
    return DIM[m - 1] + 1


def epacta(m, d):
    sb = _skips_before_month(m)
    if m in SKIP_MONTHS and d >= _skipday(m):
        sb += 1
    e = (1 - doy(m, d) - sb) % 30
    return "*" if e == 0 else str(e)


def build():
    # columns: day | (Epacta, Litera) per month
    cols = ["Den"]
    for mo in MON:
        cols += [mo, ""]            # month name spans the Epacta header; Litera under it
    cells = []
    # header row 0: month names over each Epacta/Litera pair
    cells.append({"row": 0, "col": 0, "text": "Den", "row_span": 2, "col_span": 1})
    for i, mo in enumerate(MON):
        cells.append({"row": 0, "col": 1 + 2 * i, "text": mo, "row_span": 1, "col_span": 2})
    # header row 1: Ep / Lit labels + days-in-month note
    cells.append({"row": 1, "col": 0, "text": "", "row_span": 1, "col_span": 1})
    for i in range(12):
        cells.append({"row": 1, "col": 1 + 2 * i, "text": "Ep.", "row_span": 1, "col_span": 1})
        cells.append({"row": 1, "col": 2 + 2 * i, "text": "Lit.", "row_span": 1, "col_span": 1})
    # body: one row per day 1..31
    for d in range(1, 32):
        r = d + 1
        cells.append({"row": r, "col": 0, "text": str(d), "row_span": 1, "col_span": 1})
        for i in range(12):
            m = i + 1
            if d <= DIM[i]:
                cells.append({"row": r, "col": 1 + 2 * i, "text": epacta(m, d),
                              "row_span": 1, "col_span": 1})
                cells.append({"row": r, "col": 2 + 2 * i, "text": litera(m, d),
                              "row_span": 1, "col_span": 1})
            else:
                cells.append({"row": r, "col": 1 + 2 * i, "text": "", "row_span": 1, "col_span": 1})
                cells.append({"row": r, "col": 2 + 2 * i, "text": "", "row_span": 1, "col_span": 1})
    return [{"region_id": "f66_calendarium_novilunia", "cells": cells}]


# scan-read epacts (Jan–Apr, days 1–9) for self-verification
_SCAN = {
    1: [30, 29, 28, 27, 26, 25, 24, 23, 22],
    2: [29, 28, 27, 26, 24, 23, 22, 21, 20],
    3: [30, 29, 28, 27, 26, 25, 24, 23, 22],
    4: [29, 28, 27, 26, 24, 23, 22, 21, 20],
}

if __name__ == "__main__":
    if "--check" in sys.argv:
        ok = tot = 0
        for m, seq in _SCAN.items():
            for d, e in enumerate(seq, start=1):
                got = epacta(m, d)
                exp = "*" if e == 30 else str(e)
                tot += 1
                ok += (got == exp)
                if got != exp:
                    print(f"  MISMATCH {MON[m-1]} {d}: got {got}, scan {exp}")
        print(f"scan-check epakt (Jan–Apr d1–9): {ok}/{tot}")
        # sample Litera
        print("Litera Jan1..8:", [litera(1, d) for d in range(1, 9)])
        print("Litera Mart1, Apr1:", litera(3, 1), litera(4, 1))
    else:
        data = build()
        out = Path("work/orloj1587/tables_clean/0066.json")
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"f66: {len(data[0]['cells'])} buněk -> {out}")
