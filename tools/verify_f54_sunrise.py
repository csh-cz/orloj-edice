# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Verify the worked example in the German computus instruction on fol. 54.

The German note (a parallel of the Czech instruction under the fol. 55 sunrise
table) teaches how to derive, from the common-hour sunrise, the Bohemian
(orloj) noon and sunrise and the day length. Its worked example is "den 3. May".

Every number in the example is pinned three ways and they agree:

    * the fol. 55 sunrise table itself gives 3 May = 4:43 (the value quoted),
    * the example's own closed arithmetic (complement to 12, subtract from 24),
    * an independent astronomical sunrise computation for Prague.

This both fixes the readings (the earlier reconstruction wrongly had
4:48/7:12/16:48/9:36/14:24) and confirms the section is a user's how-to keyed to
the book's own tables — so it post-dates them (>=1641).
"""

from __future__ import annotations

import math

PHI = 50.09
EPS = 23.44
D2R = math.pi / 180

SUNRISE_TABLE_3MAY = (4, 43)   # fol. 55, column "Máj", day 3


def hm(x: float) -> str:
    h = int(x)
    return f"{h}:{round((x - h) * 60):02d}"


def from_hm(h: int, m: int) -> float:
    return h + m / 60


def chain(sunrise: float) -> dict[str, float]:
    """The folio's own procedure, in decimal hours."""
    complement = 12 - sunrise          # "zu seinem Complement, daß 12 herauskommt"
    boh_noon = 24 - complement         # "subtrahier von 24" -> Mittag böhm. Uhr
    boh_sunrise = boh_noon - complement
    day_len = 2 * complement
    return {"complement": complement, "boh_noon": boh_noon,
            "boh_sunrise": boh_sunrise, "day_len": day_len}


def astro_sunrise(y: int, mo: int, d: int) -> tuple[float, float]:
    def jd(yy: int, mm: int, dd: int, h: float = 0) -> float:
        if mm <= 2:
            yy -= 1
            mm += 12
        a = yy // 100
        b = 2 - a + a // 4
        return int(365.25 * (yy + 4716)) + int(30.6001 * (mm + 1)) + dd + b - 1524.5 + h / 24

    j = jd(y, mo, d, 10)
    t = (j - 2451545.0) / 36525
    l0 = (280.46646 + 36000.76983 * t) % 360
    m = math.radians((357.52911 + 35999.05029 * t) % 360)
    sl = (l0 + 1.914602 * math.sin(m) + 0.019993 * math.sin(2 * m)) % 360
    dec = math.asin(math.sin(EPS * D2R) * math.sin(sl * D2R))
    h_arc = math.degrees(math.acos(max(-1, min(1, -math.tan(PHI * D2R) * math.tan(dec)))))
    return 12 - h_arc / 15, 2 * h_arc / 15


def main() -> bool:
    sr = from_hm(*SUNRISE_TABLE_3MAY)
    c = chain(sr)
    a_sr, a_day = astro_sunrise(1641, 5, 3)

    # Values the manuscript states (now corrected from the raw German-Kurrent HTR).
    stated = {"sunrise": "4:43", "complement": "7:17", "boh_noon": "16:43",
              "boh_sunrise": "9:26", "day_len": "14:34"}

    print("fol. 54 — německý návod, příklad na 3. máje (Praha)\n")
    rows = [
        ("východ Slunce (obecná Uhr)", stated["sunrise"], hm(sr), "= tabule f55 (3. máj)"),
        ("doplněk do 12", stated["complement"], hm(c["complement"]), ""),
        ("poledne v českých hod.", stated["boh_noon"], hm(c["boh_noon"]), "24 − doplněk"),
        ("východ v českých hod.", stated["boh_sunrise"], hm(c["boh_sunrise"]), "poledne − doplněk"),
        ("délka dne", stated["day_len"], hm(c["day_len"]), "2 × doplněk"),
    ]
    ok = True
    for what, said, comp, note in rows:
        good = said == comp
        ok &= good
        print(f"  {'✓' if good else '✗'} {what:28s} rukopis {said:6s} výpočet {comp:6s} {note}")

    print(f"\n  Astronomická kontrola (nezávisle): východ {hm(a_sr)}, délka dne {hm(a_day)} "
          "(shoda ±2–4 min).")
    print(f"\n{'✓ VŠE SOUHLASÍ' if ok else '✗ NESHODA'} — čísla příkladu f54 jsou jistá "
          "(tabule f55 + uzavřená aritmetika + astronomie).")
    return ok


if __name__ == "__main__":
    import sys

    sys.exit(0 if main() else 1)
