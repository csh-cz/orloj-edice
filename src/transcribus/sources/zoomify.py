# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Generic Zoomify tile downloader.

Zoomify splits a large image into 256x256 tiles arranged in zoom levels. The
base directory holds ``ImageProperties.xml`` (width/height/tilesize) plus
``TileGroup{N}/`` folders with tiles named ``{level}-{col}-{row}.jpg``. To get
the original image we download every tile of the highest level and stitch them.

Tile-index math matches the canonical Zoomify scheme (same as OpenSeadragon's
ZoomifyTileSource and dezoomify).
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

import httpx
from lxml import etree
from PIL import Image


@dataclass
class ZoomifyImage:
    width: int
    height: int
    tile_size: int

    @property
    def levels(self) -> list[tuple[int, int]]:
        """Level dimensions, smallest first (level 0) to full resolution last."""
        dims: list[tuple[int, int]] = []
        w, h = self.width, self.height
        while True:
            dims.append((w, h))
            if w <= self.tile_size and h <= self.tile_size:
                break
            w = (w + 1) // 2
            h = (h + 1) // 2
        dims.reverse()
        return dims

    def _tiles_xy(self, w: int, h: int) -> tuple[int, int]:
        return math.ceil(w / self.tile_size), math.ceil(h / self.tile_size)

    def tile_group(self, level: int, col: int, row: int) -> int:
        """TileGroup folder index for a tile (cumulative tile count // 256)."""
        levels = self.levels
        before = 0
        for lw, lh in levels[:level]:
            tx, ty = self._tiles_xy(lw, lh)
            before += tx * ty
        tx, _ = self._tiles_xy(*levels[level])
        return (before + row * tx + col) // 256


def parse_image_properties(xml: bytes) -> ZoomifyImage:
    root = etree.fromstring(xml)
    return ZoomifyImage(
        width=int(root.get("WIDTH")),
        height=int(root.get("HEIGHT")),
        tile_size=int(root.get("TILESIZE", "256")),
    )


def _normalize_base(base_url: str) -> str:
    base = base_url.strip()
    if base.endswith("ImageProperties.xml"):
        base = base.rsplit("/", 1)[0]
    return base.rstrip("/")


# Default path-based Zoomify scheme: {base}/TileGroup{group}/{level}-{col}-{row}.jpg
DEFAULT_TILE_TEMPLATE = "{base}/TileGroup{group}/{level}-{col}-{row}.jpg"
DEFAULT_PROPS_TEMPLATE = "{base}/ImageProperties.xml"


def download_zoomify(
    base_url: str,
    out_path: Path,
    client: httpx.Client | None = None,
    *,
    tile_template: str = DEFAULT_TILE_TEMPLATE,
    props_template: str = DEFAULT_PROPS_TEMPLATE,
) -> Path:
    """Download the full-resolution image from a Zoomify base URL and stitch it.

    ``tile_template`` / ``props_template`` are format strings. The default is the
    standard path-based scheme; pass a query-param template (e.g. Bach's
    ``Zoomify.action?...&file=TileGroup{group}/{level}-{col}-{row}.jpg``) when the
    server serves tiles through a single action endpoint. Available placeholders:
    ``{base} {group} {level} {col} {row}``.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        base = _normalize_base(base_url) if tile_template is DEFAULT_TILE_TEMPLATE else base_url
        props = parse_image_properties(client.get(props_template.format(base=base)).content)
        levels = props.levels
        max_level = len(levels) - 1
        full_w, full_h = levels[max_level]
        tiles_x, tiles_y = props._tiles_xy(full_w, full_h)

        canvas = Image.new("RGB", (full_w, full_h))
        for row in range(tiles_y):
            for col in range(tiles_x):
                group = props.tile_group(max_level, col, row)
                url = tile_template.format(
                    base=base, group=group, level=max_level, col=col, row=row
                )
                resp = client.get(url)
                resp.raise_for_status()
                tile = Image.open(io.BytesIO(resp.content))
                canvas.paste(tile, (col * props.tile_size, row * props.tile_size))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path, quality=95)
        return out_path
    finally:
        if owns_client:
            client.close()
