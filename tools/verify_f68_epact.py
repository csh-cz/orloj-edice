# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Verify the two worked epact examples on fol. 68 ("Z francouzského autora").

The folio teaches a medieval finger-computus rule for the day of the new moon:

    new_moon_day = 30 - ((epact + month_index_from_March) mod 30)      [+15 -> full moon]

Each example states its own intermediate sum, so the epact digits (originally
flagged [?] in the transcription) are fixed by the arithmetic, not guessed:

    1641, January: epact + 11 = 13  ->  epact = 2 ; new moon 30 - 13 = 17 Jan
    1609, January: epact + 11 = 35  ->  35 mod 30 = 5 ; new moon 30 - 5 = 25 Jan

We recompute both chains and check they reproduce the days stated in the text
(17 Jan and 25 Jan), confirming the readings epact(1641)=2 and epact(1609)=24.
"""

from __future__ import annotations

# (year, stated epact, stated sum, January month-index from March, stated new-moon day)
CASES = [
    (1641, 2, 13, 11, 17),
    (1609, 24, 35, 11, 25),
]


def new_moon_day(epact: int, month_index: int) -> tuple[int, int]:
    """Return (stated sum before mod, computed new-moon day) per the folio's rule."""
    s = epact + month_index
    return s, 30 - (s % 30)


def main() -> bool:
    print("fol. 68 — kontrola epakt z vlastní aritmetiky příkladů\n")
    ok = True
    for year, epact, sum_text, mi, day_text in CASES:
        s, day = new_moon_day(epact, mi)
        good = (s == sum_text) and (day == day_text)
        ok &= good
        mark = "✓" if good else "✗"
        print(f"  {mark} {year} I: epakta {epact:2d} + {mi} = {s:2d} "
              f"(rukopis {sum_text}); nový měsíc {day}. I (rukopis {day_text}.)")
    print(f"\n{'✓ VŠE SOUHLASÍ' if ok else '✗ NESHODA'} — epakty 1641 = 2, 1609 = 24 "
          "jsou jisté z uzavřeného počtu.")
    return ok


if __name__ == "__main__":
    import sys

    sys.exit(0 if main() else 1)
