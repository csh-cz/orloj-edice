# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Acquisition sources (archives) that yield local page images."""

from transcribus.sources.ahmp import AhmpSource
from transcribus.sources.base import AcquisitionSource, PageImage

SOURCES: dict[str, type[AcquisitionSource]] = {
    "ahmp": AhmpSource,
}

__all__ = ["AcquisitionSource", "PageImage", "AhmpSource", "SOURCES"]
