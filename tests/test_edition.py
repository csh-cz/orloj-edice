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
    index = build_edition(tmp_path, title="Test", ahmp_permalink="https://katalog.ahmp.cz/x")

    assert index.exists() and index.name == "index.html"
    assert (tmp_path / "edition" / "assets" / "edition.css").exists()
    page = (tmp_path / "edition" / "p0001.html").read_text(encoding="utf-8")
    assert "genž slowe hlawni" in page  # diplomatic layer
    assert "jenž slove hlavni" in page  # normalized layer
    assert "sken v AHMP" in page
    assert 'name="mode"' in page  # mode switcher present
