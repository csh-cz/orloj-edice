# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Parse PAGE XML (PRImA schema) into ordered text lines.

Transkribus exports transcripts as PAGE XML. We extract TextLine content in
reading order: regions ordered by their ReadingOrder index (falling back to
document order), lines ordered within each region likewise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import etree


@dataclass
class TextRegion:
    region_id: str
    lines: list[str]
    rtype: str = "paragraph"  # paragraph | marginalia | heading | page-number | ...


@dataclass
class TableCell:
    row: int
    col: int
    text: str
    row_span: int = 1
    col_span: int = 1


@dataclass
class Table:
    region_id: str
    cells: list[TableCell]

    def n_rows(self) -> int:
        return max((c.row + c.row_span for c in self.cells), default=0)

    def n_cols(self) -> int:
        return max((c.col + c.col_span for c in self.cells), default=0)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _region_type(region: etree._Element) -> str:
    """Region structure type from PAGE @type or the Transkribus custom attribute."""
    t = region.get("type")
    if t:
        return t
    custom = region.get("custom", "")
    m = re.search(r"structure\s*\{[^}]*type:\s*([\w-]+)", custom)
    return m.group(1) if m else "paragraph"


def _reading_order_index(elem: etree._Element, ns: dict[str, str]) -> dict[str, int]:
    """Map regionRef -> index from the page's ReadingOrder, if present."""
    order: dict[str, int] = {}
    for ix in elem.iter():
        if _local(ix.tag) == "RegionRefIndexed":
            ref = ix.get("regionRef")
            idx = ix.get("index")
            if ref is not None and idx is not None:
                order[ref] = int(idx)
    return order


def _bbox(region: etree._Element) -> tuple[int, int, int, int] | None:
    for c in region.iter():
        if _local(c.tag) == "Coords" and c.get("points"):
            pts = [tuple(map(int, p.split(","))) for p in c.get("points").split()]
            xs = [x for x, _ in pts]
            ys = [y for _, y in pts]
            return min(xs), min(ys), max(xs), max(ys)
    return None


def _geom_type(bbox: tuple[int, int, int, int] | None, page_w: int, n_regions: int) -> str:
    """Heuristic: a narrow region hugging an outer margin is a marginal note."""
    if not bbox or not page_w or n_regions < 2:
        return "paragraph"
    x0, _y0, x1, _y1 = bbox
    width_frac = (x1 - x0) / page_w
    if width_frac < 0.25 and (x0 / page_w < 0.15 or x1 / page_w > 0.85):
        return "marginalia"
    return "paragraph"


def parse_page_xml(xml: str | bytes) -> list[TextRegion]:
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = etree.fromstring(xml)

    order = _reading_order_index(root, {})
    page = next((e for e in root.iter() if _local(e.tag) == "Page"), None)
    page_w = int(page.get("imageWidth", 0)) if page is not None else 0

    raw = [r for r in root.iter() if _local(r.tag) == "TextRegion"]
    regions: list[tuple[int, TextRegion]] = []
    for doc_pos, region in enumerate(raw):
        rid = region.get("id", f"r{doc_pos}")
        lines: list[tuple[int, str]] = []
        for line_pos, line in enumerate(ln for ln in region.iter() if _local(ln.tag) == "TextLine"):
            text = _line_text(line)
            if text is not None:
                lines.append((line_pos, text))
        ordered_lines = [t for _, t in sorted(lines, key=lambda x: x[0])]
        # Prefer an explicit PAGE/Transkribus type; else infer from geometry.
        rtype = _region_type(region)
        if rtype == "paragraph":
            rtype = _geom_type(_bbox(region), page_w, len(raw))
        sort_key = order.get(rid, 1000 + doc_pos)
        regions.append((sort_key, TextRegion(region_id=rid, lines=ordered_lines, rtype=rtype)))

    regions.sort(key=lambda x: x[0])
    return [r for _, r in regions]


def marginalia_bboxes(xml: str | bytes) -> list[tuple[tuple[int, int, int, int], str]]:
    """Return (bbox, HTR-text) of marginal regions, sorted top-to-bottom.

    A marginal region = a narrow region hugging an outer margin (geometry, see
    ``_geom_type``). Used to crop the marginalia from the scan for the analysis page.
    """
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = etree.fromstring(xml)
    page = next((e for e in root.iter() if _local(e.tag) == "Page"), None)
    page_w = int(page.get("imageWidth", 0)) if page is not None else 0
    raw = [r for r in root.iter() if _local(r.tag) == "TextRegion"]
    out: list[tuple[tuple[int, int, int, int], str]] = []
    for region in raw:
        bb = _bbox(region)
        if bb and _geom_type(bb, page_w, len(raw)) == "marginalia":
            txt = " ".join(
                t for t in (_line_text(ln) for ln in region.iter()
                            if _local(ln.tag) == "TextLine") if t
            )
            out.append((bb, txt))
    return sorted(out, key=lambda it: it[0][1])  # by y0, top to bottom


def _line_text(line: etree._Element) -> str | None:
    """Return the line's transcribed text (TextEquiv/Unicode), or None if absent."""
    for te in line.iter():
        if _local(te.tag) == "TextEquiv":
            for u in te.iter():
                if _local(u.tag) == "Unicode":
                    return (u.text or "").strip()
    return None


def page_to_lines(xml: str | bytes) -> list[str]:
    """Flatten a PAGE XML page into a list of text lines in reading order."""
    lines: list[str] = []
    for region in parse_page_xml(xml):
        lines.extend(region.lines)
    return lines


def parse_tables(xml: str | bytes) -> list[Table]:
    """Extract TableRegion/TableCell structure (row/col) from PAGE XML, if any."""
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = etree.fromstring(xml)
    tables: list[Table] = []
    for tr in root.iter():
        if _local(tr.tag) != "TableRegion":
            continue
        cells: list[TableCell] = []
        for cell in tr.iter():
            if _local(cell.tag) != "TableCell":
                continue
            texts = [t for line in cell.iter() if _local(line.tag) == "TextLine"
                     for t in [_line_text(line)] if t]
            cells.append(
                TableCell(
                    row=int(cell.get("row", 0)),
                    col=int(cell.get("col", 0)),
                    text=" ".join(texts).strip(),
                    row_span=int(cell.get("rowSpan", 1)),
                    col_span=int(cell.get("colSpan", 1)),
                )
            )
        if cells:
            tables.append(Table(region_id=tr.get("id", f"t{len(tables)}"), cells=cells))
    return tables
