# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
import io

import httpx
from PIL import Image

from transcribus.sources.zoomify import (
    ZoomifyImage,
    download_zoomify,
    parse_image_properties,
)


def test_levels_and_tile_group():
    img = ZoomifyImage(width=512, height=512, tile_size=256)
    assert img.levels == [(256, 256), (512, 512)]
    # all 4 full-res tiles fall in TileGroup0 (cumulative index < 256)
    groups = {img.tile_group(1, c, r) for r in range(2) for c in range(2)}
    assert groups == {0}


def test_parse_image_properties():
    xml = b'<IMAGE_PROPERTIES WIDTH="300" HEIGHT="200" TILESIZE="256" NUMTILES="3"/>'
    props = parse_image_properties(xml)
    assert (props.width, props.height, props.tile_size) == (300, 200, 256)


def _jpeg(w: int, h: int, color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


def test_download_and_stitch(tmp_path):
    xml = b'<IMAGE_PROPERTIES WIDTH="300" HEIGHT="200" TILESIZE="256"/>'

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("ImageProperties.xml"):
            return httpx.Response(200, content=xml)
        if "TileGroup" in path:
            return httpx.Response(200, content=_jpeg(256, 256, (200, 50, 50)))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = tmp_path / "0001.jpg"
    download_zoomify("http://x/img", out, client=client)

    assert out.exists()
    with Image.open(out) as im:
        assert im.size == (300, 200)


def test_ahmp_scan_base_sentinel():
    from transcribus.sources.ahmp import _is_scan_base
    assert _is_scan_base("https://images.ahmp.cz/mrimage/.../x.jpg")
    assert not _is_scan_base("zoomify/")       # end-of-scans sentinel
    assert not _is_scan_base("")
    assert not _is_scan_base(None)
