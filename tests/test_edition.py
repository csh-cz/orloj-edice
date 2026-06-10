# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
from transcribus.processing.edition import build_edition, derive_sections
from transcribus.processing.normalize import normalize_text


def test_derive_sections_bridges_small_gaps():
    # matched 5-30 (with small gaps) and 43-49 -> two Táborský sections + 'other' around
    matched = (set(range(5, 31)) - {6, 22, 24, 29}) | set(range(43, 50))
    secs = derive_sections(matched, total=81, gap=2)
    kinds = [(k, lo, hi) for k, lo, hi, _ in secs]
    assert ("jine", 1, 4) in kinds
    assert ("taborsky", 5, 30) in kinds
    assert ("jine", 31, 42) in kinds
    assert ("taborsky", 43, 49) in kinds
    assert ("jine", 50, 81) in kinds

PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15">
  <Page imageFilename="0001.jpg">
    <TextRegion id="r1">
      <TextLine id="l1"><TextEquiv><Unicode>genž slowe hlawni</Unicode></TextEquiv></TextLine>
    </TextRegion>
  </Page>
</PcGts>
"""


def test_normalize_old_czech():
    assert normalize_text("genž slowe hlawni") == "jenž slove hlavni"
    assert normalize_text("dlauho") == "dlouho"


def test_build_edition_html(tmp_path):
    xml_dir = tmp_path / "page_xml"
    xml_dir.mkdir()
    (xml_dir / "0001.xml").write_text(PAGE, encoding="utf-8")
    index = build_edition(
        tmp_path, title="Test",
        ahmp_permalink="https://katalog.ahmp.cz/pragapublica/permalink?xid=ABC123",
    )

    assert index.exists() and index.name == "index.html"
    assert (tmp_path / "edition" / "assets" / "edition.css").exists()
    page = (tmp_path / "edition" / "p0001.html").read_text(encoding="utf-8")
    assert "genž slowe hlawni" in page  # diplomatic layer
    assert "jenž slove hlavni" in page  # normalized layer
    assert "sken v AHMP" in page
    assert 'name="mode"' in page  # mode switcher present


TABLE_PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15">
  <Page imageFilename="0055.jpg">
    <TableRegion id="tab1">
      <TableCell row="0" col="0"><TextLine><TextEquiv><Unicode>Januarius</Unicode></TextEquiv></TextLine></TableCell>
      <TableCell row="0" col="1"><TextLine><TextEquiv><Unicode>Februarius</Unicode></TextEquiv></TextLine></TableCell>
      <TableCell row="1" col="0"><TextLine><TextEquiv><Unicode>31</Unicode></TextEquiv></TextLine></TableCell>
      <TableCell row="1" col="1"><TextLine><TextEquiv><Unicode>28</Unicode></TextEquiv></TextLine></TableCell>
    </TableRegion>
  </Page>
</PcGts>
"""


def test_parse_and_render_table(tmp_path):
    from transcribus.processing.edition import _table_html
    from transcribus.processing.page_xml import parse_tables

    tables = parse_tables(TABLE_PAGE)
    assert len(tables) == 1
    t = tables[0]
    assert t.n_rows() == 2 and t.n_cols() == 2
    html = _table_html(t)
    assert "<table" in html and "Januarius" in html and "<td>28</td>" in html


def test_edition_renders_verified_table_page(tmp_path):
    # Only verified tables (tables_clean/NNNN.json) are rendered as a grid; raw
    # PAGE-XML TableRegions are deliberately ignored (Docling/HTR of handwritten
    # digits is unreliable). This codifies that design.
    import json

    xml_dir = tmp_path / "page_xml"
    xml_dir.mkdir()
    (xml_dir / "0055.xml").write_text(TABLE_PAGE, encoding="utf-8")
    tc = tmp_path / "tables_clean"
    tc.mkdir()
    (tc / "0055.json").write_text(json.dumps([{
        "region_id": "t1",
        "cells": [
            {"row": 0, "col": 0, "text": "Januarius", "row_span": 1, "col_span": 1},
            {"row": 0, "col": 1, "text": "Februarius", "row_span": 1, "col_span": 1},
        ],
    }]), encoding="utf-8")
    build_edition(tmp_path, title="T")
    page = (tmp_path / "edition" / "p0055.html").read_text(encoding="utf-8")
    assert 'class="page-table"' in page and "Februarius" in page


def test_edition_ignores_raw_table_regions(tmp_path):
    # A page with ONLY a raw TableRegion (no tables_clean JSON) must not render a
    # grid — it falls back to the 'table not yet transcribed' placeholder.
    xml_dir = tmp_path / "page_xml"
    xml_dir.mkdir()
    (xml_dir / "0055.xml").write_text(TABLE_PAGE, encoding="utf-8")
    build_edition(tmp_path, title="T")
    page = (tmp_path / "edition" / "p0055.html").read_text(encoding="utf-8")
    assert 'class="page-table"' not in page


def test_docling_tables_json_roundtrip():
    from transcribus.processing.docling_tables import tables_from_json, tables_to_json
    from transcribus.processing.page_xml import Table, TableCell

    t = Table(region_id="docling0", cells=[
        TableCell(row=0, col=0, text="Januarius"),
        TableCell(row=1, col=0, text="31", row_span=1, col_span=1),
    ])
    back = tables_from_json(tables_to_json([t]))
    assert len(back) == 1 and back[0].n_rows() == 2
    assert back[0].cells[0].text == "Januarius"
