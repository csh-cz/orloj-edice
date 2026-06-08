# SPDX-FileCopyrightText: 2026 David Knespl
"""Rebuild f3 (0003.json) as a faithful symmetric day-length table.

Headers are transcribed from the manuscript (Dnové měsíců / Svátkové podle
kalendáře / Dlúhost dne / Slunce celého orloje / Slunce na díl orloje /
Poledne celého orloje / Západ celého orloje).

Cells hold ONLY the transcription: feast names (lightly normalised) and the
zodiac entry "Slunce na <symbol>". All editorial commentary (sign names,
solstice/equinox, the Bohemian-hour gloss, calendar cross-checks) lives in
the editorial note, not in the cells. [?] = uncertain reading that does not
match a known saint for that date. Numeric columns are the MS's own exact
functions of day length (verified to the minute).
"""
import json

MON = {"led": "Leden", "úno": "Únor", "bře": "Březen", "dub": "Duben",
       "kvě": "Máj", "čvn": "Červen", "pro": "Prosinec"}


def hm(mins):
    return f"{mins // 60}:{mins % 60:02d}"


# (row, day-length min, spring date "D. mon", spring feast transcription)
SPINE = [
    (1, 470, "23. pro", "Slunce na ♑"),
    (2, 480, "4. led", ""),
    (3, 490, "11. led", ""),
    (4, 500, "16. led", ""),
    (5, 510, "19. led", "Ferdinanda"),
    (6, 520, "21. led", "Fabiána a Šebestiána · Anežky Panny · Slunce na ♒"),
    (7, 530, "24. led", "Emerenciány Panny"),
    (8, 540, "27. led", "Jana Zlatoústého"),
    (9, 550, "30. led", ""),
    (10, 560, "2. úno", "Hromnice"),
    (11, 570, "5. úno", "Doroty Panny"),
    (12, 580, "8. úno", ""),
    (13, 590, "11. úno", "Eufrozyny Panny"),
    (14, 600, "14. úno", "Valentina biskupa"),
    (15, 610, "17. úno", "Polykronia"),
    (16, 620, "20. úno", "Simeona biskupa · Slunce na ♓"),
    (17, 630, "23. úno", ""),
    (18, 640, "26. úno", "Alexandra biskupa"),
    (19, 650, "1. bře", "Samuele"),
    (20, 660, "4. bře", ""),
    (21, 670, "7. bře", "Tomáše Akvinského"),
    (22, 680, "9. bře", "Cyrila a Metoděje"),
    (23, 690, "13. bře", ""),
    (24, 700, "15. bře", ""),
    (25, 710, "18. bře", "Anselma"),
    (26, 720, "21. bře", "Benedikta opata · Slunce na ♈"),
    (27, 730, "24. bře", ""),
    (28, 740, "26. bře", "Haštala mučedníka"),
    (29, 750, "29. bře", ""),
    (30, 760, "31. bře", ""),
    (31, 770, "3. dub", ""),
    (32, 780, "6. dub", ""),
    (33, 790, "8. dub", ""),
    (34, 800, "11. dub", "Lva papeže"),
    (35, 810, "14. dub", ""),
    (36, 820, "16. dub", ""),
    (37, 830, "19. dub", "Slunce na ♉"),
    (38, 840, "23. dub", "Vojtěcha"),
    (39, 850, "26. dub", ""),
    (40, 860, "29. dub", "Petra mučedníka"),
    (41, 870, "2. kvě", "Žikmunda krále"),
    (42, 880, "5. kvě", ""),
    (43, 890, "8. kvě", "Stanislava"),
    (44, 900, "11. kvě", ""),
    (45, 910, "14. kvě", "Bonifacia"),
    (46, 920, "18. kvě", "Slunce na ♊"),
    (47, 930, "22. kvě", "Heleny Panny"),
    (48, 940, "27. kvě", ""),
    (49, 950, "1. čvn", "Nikodema"),
    (50, 960, "11. čvn", ""),
    (51, 970, "23. čvn", "Slunce na ♋"),
]

# autumn block read from scan. row -> (feast transcription, day-of-month, month)
AUTUMN = {
    1: ("", "", "Prosinec"),
    4: ("Valeriána", "2.", "Prosinec"),
    7: ("Slunce na ♐ · Alžběty vdovy", "19.", "Listopad"),
    8: ("Jana Milostivého [?]", "16.", "Listopad"),
    14: ("Šimona a Judy", "28.", "Říjen"),
    16: ("Slunce na ♏ · Korduly Panny", "22.", "Říjen"),
    19: ("Havla opata", "16.", "Říjen"),
    22: ("Diviše biskupa", "9.", "Říjen"),
    25: ("Václava", "28.", "Září"),
    26: ("Slunce na ♎", "23.", "Září"),
    27: ("Matouše apoštola", "21.", "Září"),
    29: ("Tobiáše", "12.", "Září"),
    31: ("Zachariáše", "6.", "Září"),
    32: ("Rozálie Panny", "4.", "Září"),
    35: ("Stětí svatého Jana", "29.", "Srpen"),
    37: ("Bartoloměje · Slunce na ♍", "24.", "Srpen"),
    41: ("Nanebevzetí Panny Marie", "15.", "Srpen"),
    43: ("Zuzany mučednice · Cyriaka", "11.", "Srpen"),
    44: ("Matky Boží Sněžné", "5.", "Srpen"),
    46: ("Porciunkuly", "2.", "Srpen"),
    47: ("Jakuba apoštola · Slunce na ♌", "25.", "Červenec"),
    48: ("Maří Magdaleny", "22.", "Červenec"),
    49: ("Jindřicha", "13.", "Červenec"),
    51: ("", "", "Červen"),
}

# Headers transcribed from the manuscript (margin "Měsíc" is an editorial label).
COLS = [
    "Měsíc", "Dnové měsíců", "Svátkové podle kalendáře",
    "Dlúhost dne", "Slunce celého orloje", "Slunce na díl orloje",
    "Poledne celého orloje", "Západ celého orloje",
    "Svátkové podle kalendáře", "Dnové měsíců", "Měsíc",
]

cells = [{"row": 0, "col": c, "text": n, "row_span": 1, "col_span": 1}
         for c, n in enumerate(COLS)]

prev_mon = prev_amon = None
for row, dd, datum, feast in SPINE:
    half = dd / 2
    day, mon = datum.split(". ")
    mon_full = MON[mon]
    mon_cell = mon_full if mon_full != prev_mon else ""
    prev_mon = mon_full
    afeast, aday, amon = AUTUMN.get(row, ("", "", prev_amon or ""))
    amon_cell = amon if amon != prev_amon else ""
    prev_amon = amon
    vals = [
        mon_cell, day + ".", feast,
        hm(dd), hm(1440 - dd), hm(round(720 - half)),
        hm(round(1440 - half)), hm(round(half)),
        afeast, aday, amon_cell,
    ]
    cells += [{"row": row, "col": c, "text": v, "row_span": 1, "col_span": 1}
              for c, v in enumerate(vals)]

out = [{"region_id": "f3_daylength_haijek", "cells": cells}]
json.dump(out, open("work/orloj1587/tables_clean/0003.json", "w"),
          ensure_ascii=False, indent=1)
qmark = sum(1 for _, _, _, f in SPINE if "[?]" in f) + \
        sum(1 for v in AUTUMN.values() if "[?]" in v[0])
print("rows:", len(SPINE), "cols:", len(COLS), "cells:", len(cells), "[?]:", qmark)
