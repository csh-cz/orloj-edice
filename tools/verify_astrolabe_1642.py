# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Verify the worked example in the Astrolabium parvum (fol. 78–79): night
time-telling from the Moon's shadow, dated 1 November 1642.

The manuscript states for that night (Gregorian calendar, Prague):
    Sun on 8° Scorpio; sunset 4 h 48 min German (= 16:48); Moon on 1° Pisces;
    the Moon's shadow on the sundial hit the noon line, and the astrolabe gave
    7 h 48 min German = 3 Czech (Italian) hours after sunset.

We recompute all of it from first principles (Meeus low-precision Sun + Moon,
spherical sunset, Moon meridian transit) and check the agreement. This both
confirms the calculation and fixes the dating of the section to 1642 — the Sun's
8° Scorpio pins it to ~1 Nov (and proves the Gregorian calendar), the Moon's 1°
Pisces pins the year.
"""

from __future__ import annotations

import math

D2R = math.pi / 180
R2D = 180 / math.pi
PHI = 50.09          # Prague latitude
EPS = 23.4378        # obliquity, ~1642
SIGN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
        "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


def norm(x: float) -> float:
    return x % 360


def zodiac(lon: float) -> str:
    lon = norm(lon)
    s = int(lon // 30)
    return f"{lon - 30 * s:.1f}° {SIGN[s]}"


def jd_greg(y: int, m: int, d: int, hour: float = 0.0) -> float:
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5 + hour / 24


def sun_lon(jd: float) -> float:
    t = (jd - 2451545.0) / 36525
    l0 = norm(280.46646 + 36000.76983 * t + 0.0003032 * t * t)
    m = norm(357.52911 + 35999.05029 * t - 0.0001537 * t * t) * D2R
    c = ((1.914602 - 0.004817 * t) * math.sin(m) + (0.019993 - 0.000101 * t) * math.sin(2 * m)
         + 0.000289 * math.sin(3 * m))
    return norm(l0 + c)


def _moon_args(jd: float):
    t = (jd - 2451545.0) / 36525
    lp = norm(218.3164477 + 481267.88123421 * t - 0.0015786 * t * t)
    dd = norm(297.8501921 + 445267.1114034 * t - 0.0018819 * t * t)
    m = norm(357.5291092 + 35999.0502909 * t)
    mp = norm(134.9633964 + 477198.8675055 * t + 0.0087414 * t * t)
    f = norm(93.272095 + 483202.0175233 * t)
    return lp, dd, m, mp, f


def moon_lon(jd: float) -> float:
    lp, dd, m, mp, f = _moon_args(jd)
    terms = [(6.288774, mp), (1.274027, 2 * dd - mp), (0.658314, 2 * dd), (0.213618, 2 * mp),
             (-0.185116, m), (-0.114332, 2 * f), (0.058793, 2 * dd - 2 * mp),
             (0.057066, 2 * dd - m - mp), (0.053322, 2 * dd + mp), (0.045758, 2 * dd - m),
             (-0.040923, m - mp), (-0.034720, dd), (-0.030383, m + mp), (0.015327, 2 * dd - 2 * f),
             (-0.012528, mp + 2 * f), (0.010980, mp - 2 * f), (0.010675, 4 * dd - mp),
             (0.010034, 3 * mp), (0.008548, 4 * dd - 2 * mp)]
    return norm(lp + sum(a * math.sin(ang * D2R) for a, ang in terms))


def moon_lat(jd: float) -> float:
    """Moon's ecliptic latitude β (deg) — the term the astrolabe method ignores."""
    _lp, dd, m, mp, f = _moon_args(jd)
    terms = [(5.128122, f), (0.280602, mp + f), (0.277693, mp - f), (0.173237, 2 * dd - f),
             (0.055413, 2 * dd - mp + f), (0.046271, 2 * dd - mp - f), (0.032573, 2 * dd + f),
             (0.017198, 2 * mp + f), (0.009266, 2 * dd + mp - f), (0.008822, 2 * mp - f),
             (0.008216, 2 * dd - m - f), (0.004324, 2 * dd - 2 * mp - f)]
    return sum(a * math.sin(ang * D2R) for a, ang in terms)


def ra_from_lon(lon: float, lat: float = 0.0) -> float:
    le, be, e = lon * D2R, lat * D2R, EPS * D2R
    return norm(math.atan2(math.sin(le) * math.cos(e) - math.tan(be) * math.sin(e),
                           math.cos(le)) * R2D)


def decl_from_lon(lon: float) -> float:
    return math.asin(math.sin(EPS * D2R) * math.sin(lon * D2R)) * R2D


def hm(hours: float) -> str:
    h = int(hours)
    return f"{h}:{round((hours - h) * 60):02d}"


def main() -> bool:
    jd_noon = jd_greg(1642, 11, 1, 11.0)   # ~noon Prague (UT ≈ local − 1 h)
    sl = sun_lon(jd_noon)
    ml_noon = moon_lon(jd_noon)            # tabular/calendar Moon = noon position
    # sunset
    dec = decl_from_lon(sl)
    h_arc = math.degrees(math.acos(max(-1, min(1, -math.tan(PHI * D2R) * math.tan(dec * D2R)))))
    sunset = 12 + h_arc / 15
    # Moon meridian transit → apparent solar time.
    # The astrolabe places only the Moon's ECLIPTIC LONGITUDE (β = 0, treated like the
    # Sun), so the manuscript's computed time corresponds to ra_from_lon(ml, lat=0).
    ra_sun = ra_from_lon(sl)
    transit = 12 + norm(ra_from_lon(ml_noon, 0.0) - ra_sun) / 15      # instrument (β = 0)
    beta = moon_lat(jd_noon)
    transit_real = 12 + norm(ra_from_lon(ml_noon, beta) - ra_sun) / 15  # true sky (with β)
    czech = transit - sunset               # Italian/Czech hours since sunset

    print("Astrolabium parvum, fol. 78–79 — kontrola příkladu z 1. XI 1642 (Praha, greg.)\n")
    rows = [
        ("Slunce", "8° Scorpio", zodiac(sl)),
        ("Měsíc (v poledne)", "1° Pisces", zodiac(ml_noon)),
        ("Západ Slunce (něm.)", "4:48 (16:48)", hm(sunset)),
        ("Kulminace Měsíce (něm.)", "7:48 (19:48)", hm(transit)),
        ("České (italské) hodiny", "3", hm(czech)),
    ]
    for what, text, comp in rows:
        print(f"  {what:26s} rukopis {text:14s} výpočet {comp}")

    print("\n  Pozn. k metodě: astroláb pracuje jen v ekliptikální délce (β = 0). Měsíc měl ale")
    print(f"  β = {beta:+.1f}°, takže SKUTEČNĚ kulminoval v {hm(transit_real)} — tj. o "
          f"{abs(transit_real - transit) * 60:.0f} min dříve než")
    print("  dá astroláb. Není to chyba přepisu/aritmetiky, ale inherentní mez dobové metody.")

    checks = [
        205 <= sl <= 222,                  # ~8° Scorpio (Scorpio = 210–240)
        327 <= ml_noon <= 335,             # ~1° Pisces (Pisces = 330–360, allow ±)
        abs(sunset - 16.8) < 0.1,          # 16:48 ± 6 min
        abs(transit - 19.8) < 0.1,         # 19:48 ± 6 min
        abs(czech - 3.0) < 0.1,            # 3 Czech hours
    ]
    ok = all(checks)
    print(f"\n{'✓ VŠE SOUHLASÍ' if ok else '✗ NESHODA'} — datace sekce: 1. listopadu 1642 "
          "(gregoriánský kalendář).")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
