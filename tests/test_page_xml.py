# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
from transcribus.processing.page_xml import page_to_lines, parse_page_xml

PAGE = """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15">
  <Page imageFilename="0001.jpg" imageWidth="1000" imageHeight="1500">
    <ReadingOrder>
      <OrderedGroup id="g">
        <RegionRefIndexed index="0" regionRef="r1"/>
        <RegionRefIndexed index="1" regionRef="r2"/>
      </OrderedGroup>
    </ReadingOrder>
    <TextRegion id="r2">
      <TextLine id="l3"><TextEquiv><Unicode>third</Unicode></TextEquiv></TextLine>
    </TextRegion>
    <TextRegion id="r1">
      <TextLine id="l1"><TextEquiv><Unicode>first</Unicode></TextEquiv></TextLine>
      <TextLine id="l2"><TextEquiv><Unicode>second</Unicode></TextEquiv></TextLine>
    </TextRegion>
  </Page>
</PcGts>
"""


def test_reading_order_respected():
    regions = parse_page_xml(PAGE)
    assert [r.region_id for r in regions] == ["r1", "r2"]


def test_page_to_lines():
    assert page_to_lines(PAGE) == ["first", "second", "third"]
