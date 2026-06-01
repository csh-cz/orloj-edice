# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
from transcribus.processing.cleanup import (
    assemble_markdown,
    clean_page,
    dehyphenate,
    normalize_line,
)


def test_normalize_line_collapses_whitespace():
    assert normalize_line("  foo\t bar  ") == "foo bar"


def test_dehyphenate_joins_split_word():
    lines = ["Haupt-", "mann kam", "spät"]
    assert dehyphenate(lines) == ["Hauptmann kam", "spät"]


def test_clean_page():
    out = clean_page(["Haupt-", "mann", "  und   Frau "])
    assert out == "Hauptmann\nund Frau"


def test_assemble_markdown_has_page_markers():
    md = assemble_markdown([["a", "b"], ["c"]], title="Kniha")
    assert "# Kniha" in md
    assert "## sken 0001" in md
    assert "## sken 0002" in md
