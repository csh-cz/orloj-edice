# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Assemble and normalize per-page transcript lines into clean text."""

from __future__ import annotations

import re
import unicodedata

# End-of-line hyphenation: a word split across lines ("Haupt-\nmann").
_HYPHEN_EOL = re.compile(r"(\w)[-¬­]\s*$")
_MULTISPACE = re.compile(r"[ \t]+")


def normalize_line(line: str) -> str:
    line = unicodedata.normalize("NFC", line)
    line = line.replace("­", "")  # stray soft hyphens
    return _MULTISPACE.sub(" ", line).strip()


def dehyphenate(lines: list[str]) -> list[str]:
    """Join words split by an end-of-line hyphen into the next line's first word."""
    out: list[str] = []
    carry = ""
    for raw in lines:
        line = (carry + raw) if carry else raw
        carry = ""
        m = _HYPHEN_EOL.search(line)
        if m:
            carry = line[: m.start() + 1]  # keep char before the hyphen, drop hyphen
            continue
        out.append(line)
    if carry:
        out.append(carry)
    return out


def clean_page(lines: list[str]) -> str:
    """Normalize + dehyphenate one page's lines into a paragraph block."""
    normalized = [normalize_line(line) for line in lines]
    joined = dehyphenate(normalized)
    return "\n".join(line for line in joined if line)


def assemble_markdown(pages: list[list[str]], *, title: str = "") -> str:
    """Build a Markdown transcript with per-scan page markers.

    ``pages`` is a list of pages, each a list of raw transcript lines.
    """
    parts: list[str] = []
    if title:
        parts.append(f"# {title}\n")
    for i, page_lines in enumerate(pages, start=1):
        parts.append(f"\n## sken {i:04d}\n")
        parts.append(clean_page(page_lines))
    return "\n".join(parts).strip() + "\n"
