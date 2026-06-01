# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Archiv hlavního města Prahy (AHMP) acquisition source.

AHMP's archival catalogue (katalog.ahmp.cz/pragapublica) runs on Bach systems
"VadeMeCum". The actual scans are served by a separate image server,
``images.ahmp.cz``, as standard path-based Zoomify tiles. The flow, verified
against a live permalink, is:

1. GET the permalink -> the page embeds a ``Zoomify.action`` viewer URL carrying
   ``xid``, ``entityType`` and ``entityRef``.
2. GET ``Zoomify.action?...&scanIndex=N`` -> HTML viewer whose JS sets
   ``var zoomifyImgPath = "https://images.ahmp.cz/.../zoomify/.../<hash>.jpg"``.
   That path is a Zoomify base (``/ImageProperties.xml`` + ``/TileGroup{g}/...``).
3. Enumerate ``scanIndex`` from 1 upward until a page has no zoomifyImgPath.
4. Download + stitch each scan via the generic Zoomify downloader.

Scans carry the public ``ahmp_watermark`` overlay (inherent to public access).
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import httpx

from transcribus.sources.base import PageImage
from transcribus.sources.zoomify import download_zoomify

_XID_RE = re.compile(r"^[0-9A-Fa-f]{16,}$")
_ENTITY_TYPE_RE = re.compile(r"entityType=(\d+)")
_ENTITY_REF_RE = re.compile(r"entityRef=([^&\"'<>\s]+)")
_ZOOMIFY_PATH_RE = re.compile(r'zoomifyImgPath\s*=\s*"([^"]+)"')


def _is_scan_base(value: str | None) -> bool:
    """A real scan base is an absolute http(s) URL.

    Past the last scan, Bach's viewer emits a relative sentinel like ``"zoomify/"``;
    treat anything that is not an absolute URL as end-of-scans.
    """
    return bool(value) and value.startswith(("http://", "https://"))

_DEFAULT_ROOT = "https://katalog.ahmp.cz/pragapublica"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (transcribus pipeline)",
    "Referer": "https://katalog.ahmp.cz/",
}


class AhmpSource:
    name = "ahmp"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=60.0, follow_redirects=True, headers=_HEADERS
        )

    # -- public API -------------------------------------------------------
    def resolve(self, ref: str, out_dir: Path, *, limit: int | None = None) -> list[PageImage]:
        root, xid = self._parse_ref(ref)
        entity_type, entity_ref = self._discover_entity(root, xid)

        pages: list[PageImage] = []
        scan_index = 1
        while limit is None or len(pages) < limit:
            base = self._scan_zoomify_base(root, xid, entity_type, entity_ref, scan_index)
            if base is None:
                break  # past the last scan
            out_path = out_dir / f"{scan_index:04d}.jpg"
            # Per-page resume: skip pages already downloaded.
            if not (out_path.exists() and out_path.stat().st_size > 0):
                download_zoomify(base, out_path, client=self._client)
            pages.append(PageImage(index=scan_index - 1, path=out_path, source_url=base))
            scan_index += 1

        if not pages:
            raise RuntimeError(
                f"No scans found for xid={xid}. Verify the permalink points to a "
                "digitized unit."
            )
        return pages

    # -- internals --------------------------------------------------------
    def _parse_ref(self, ref: str) -> tuple[str, str]:
        """Return (catalogue root URL, xid) from a permalink URL or a bare xid."""
        if "://" not in ref:
            if not _XID_RE.match(ref):
                raise ValueError(f"Not a valid xid: {ref!r}")
            return _DEFAULT_ROOT, ref

        parsed = urlparse(ref)
        xid = (parse_qs(parsed.query).get("xid") or [None])[0]
        if not xid:
            raise ValueError(f"Could not extract xid from URL: {ref!r}")
        root = f"{parsed.scheme}://{parsed.netloc}/pragapublica"
        return root, xid

    def _discover_entity(self, root: str, xid: str) -> tuple[str, str]:
        """Open the permalink (sets the session cookie) and read entityType/entityRef."""
        html = self._client.get(f"{root}/permalink", params={"xid": xid}).text
        html = html.replace("&amp;", "&")
        et = _ENTITY_TYPE_RE.search(html)
        er = _ENTITY_REF_RE.search(html)
        if not et or not er:
            raise RuntimeError(
                f"Could not find Zoomify entity params for xid={xid}. The unit may "
                "have no digitized scans."
            )
        return et.group(1), er.group(1)

    def _scan_zoomify_base(
        self, root: str, xid: str, entity_type: str, entity_ref: str, scan_index: int
    ) -> str | None:
        """Return the Zoomify base URL for a scan, or None if scan_index is out of range."""
        # entity_ref is already percent-encoded in the page; keep it verbatim.
        url = (
            f"{root}/Zoomify.action?xid={quote(xid)}"
            f"&entityType={entity_type}&entityRef={entity_ref}&scanIndex={scan_index}"
        )
        html = self._client.get(url).text
        m = _ZOOMIFY_PATH_RE.search(html)
        base = m.group(1).strip() if m else None
        return base if _is_scan_base(base) else None
