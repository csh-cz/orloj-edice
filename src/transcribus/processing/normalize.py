# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Heuristic transcription of early-modern Czech orthography to a modern reading form.

This is an ASSISTED normalization (a starting point for proofreading), NOT a
scholarly critical normalization. It applies the most regular spelling shifts of
16th–17th c. Czech (spřežkový/early modern orthography) so the diplomatic HTR
text becomes more readable. Always expect manual correction.

Rules are deliberately conservative and applied longest-match-first per token.
"""

from __future__ import annotations

import re

# Order matters: multi-char sequences before single chars.
_RULES: list[tuple[str, str]] = [
    ("ʃ", "s"),  # long s (U+0283)
    ("ſ", "s"),  # long s (U+017F)
    ("ss", "š"),
    ("cž", "č"),  # č was written with the cž spřežka
    ("cz", "c"),  # plain cz spřežka = c (jsoucze->jsouce, zprawcze->zpravce)
    ("rž", "ř"),
    ("rz", "ř"),
    ("au", "ou"),  # dlauho -> dlouho
    ("w", "v"),
    ("g", "j"),  # old Czech g = j (geho -> jeho)
]

_WORD = re.compile(r"\w+", re.UNICODE)


def normalize_word(word: str) -> str:
    out = word
    for src, dst in _RULES:
        out = out.replace(src, dst)
        out = out.replace(src.upper(), dst.upper())
    return out


def normalize_text(text: str) -> str:
    """Apply the heuristic rules token-by-token, preserving punctuation/whitespace."""
    return _WORD.sub(lambda m: normalize_word(m.group(0)), text)
