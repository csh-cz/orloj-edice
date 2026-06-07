# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Build f61 — Tabula Intervalli Paschae, Gregorian (twin of f60).

Rows = Gregorian epacts in the manuscript's order 30(*), 29, 28, 27, 26, 25, 23 … 1
(epact 24 is only the alternate of 25, XXV the alternate of 26 — placed as labels on
those rows, since they share the same Paschal full moon). Columns = dominical letters
A–G. Each cell = "week complement":
    week       = floor((Gregorian-Easter day-of-year-from-1-March + 16) / 7)
    complement = (35 for column A, else 34) − week
Easter = the first Sunday strictly after the Paschal full moon (Sundays = dates with
the row's dominical letter). The formula reproduces f60's decode and was verified
against the f61 scan (epact 29/A→"9 26", 29/G→"8 26", 26/A→"10 25", 27/A→"10 25").
"""

from __future__ import annotations

import json
from pathlib import Path

CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
LET = "ABCDEFG"


def doy(m, d):
    return CUM[m - 1] + d


def letter(n):
    return LET[(n - 1) % 7]


# Gregorian Paschal full moon (day-of-year) for the epact.
def pfm(e: int) -> int:
    if 1 <= e <= 23:
        return doy(4, 13) - e          # e=1→12 Apr … e=23→21 Mar
    if e in (30, 0):
        return doy(4, 13)              # 13 Apr  (epact * )
    if 25 <= e <= 29:
        return doy(4, 43 - e)          # 25→18 Apr, 26→17 … 29→14 Apr
    if e == 24:
        return doy(4, 18)              # alternate of 25
    raise ValueError(e)


def easter_week(e: int, dl: str) -> int:
    p = pfm(e)
    d = p + 1
    while letter(d) != dl:
        d += 1
    return (d - doy(3, 1) + 1 + 16) // 7   # day-of-year from 1 March (1 Mar = 1)


# epact rows in MS order; label carries the lunar-equation alternates
ROWS = [(30, "* (30)"), (29, "29"), (28, "28"), (27, "27"), (26, "26 · XXV"),
        (25, "25 · 24")] + [(e, str(e)) for e in range(23, 0, -1)]


def build():
    cols = ["Epacta"] + list(LET)
    cells = [{"row": 0, "col": c, "text": n, "row_span": 1, "col_span": 1}
             for c, n in enumerate(cols)]
    for r, (e, lab) in enumerate(ROWS, start=1):
        vals = [lab]
        for dl in LET:
            w = easter_week(e, dl)
            comp = (35 if dl == "A" else 34) - w
            vals.append(f"{w} {comp}")
        cells += [{"row": r, "col": c, "text": v, "row_span": 1, "col_span": 1}
                  for c, v in enumerate(vals)]
    # bottom row: Dies Concurrentes 0–6 under A–G (read from the scan)
    last = len(ROWS) + 1
    conc = ["Dies Concurrentes", "0", "1", "2", "3", "4", "5", "6"]
    cells += [{"row": last, "col": c, "text": v, "row_span": 1, "col_span": 1}
              for c, v in enumerate(conc)]
    return [{"region_id": "f61_intervallum_greg", "cells": cells}]


if __name__ == "__main__":
    data = build()
    out = Path("work/orloj1587/tables_clean/0061.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"f61: {len(ROWS)} epaktových řádků, {len(data[0]['cells'])} buněk -> {out}")
