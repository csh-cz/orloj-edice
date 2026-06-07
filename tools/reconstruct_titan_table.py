# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Reconstruct a 2-D cell grid from a Transkribus PAGE XML whose table cells were
recognised as individual TextLines (Titan, useExistingLinePolygons).

Strategy: take every TextLine centroid (x, y) + text, cluster into ROWS by an
adaptive y-gap, detect global COLUMNS by 1-D clustering of all x-centroids, then
assign each cell to its nearest column. Emits a readable grid (TSV) and JSON.

This is a *draft* reconstruction for editorial review — dense computistic grids
still need formula verification before publication.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lxml import etree


def _loc(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _lines(path: str) -> list[tuple[int, int, str]]:
    root = etree.fromstring(Path(path).read_bytes())
    out: list[tuple[int, int, str]] = []
    for ln in root.iter():
        if _loc(ln.tag) != "TextLine":
            continue
        pts = None
        txt = ""
        for c in ln.iter():
            lc = _loc(c.tag)
            if lc == "Coords" and c.get("points") and pts is None:
                pts = c.get("points")
            if lc == "Unicode":
                txt = (c.text or "")
        if not pts:
            continue
        p = [tuple(map(int, q.split(","))) for q in pts.split()]
        xs = [a for a, _ in p]
        ys = [b for _, b in p]
        out.append(((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2, txt.strip()))
    return out


def _cluster_1d(vals: list[int], gap: int) -> list[float]:
    """Return cluster centers of 1-D points using a simple gap split."""
    if not vals:
        return []
    s = sorted(vals)
    groups = [[s[0]]]
    for v in s[1:]:
        if v - groups[-1][-1] <= gap:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def reconstruct(path: str, row_gap: int = 26, col_gap: int = 55):
    cells = [(x, y, t) for x, y, t in _lines(path) if t]
    # rows by y-gap
    cells.sort(key=lambda c: c[1])
    rows: list[list[tuple[int, int, str]]] = []
    cur: list[tuple[int, int, str]] = []
    last = None
    for x, y, t in cells:
        if last is None or y - last <= row_gap:
            cur.append((x, y, t))
        else:
            rows.append(cur)
            cur = [(x, y, t)]
        last = y
    if cur:
        rows.append(cur)
    # global columns by x-gap
    centers = _cluster_1d([x for x, _, _ in cells], col_gap)

    def col_of(x: int) -> int:
        return min(range(len(centers)), key=lambda i: abs(centers[i] - x))

    grid = []
    for r in rows:
        r.sort(key=lambda c: c[0])
        ncols = len(centers)
        cellrow = [""] * ncols
        for x, _, t in r:
            ci = col_of(x)
            cellrow[ci] = (cellrow[ci] + " " + t).strip() if cellrow[ci] else t
        y = sum(c[1] for c in r) // len(r)
        grid.append({"y": y, "cells": cellrow})
    return centers, grid


if __name__ == "__main__":
    p = sys.argv[1]
    rg = int(sys.argv[2]) if len(sys.argv) > 2 else 26
    cg = int(sys.argv[3]) if len(sys.argv) > 3 else 55
    centers, grid = reconstruct(p, rg, cg)
    print(f"# {p}  cols={len(centers)} rows={len(grid)}")
    print("# col centers x:", [round(c) for c in centers])
    for row in grid:
        print(f"{row['y']:4d} | " + " | ".join(c or "·" for c in row["cells"]))
    out = Path(p).with_suffix(".grid.json")
    out.write_text(json.dumps({"col_centers": centers, "grid": grid},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stderr.write(f"saved {out}\n")
