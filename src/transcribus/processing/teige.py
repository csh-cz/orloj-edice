# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Approximate alignment of our (noisy) page transcripts to Teige's edition text.

Our text is a diplomatic HTR of the 1587+ copy; Teige (1901) edited the 1570
original. They are different witnesses, so this is a *best-effort* passage
alignment for a side-by-side reading aid — not a critical apparatus.

Approach: fold both sides (lowercase + strip diacritics + map spřežka), build an
inverted index of Teige tokens, and for each page pick the densest window of
matching token positions.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from transcribus.processing.normalize import normalize_text

_WORD = re.compile(r"\w+", re.UNICODE)


def fold(s: str) -> str:
    """Lowercase, normalize orthography, strip diacritics — for fuzzy matching."""
    s = normalize_text(s).lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


@dataclass
class Token:
    folded: str
    start: int  # char offset in the original Teige text
    end: int


def _tokenize(text: str) -> list[Token]:
    toks: list[Token] = []
    for m in _WORD.finditer(text):
        f = fold(m.group(0))
        if f:
            toks.append(Token(folded=f, start=m.start(), end=m.end()))
    return toks


class TeigeIndex:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = _tokenize(text)
        self.index: dict[str, list[int]] = defaultdict(list)
        for i, t in enumerate(self.tokens):
            if len(t.folded) >= 4:  # ignore short, ambiguous tokens
                self.index[t.folded].append(i)

    def align(
        self, page_text: str, *, min_hits: int = 6, min_overlap: float = 0.33
    ) -> str | None:
        """Return the Teige passage matching ``page_text``, or None.

        The gate is *lexical overlap* — the fraction of the page's distinct words
        that occur anywhere in Teige. Táborský-report pages score ~0.35–0.45; other
        sections of the convolut (Latin, calendar tables, 17th-c. notes), which
        Teige did NOT edit, score well below and get no (spurious) alignment.
        """
        page_set = {f for f in (fold(w) for w in _WORD.findall(page_text)) if len(f) >= 4}
        present = {f for f in page_set if f in self.index}
        if len(page_set) < min_hits or len(present) < min_hits:
            return None
        if len(present) / len(page_set) < min_overlap:
            return None  # outside the Táborský section — no reference edition

        # Densest window over the positions of the matching words (for display).
        hits = sorted(p for f in present for p in self.index[f])
        window = max(len(page_set), 20)
        best_lo = best_hi = hits[0]
        best_count = 0
        j = 0
        for i in range(len(hits)):
            while j < len(hits) and hits[j] - hits[i] <= window:
                j += 1
            if j - i > best_count:
                best_count = j - i
                best_lo, best_hi = hits[i], hits[min(j, len(hits)) - 1]
        start = self.tokens[best_lo].start
        end = self.tokens[min(best_hi, len(self.tokens) - 1)].end
        return self.text[start:end].strip()
