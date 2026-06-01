# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Common interface for acquisition sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class PageImage:
    """One downloaded scan page."""

    index: int  # 0-based scan index within the archival unit
    path: Path  # local file path of the full-resolution image
    source_url: str  # where it came from (for the manifest / provenance)


class AcquisitionSource(Protocol):
    """A source that resolves an archive reference into local page images."""

    #: short identifier used on the CLI (e.g. "ahmp")
    name: str

    def resolve(self, ref: str, out_dir: Path, *, limit: int | None = None) -> list[PageImage]:
        """Download scans of ``ref`` into ``out_dir`` and return them ordered.

        ``limit`` caps the number of scans (None = all).
        """
        ...
