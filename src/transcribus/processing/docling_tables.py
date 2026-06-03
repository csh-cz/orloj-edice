# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Table-structure extraction via Docling (TableFormer).

Transkribus HTR reads the handwritten *prose*, but table-structure recognition
is gated on the account's plan. Docling's TableFormer recovers the grid
(rows/cols/cells) from a scan locally and free; the (handwritten) cell text is
approximate and meant for proofreading.

Docling runs as an external CLI (it lives in its own heavy environment). We shell
out with ``--to json`` and map its DoclingDocument table cells onto our
:class:`Table` / :class:`TableCell`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from PIL import Image

from transcribus.processing.page_xml import Table, TableCell


def docling_available() -> bool:
    return shutil.which("docling") is not None


def _tables_from_doc(doc: dict) -> list[Table]:
    tables: list[Table] = []
    for i, t in enumerate(doc.get("tables", [])):
        cells = [
            TableCell(
                row=int(c.get("start_row_offset_idx", 0)),
                col=int(c.get("start_col_offset_idx", 0)),
                text=(c.get("text") or "").strip(),
                row_span=int(c.get("row_span", 1)),
                col_span=int(c.get("col_span", 1)),
            )
            for c in t.get("data", {}).get("table_cells", [])
        ]
        if cells:
            tables.append(Table(region_id=f"docling{i}", cells=cells))
    return tables


def _page_size(doc: dict) -> tuple[float, float] | None:
    pages = doc.get("pages", {})
    if not pages:
        return None
    size = next(iter(pages.values())).get("size", {})
    return size.get("width"), size.get("height")


def pictures_px_from_doc(doc: dict, scan_w: int, scan_h: int) -> list[tuple[int, int, int, int]]:
    """Picture bounding boxes mapped to the scan's pixel space."""
    page = _page_size(doc)
    pics = doc.get("pictures", [])
    if not page or not page[0] or not pics:
        return []
    pw, ph = page
    sx, sy = scan_w / pw, scan_h / ph
    boxes: list[tuple[int, int, int, int]] = []
    for p in pics:
        prov = (p.get("prov") or [{}])[0]
        bb = prov.get("bbox")
        if not bb:
            continue
        x0, x1 = bb["l"] * sx, bb["r"] * sx
        if bb.get("coord_origin") == "BOTTOMLEFT":
            y0, y1 = (ph - bb["t"]) * sy, (ph - bb["b"]) * sy
        else:
            y0, y1 = bb["t"] * sy, bb["b"] * sy
        boxes.append((int(x0), int(min(y0, y1)), int(x1), int(max(y0, y1))))
    return boxes


def extract_layout(image_path: Path, *, timeout: float = 900.0):
    """Run Docling on one image; return (tables, picture boxes in scan pixels)."""
    binary = shutil.which("docling") or "docling"
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            [binary, str(image_path), "--from", "image", "--to", "json", "--output", td],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
        files = list(Path(td).glob("*.json"))
        if not files:
            return [], []
        doc = json.loads(files[0].read_text(encoding="utf-8"))
    with Image.open(image_path) as im:
        w, h = im.size
    return _tables_from_doc(doc), pictures_px_from_doc(doc, w, h)


def run_docling_dir(scans_dir: Path, out_json_dir: Path, *, timeout: float = 5400.0) -> None:
    """Run Docling once over a whole directory of images (single model load)."""
    binary = shutil.which("docling") or "docling"
    out_json_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [binary, str(scans_dir), "--from", "image", "--to", "json", "--output", str(out_json_dir)],
        check=True,
        capture_output=True,
        timeout=timeout,
    )


def crop_figures(scan_path: Path, boxes: list[tuple[int, int, int, int]], out_dir: Path,
                 page_nr: int, *, pad: int = 8) -> list[str]:
    """Crop figure boxes from the full-resolution scan; return relative filenames."""
    if not boxes:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with Image.open(scan_path) as im:
        W, H = im.size
        for k, (x0, y0, x1, y1) in enumerate(boxes, start=1):
            box = (max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad))
            if box[2] - box[0] < 20 or box[3] - box[1] < 20:
                continue
            name = f"{page_nr:04d}_{k}.jpg"
            im.crop(box).save(out_dir / name, quality=90)
            names.append(name)
    return names


def extract_tables(image_path: Path, *, timeout: float = 900.0) -> list[Table]:
    """Run Docling on one image and return its detected tables."""
    binary = shutil.which("docling") or "docling"
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            [binary, str(image_path), "--from", "image", "--to", "json", "--output", td],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
        files = list(Path(td).glob("*.json"))
        if not files:
            return []
        doc = json.loads(files[0].read_text(encoding="utf-8"))

    tables: list[Table] = []
    for i, t in enumerate(doc.get("tables", [])):
        cells: list[TableCell] = []
        for c in t.get("data", {}).get("table_cells", []):
            cells.append(
                TableCell(
                    row=int(c.get("start_row_offset_idx", 0)),
                    col=int(c.get("start_col_offset_idx", 0)),
                    text=(c.get("text") or "").strip(),
                    row_span=int(c.get("row_span", 1)),
                    col_span=int(c.get("col_span", 1)),
                )
            )
        if cells:
            tables.append(Table(region_id=f"docling{i}", cells=cells))
    return tables


# -- (de)serialization for the work/<job>/tables/NNNN.json sidecars ----------
def tables_to_json(tables: list[Table]) -> str:
    payload = [
        {"region_id": t.region_id, "cells": [asdict(c) for c in t.cells]} for t in tables
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def tables_from_json(text: str) -> list[Table]:
    data = json.loads(text)
    return [
        Table(region_id=x.get("region_id", "t"), cells=[TableCell(**c) for c in x["cells"]])
        for x in data
    ]
