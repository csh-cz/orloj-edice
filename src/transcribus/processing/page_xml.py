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


def parse_page_xml(xml: str | bytes) -> list[TextRegion]:
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = etree.fromstring(xml)
    ns = {"p": root.nsmap.get(None, "")} if root.nsmap.get(None) else {}

    order = _reading_order_index(root, ns)

    regions: list[tuple[int, TextRegion]] = []
    doc_pos = 0
    for region in root.iter():
        if _local(region.tag) != "TextRegion":
            continue
        rid = region.get("id", f"r{doc_pos}")
        lines: list[tuple[int, str]] = []
        line_pos = 0
        for line in region.iter():
            if _local(line.tag) != "TextLine":
                continue
            text = _line_text(line)
            if text is not None:
                # explicit custom reading order isn't always present; keep doc order
                lines.append((line_pos, text))
            line_pos += 1
        ordered_lines = [t for _, t in sorted(lines, key=lambda x: x[0])]
        sort_key = order.get(rid, 1000 + doc_pos)
        regions.append(
            (sort_key, TextRegion(region_id=rid, lines=ordered_lines, rtype=_region_type(region)))
        )
        doc_pos += 1

    regions.sort(key=lambda x: x[0])
    return [r for _, r in regions]


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
