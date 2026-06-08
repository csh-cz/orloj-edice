# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Generate a static HTML edition (one file per folio) from PAGE XML.

Features:
  - page-per-folio (index.html + pNNNN.html) with prev/next + keyboard nav
  - view modes: Diplomatický / Normalizovaný / Teige (srovnání)
  - structure-aware rendering: regions typed marginalia / heading are placed
    accordingly (falls back to paragraph when untagged)
  - images are not republished — each page links out to the AHMP viewer
  - Teige (1570) passage shown side-by-side via best-effort alignment

Shared CSS/JS live under edition/assets/.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from transcribus.processing.normalize import normalize_text
from transcribus.processing.page_xml import (
    Table,
    TextRegion,
    marginalia_bboxes,
    parse_page_xml,
)
from transcribus.processing.teige import TeigeIndex, fold

try:  # Pillow is optional; without it the marginalia page is skipped (no crops).
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

_MARGINALIA = {"marginalia", "margin-text", "margin"}
_HEADING = {"heading", "header", "title", "caption"}

_SECTION_LABEL = {
    "taborsky": "Opis Táborského zprávy o orloji",
    "jine": "Další části knihy (bez referenční edice)",
}
_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def derive_sections(
    matched: set[int], total: int, *, gap: int = 2, work_slug: str = ""
) -> list[tuple[str, int, int, str]]:
    """Group folios into sections from the Teige-match blocks.

    Contiguous matched folios (small gaps bridged) form a Táborský section; the
    stretches between them are 'other writings'. Returns (kind, lo, hi, label).
    """
    # Merge matched folios into intervals, bridging gaps <= ``gap``.
    intervals: list[list[int]] = []
    for n in sorted(matched):
        if intervals and n - intervals[-1][1] <= gap + 1:
            intervals[-1][1] = n
        else:
            intervals.append([n, n])

    sections: list[tuple[str, int, int]] = []
    cur = 1
    for lo, hi in intervals:
        if cur < lo:
            sections.append(("jine", cur, lo - 1))
        sections.append(("taborsky", lo, hi))
        cur = hi + 1
    if cur <= total:
        sections.append(("jine", cur, total))
    if not intervals:
        sections = [("jine", 1, total)]

    # Originál 1570 = jeden souvislý text (Zpráva); „jiné“ oddíly jsou jen vazba/přídeští.
    label_1570 = {
        "taborsky": "Zpráva o orloji pražském (1570)",
        "jine": "Vazba a přídeští",
    }
    is_1570 = "1570" in work_slug
    out: list[tuple[str, int, int, str]] = []
    for i, (kind, lo, hi) in enumerate(sections, start=1):
        if is_1570:
            label = label_1570[kind]
        else:
            label = f"Oddíl {_ROMAN[i] if i < len(_ROMAN) else i} — {_SECTION_LABEL[kind]}"
        out.append((kind, lo, hi, label))
    return out


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


# Editorial apparatus inside the running text: everything in square brackets is an
# editorial intervention (expansion „[Novembris]", uncertain reading „[?]", gloss
# „[= 116]"). Wrap each so the reader can dim/hide them (the „Ediční značky" toggle)
# for uninterrupted reading. Applied to already-escaped HTML (brackets aren't escaped).
_ED_RE = re.compile(r"\[[^\]]*\]")


def _apparatus(escaped: str) -> str:
    return _ED_RE.sub(lambda m: f'<span class="ed">{m.group(0)}</span>', escaped)


_ZODIAC = "♈♉♊♋♌♍♎♏♐♑♒♓"


def _zodiac_textstyle(s: str) -> str:
    """Wrap zodiac signs so they render as monochrome text glyphs, not color emoji.

    Adds the U+FE0E text-presentation selector and a .zod span (CSS forces text).
    """
    for ch in _ZODIAC:
        s = s.replace(ch, f'<span class="zod">{ch}\ufe0e</span>')
    return s


# Folia, jejichž jazyk NENÍ čeština (latina, němčina) — česká normalizace by je zkomolila
# (g→j apod.), takže se u nich „normalizovaný" pohled rovná diplomatickému.
_NO_NORMALIZE: frozenset[int] = frozenset({4, 51, 52, 54, 62, 80})


def _line_html(
    line: str, *, normalize: bool = True, page_nr: int = 0, n: int | None = None
) -> str:
    """Render one transcription line (diplomatic + normalized span).

    When ``n`` is given the line gets a citable id (``pNNlN``) and a margin
    line-number gutter; the number itself is shown only every 5th line (edition
    convention), but every line is individually anchorable for citation.
    """
    norm = normalize_text(line) if normalize else line
    dip = _apparatus(_esc(line))
    nor = _apparatus(_esc(norm))
    if n is None:
        return (
            f'<span class="ln"><span class="dipl">{dip}</span>'
            f'<span class="norm">{nor}</span></span>'
        )
    lid = f"p{page_nr}l{n}"
    cls = "lno show" if n % 5 == 0 else "lno"
    gutter = (
        f'<a class="{cls}" href="#{lid}" data-n="{n}" '
        f'title="Kopírovat citaci řádku">{n}</a>'
    )
    return (
        f'<span class="ln" id="{lid}" data-n="{n}">{gutter}'
        f'<span class="dipl">{dip}</span>'
        f'<span class="norm">{nor}</span></span>'
    )


def _clean_block(main_lines: list[str], page_nr: int, do_norm: bool) -> str:
    """Render corrected clean text as numbered lines + a collapsed editorial note.

    Blank lines become paragraph breaks. Trailing ``[Ediční pozn.: …]`` / ``[Pozn. …]``
    lines are lifted out of the running text into a collapsible apparatus block so they
    don't interrupt reading.
    """
    ed_start = re.compile(r"^\[(?:[Ee]diční pozn|[Pp]ozn[.:])")
    text_lines: list[str] = []
    ed_lines: list[str] = []
    in_ed = False
    for ln in main_lines:
        if not in_ed and ed_start.match(ln.lstrip()):
            in_ed = True
        (ed_lines if in_ed else text_lines).append(ln)

    out = [
        '<span class="clean-flag">opravený přepis</span>',
        f'<div class="lines" data-folio="{page_nr}">',
    ]
    n = 0
    for ln in text_lines:
        if not ln.strip():
            out.append('<span class="pbreak"></span>')
            continue
        n += 1
        out.append(_line_html(ln, normalize=do_norm, page_nr=page_nr, n=n))
    out.append("</div>")

    ed_text = " ".join(s.strip() for s in ed_lines if s.strip())
    if ed_text:
        ed_text = re.sub(r"^\[(?:[Ee]diční pozn|[Pp]ozn)[.:\s]*", "", ed_text).rstrip("] ")
        out.append(
            '<details class="ed-note"><summary>Ediční poznámka</summary>'
            f"<p>{_apparatus(_esc(ed_text))}</p></details>"
        )
    return "".join(out)


def _region_html(region: TextRegion) -> str:
    inner = "\n".join(_line_html(line) for line in region.lines if line)
    if not inner:
        return ""
    if region.rtype in _MARGINALIA:
        return f'<aside class="region marginalia">{inner}</aside>'
    if region.rtype in _HEADING:
        return f'<h3 class="region heading">{inner}</h3>'
    return f'<p class="region paragraph">{inner}</p>'


def _table_html(table: Table) -> str:
    """Render a TableRegion as an HTML <table>, honouring row/col spans."""
    by_pos = {(c.row, c.col): c for c in table.cells}
    occupied: set[tuple[int, int]] = set()
    rows_html = []
    for r in range(table.n_rows()):
        tds = []
        for c in range(table.n_cols()):
            if (r, c) in occupied:
                continue
            cell = by_pos.get((r, c))
            if cell is None:
                tds.append("<td></td>")
                continue
            for dr in range(cell.row_span):
                for dc in range(cell.col_span):
                    occupied.add((r + dr, c + dc))
            span = ""
            if cell.row_span > 1:
                span += f' rowspan="{cell.row_span}"'
            if cell.col_span > 1:
                span += f' colspan="{cell.col_span}"'
            tds.append(f"<td{span}>{_esc(cell.text)}</td>")
        rows_html.append("<tr>" + "".join(tds) + "</tr>")
    return '<table class="page-table">' + "".join(rows_html) + "</table>"


def _teige_html(passage: str | None, page_folded: set[str]) -> str:
    if not passage:
        return (
            '<div class="teige-empty">Mimo Táborského zprávu — tato část knihy '
            "nemá referenční edici (Teige vydal pouze Táborského text).</div>"
        )
    out = []
    for token in passage.split(" "):
        f = fold(token)
        cls = "hit" if f and f in page_folded else ""
        out.append(f'<span class="{cls}">{_esc(token)}</span>' if cls else _esc(token))
    return '<div class="teige-text">' + " ".join(out) + "</div>"


# Popisky tabulkových folií (z hlaviček; data zatím nepřepsána). Komputistický aparát.
_TABLE_CAPTIONS: dict[int, str] = {
    2: "Tabule dlúhosti dne i noci, vejchodu, poledne a západu — předtištěná (z větší části nevyplněná) tabule pro zpravování orloje.",
    3: "Perpetuální tabule délky dne i noci, východu, poledne a západu Slunce v orlojních (českých) i obecných hodinách — po 10min krocích délky dne od zimního k letnímu slunovratu; symetrická (jaro vlevo, podzim vpravo). Opis tištěné tabule Tadeáše Hájka z Hájku „Tabule dlúhosti dne a noci k spravování orloje“ (1574), zhotovené přímo pro pražský orloj; výška pólu 50° (Praha), upraveno na nový kalendář; opis ≈ 1689 (ruka D). Viz poznámku pod tabulkou.",
    50: "Tabula, ex qua Litera Dominicalis desumitur in ingressu cum Cyclo Solari („N. I”) — nedělní písmeno pro každý rok 28letého slunečního cyklu, juliánské i gregoriánské.",
    55: "Tabule vejchodu Slunce wedle polovičního orloje — čas východu pro každý den (1–31) a měsíc (h:min).",
    56: "Tabula, ex qua Litera Dominicalis desumitur („N. I”) — duplikát tabule z fol. 50 (nedělní písmeno, juliánské i gregoriánské).",
    57: "Tabula Epactarum („N. 2”) — epakta pro každý zlatý počet (1–19), juliánská a gregoriánská (období ad 1700 / 1700–1900 / 1900–2200).",
    58: "Tabula Festorum Mobilium Calendarii Juliani — pohyblivé svátky pro každé z 35 možných dat Velikonoc (22. III – 25. IV): Septuagesima, Estomihi (Quinquagesima), Pascha, Ascensio, Pentecostes, Dominica I Adventus; indexováno zlatým počtem a nedělním písmenem.",
    59: "Tabula Festorum Mobilium Calendarii Gregoriani — gregoriánské dvojče f58 (tytéž svátky), indexováno epaktou a nedělním písmenem; zakončeno rubrikou „Incipit Adventus Domini Sabbato post Catharinam“.",
    60: "Tabula Intervalli [Paschae] in Calendario Juliano — datum velikonočního úplňku/Velikonoc podle zlatého počtu (1–19) a nedělního písmene (A–G).",
    61: "Tabula Intervalli Paschae in Calendario Gregoriano — gregoriánské dvojče f60: každá buňka „týden doplněk“ podle epakty (řádek) a nedělního písmene A–G (sloupec); dole řádek „Dies Concurrentes“ (0–6). Týden = pořadí týdne gregoriánských Velikonoc.",
    62: "O slunečném cyklu (28letém), aneb jak najít nedělní písmeno pro každý rok.",
    63: "Výpočet v obojím — starém i novém — kalendáři (pokrač.).",
    64: "O zlatém počtu — cyklus decennovenalis (19letý lunární), měsíčný cyklus.",
    65: "Ukazatel nového měsíce — návodná próza (česky) k výpočtu novoluní.",
    66: "Calendarium perpetuum — pro každý den (1–31, řádky) a měsíc (sloupce, vždy dvojice Epacta / Litera): epakta, jejíž novoluní na ten den padá, a feriální/nedělní písmeno dne.",
    67: "Komputus na prstech — výpočet, který měsíc má 31/30/29 dní (Ex Gustavi Selen Cryptographia, fol. 487).",
    68: "Nalezení nového a plného měsíce pro každý měsíc — výpočet z epakt.",
    69: "Malá násobilka (pythagorejská tabule) — trojúhelníková, součiny 2×2 až 10×10.",
}

# Stručné popisky do seznamu folií (úvodní strana). Mají přednost před incipitem ze
# surového HTR, který u zpracovaných folií ukazoval staré chyby. Próza f5–49 zůstává
# na incipitu (rozpoznaný text), strukturovaná folia dostávají kurátorský popis.
_FOLIO_SNIP: dict[int, str] = {
    2: "Předtištěná (z větší části nevyplněná) tabule pro zpravování orloje",
    3: "Hájkova perpetuální tabule délky dne, východu, poledne a západu Slunce (jaro/podzim, nový kalendář)",
    4: "Latinský epigram o sedmi pražských pahorcích („Praha jako nový Řím“)",
    # Táborského Zpráva (kap. I–XVIII): začátky kapitol ukotveny rukopisnými záhlavími
    # („Kapitula N“) a titulními frázemi v textu folií; pokračování „(pokrač.)“.
    5: "Táborský — titul a předmluva (Zpráva o orloji pražském)",
    6: "Táborský — titul, autor a rok (Jan Táborský, 1570)",
    7: "Táborský — dedikace radě Starého Města pražského",
    8: "Táborský — rozdělení na XVIII kapitol; začíná kap. I (chvála orloje)",
    9: "Táborský — kap. I: chvála orloje pražského (pokrač.)",
    10: "Táborský — kap. II: čeho orloj a jeho zprávce potřebuje",
    11: "Táborský — kap. III–V: o rozdílu orloje; první, druhá a třetí strana",
    12: "Táborský — kap. VI: čtvrtá strana — kalendář a počet hodin",
    13: "Táborský — kap. VI (pokrač.)",
    14: "Táborský — kap. VI (pokrač.)",
    15: "Táborský — kap. VI (pokrač.)",
    16: "Táborský — kap. VI (pokrač.)",
    17: "Táborský — kap. VI (pokrač.)",
    18: "Táborský — kap. VII: vypsání první strany a sféry",
    19: "Táborský — kap. VII (pokrač.)",
    20: "Táborský — kap. VII (pokrač.)",
    21: "Táborský — kap. VII (pokrač.)",
    22: "Táborský — kap. VII (pokrač.)",
    23: "Táborský — kap. VII (pokrač.)",
    24: "Táborský — kap. VII (pokrač.)",
    25: "Táborský — kap. VIII–IX: kola slunce a měsíce; kolo sluneční",
    26: "Táborský — kap. IX: kolo sluneční (pokrač.)",
    27: "Táborský — kap. X: hlavní kolo (proč se neobrátí jednou za hodinu)",
    28: "Táborský — kap. XI: kolo zvířetníku (s dokončením kap. X)",
    29: "Táborský — kap. XII: kolo měsíce",
    30: "Táborský — kap. XIII: zpravení pochybení v běhu měsíce a slunce",
    31: "Táborský — kap. XIII (pokrač.)",
    32: "Táborský — kap. XIV: napravení kalendáře s počtem hodin",
    33: "Táborský — kap. XIV (pokrač.)",
    34: "Táborský — kap. XV: poslední tajnost orloje",
    35: "Táborský — kap. XVI: počet polouorlojní",
    36: "Táborský — kap. XVII: měnění a neustavičnost orloje",
    37: "Táborský — kap. XVIII: summa spisu",
    38: "Táborský — kap. XVIII: summa spisu (pokrač.)",
    39: "Táborský — kap. XVIII: summa spisu (pokrač.)",
    40: "Táborský — kap. XVIII: summa spisu (pokrač.)",
    41: "Táborský — kap. XVIII: summa spisu (pokrač.)",
    42: "Táborský — kap. XVIII: summa spisu (pokrač.)",
    43: "Táborský — závěr: osobní zpráva o orloji a jeho opravách",
    44: "Táborský — závěr (pokrač.)",
    45: "Táborský — závěr (pokrač.)",
    46: "Táborský — závěr: „summou krátce zavírám“ (pokrač.)",
    47: "Táborský — závěr (pokrač.)",
    48: "Táborský — poděkování a chvála Bohu",
    49: "Táborský — závěrečné verše a kolofon",
    50: "Tabule nedělního písmene (Litera Dominicalis), 28letý sluneční cyklus",
    51: "List purkmistrů 1410 — německy (opsáno 1628)",
    52: "List purkmistrů 1410 — německy (pokrač.)",
    53: "List purkmistrů 1410 — dobový český překlad",
    54: "List purkmistrů — český překlad; německý návod přepočtu hodin",
    55: "Tabule východu Slunce (obecné hodiny) pro každý den a měsíc",
    56: "Tabule nedělního písmene — duplikát fol. 50",
    57: "Tabule epakt (Tabula Epactarum) podle zlatého počtu",
    58: "Tabule pohyblivých svátků (Festa mobilia), nový kalendář",
    59: "Tabule pohyblivých svátků (pokrač.)",
    60: "Tabule intervalu juliánských Velikonoc (zlatý počet × nedělní písmeno)",
    61: "Tabule intervalu gregoriánských Velikonoc (dvojče fol. 60)",
    62: "O slunečním cyklu (28letém) — jak najít nedělní písmeno",
    63: "Výpočet ve starém i novém kalendáři (pokrač.)",
    64: "O zlatém počtu — 19letý lunární cyklus",
    65: "Ukazatel nového měsíce — návodná próza",
    66: "Tabule epakt / novoluní po dnech roku",
    67: "Komputus na prstech — délka měsíců (31/30/29 dní)",
    68: "Nalezení nového a plného měsíce — výpočet z epakt",
    69: "Malá násobilka (pythagorejská tabule)",
    70: "Astrolabium parvum (~1642, překlad F. Rittera; ruka C) — úvod a návod",
    71: "Astrolabium parvum — návod (pokrač.)",
    72: "Astrolabium parvum — návod (pokrač.)",
    73: "Astrolabium parvum — návod (pokrač.)",
    74: "Astrolabium parvum — návod (pokrač.)",
    75: "Astrolabium parvum — návod (pokrač.)",
    76: "Astrolabium parvum — návod (pokrač.)",
    77: "Astrolabium parvum — návod (pokrač.)",
    78: "Astrolabium parvum — návod (pokrač.)",
    79: "Astrolabium parvum — návod (závěr)",
    80: "Dva latinské epigramy (Pythagoras, Archimedes) + nákres pravoúhlého trojúhelníku",
}

# Věrný přepis rukopisného záhlaví tabule — renderuje se NAD tabulkou (HTML, kurzíva,
# ediční doplňky v hranatých závorkách). Editorský popis patří do poznámky pod tabulkou.
_TABLE_HEADING_TX: dict[int, str] = {
    3: (
        '<p class="ms-heading">Tabule dlúhosti Dne i Noci, vejchodu i poledne i západu '
        "[Slunce], spravování Orloje obojího — celého i polovičního — kterak ten srovnán býti "
        "má podle jeho hodin, a to přes celý rok položená, [pro] České zemně a k vyvýšení Polum "
        "L [= 50] graduů, od někdy D. Thadeáše Hájka z Hájku před CXVI [= 116] lety vydaná, "
        "a nyní dle Nového kalendáře spravena. Léta M·DC·LXXXIX [= 1689].</p>"
    ),
}

# Souvislý text (próza) na tabulkovém foliu — renderuje se POD tabulkou jako přepis.
_TABLE_PROSE: dict[int, str] = {
    55: (
        '<div class="ms-prose"><span class="ms-prose-label">Návod pod tabulkou — přepis</span>'
        "<p>Z této tabule východu sobě zase vynajdeš západ Slunce wedle polovičního, poledne a "
        "východ wedle celého orloje, jako i dlúhost dne, takto: přidáš ke dni východu Slunce "
        "komplementum do 12; ten týž počet odejmi od 24 hodin — co zbyde, ukáže poledne hodin "
        "českých; a odejma týž počet od téhož [poledne], ukáže východ wedle českých hodin. Když "
        "pak dotčený počet zdvojíš, ukáže dlúhost dne.</p>"
        "<p>Ku příkladu, chci to všecko věděti z máje: i nacházím v této tabuli východ Slunce "
        "wedle polovičního orloje ve <b>4 hod. 43 min</b>. Přidám k tomu jeho komplementum, aby "
        "bylo 12, totiž <b>7 hod. 17 min</b> — to jest západ hodin polovičných. Odejmu týž počet "
        "od 24 hodin, dostanu <b>16 hod. 43 min</b> — to jest poledne hodin českých. Opět odejmu "
        "odtud týž počet, zůstane mi <b>9 hod. 26 min</b> — to jest východ celý český. Když pak "
        "ten týž počet dvakrát položím, což přinese <b>14 hod. 34 min</b>, ukáže mi dlúhost dne. "
        "A tak ve všech rozuměj.</p>"
        "<p class=\"ms-prose-ed\">[Ediční pozn.: tento <b>český</b> návod je obsahově totožný s "
        "<b>německým</b> návodem dole na fol. 54 — týž postup i týž příklad na 3. května; německý "
        "text je tedy <b>německou paralelou</b> tohoto českého návodu k tabuli východu. (Poledne "
        "„16:43“ čteno z příkladu — HTR podává „16:13“, ale vlastní počet 9:26 i délka dne 14:34 "
        "ukazují 16:43.)]</p></div>"
    ),
}


# Deterministic verification (external computation / astronomy). See tools/verify_computus.py.
_TABLE_VERIFY: dict[int, str] = {
    3: "✓ věrný přepis ze skenu včetně rukopisných nadpisů sloupců. V buňkách je jen přepis "
        "(jména svatých v genitivu a zápis „Slunce na [znamení]“). Jména ověřena proti skenu "
        "i kalendáři; několik svátků neodpovídá standardnímu kalendáři pro daný den (např. "
        "Ferdinanda 19. I, Samuele 1. III, Anselma 18. III; naopak „Cyrila a Metoděje“ 9. III je "
        "starý český svátek před pozdějším přesunem na 5. VII) — čteno věrně podle předlohy, nejde "
        "o chyby přepisu. Jediné zbylé [?] je listopadové jméno u dne 12: první slovo je jistě "
        "„Jana“ (= Jan), připojené přízvisko je však zkráceno a nečitelné (čteno „Ve[?] Pro[?]“) — "
        "proto v buňce jen „Jana [?]“. Datum 12. XI odpovídá v kalendáři sv. Janu Almužníkovi "
        "(„Janu Milostivému“), takže identifikace světce je pravděpodobná, viditelné litery "
        "přízviska ji ale nepotvrzují; ponecháno jako nejisté čtení. (Den byl při kontrole skenu "
        "opraven z chybného 16. na 12. XI; den 16. XI je v tabuli bez čitelného jména.) "
        "Časové sloupce "
        "souhlasí s přepočtem do minuty. Plný přepis záhlaví, význam sloupců, legenda znamení a "
        "vysvětlení českých hodin jsou v poznámce pod tabulkou.",
    50: "✓ ověřeno výpočtem: juliánská i gregoriánská nedělní písmena souhlasí s nezávislým "
        "výpočtem pro všech 28 let slunečního cyklu; gregoriánský sloupec platí pro 17. stol. "
        "(1583–1699), což zároveň datuje použitelnost tabulky.",
    56: "✓ ověřeno výpočtem (duplikát fol. 50): nedělní písmena souhlasí pro všech 28 let.",
    57: "✓ ověřeno výpočtem: všechny tři gregoriánské sloupce epakt souhlasí s nezávislým "
        "výpočtem (Meeus) pro 19 zlatých počtů ve více obdobích; juliánský sloupec = "
        "gregoriánský + 10 (10denní rozdíl kalendářů). Hranice období = gregoriánské korekce.",
    55: "✓ ověřeno astronomicky (pravé Slunce): sezónní průběh časů východu přesně odpovídá "
        "výpočtu pro Prahu (φ ≈ 50,09°) — residuum je ploché přes celý rok (žádná chyba přepisu "
        "ani šířky). Východ je počítán jako střed Slunce na geometrickém obzoru bez refrakce "
        "(konvence perpetuálních tabulí); při této definici |Δ| ≤ 2 min, vůči modernímu východu "
        "(horní okraj + refrakce) je rukopis o ~7 min později. Sekce datovatelná kolem r. 1641 "
        "(viz metodická poznámka).",
    69: "✓ ověřeno: všechny součiny souhlasí (pythagorejská násobilka).",
    60: "✓ dekódováno a ověřeno: první číslo dvojice = pořadí týdne juliánských Velikonoc "
        "(⌊(datum Velikonoc od 1. 3. + 16)/7⌋) — souhlasí s nezávislým výpočtem ve všech 133 "
        "buňkách (19 zlatých počtů × 7 nedělních písmen); druhé číslo je doplněk (34, resp. 35 "
        "minus první). Jde tedy o tabuli „intervalu“ (týdne) juliánských Velikonoc.",
    58: "✓ ověřeno komputisticky (přepis Text Titan I ter + výpočet): pohyblivé svátky jsou "
        "pevné posuny od Velikonoc (Septuagesima −63, Estomihi −49, Ascensio +39, Pentecostes "
        "+49 dní) — shoda 96 % buněk OCR (zbylé odchylky = jediné ambivalentní čtení „9/10“, "
        "vzorec je řeší na 10 → fakticky 100 %). Litera Dominicalis = ABCDEFG[(den Velikonoc − "
        "1) mod 7]; zlatý počet = ten, jehož juliánský velikonoční úplněk (luna XIV) padá na "
        "daný den; Advent I = neděle mezi 27. XI a 3. XII. Hodnoty zde dopočítány vzorcem "
        "(kanonické a úplné), shodné s rukopisem.",
    59: "✓ ověřeno komputisticky (Text Titan I ter + výpočet): tytéž posuny svátků od Velikonoc "
        "jako u f58 — shoda 99 % buněk OCR (zbytek opět „9/10“ → 10). Epakta = (103 − den "
        "Velikonoc) mod 30, s gregoriánskou výjimkou lunární rovnice 24/25/XXV na 17.–18. IV "
        "(přesně jak ji rukopis značí). Hodnoty dopočítány vzorcem (kanonické), shodné s "
        "rukopisem.",
    66: "✓ dekódováno a ověřeno proti skenu: Litera = feriální písmeno dne ABCDEFG[(den v roce − "
        "1) mod 7] (A = 1. I); Epacta = epakta, jejíž ekleziastické novoluní na ten den padá — "
        "klesá po dnech (30 = *), s vynecháním epakty 25 v šesti 29denních lunárních měsících "
        "(II, IV, VI, VIII, IX, XI; pár VIII/IX = saltus lunae). Kotva: novoluní epakty 23 "
        "v březnu = 8. III (= velikonoční úplněk − 13). Generovaný plný kalendář se shoduje se "
        "skenem buňka po buňce (ověřeno I–IV i X–XII).",
    61: "✓ dekódováno a ověřeno proti skenu: každá buňka = „týden doplněk“. Týden = ⌊(datum "
        "gregoriánských Velikonoc od 1. III + 16)/7⌋, kde Velikonoce = první neděle po "
        "velikonočním úplňku (z epakty řádku) podle nedělního písmene sloupce; doplněk = (35 "
        "pro sloupec A, jinak 34) − týden. Generovaný plný cell-grid se shoduje se skenem buňka "
        "po buňce na ověřených řádcích (epakta *, 29, 28, 27, 26·XXV, 25·24 …) a distribučně "
        "s přepisem Text Titan I ter; epakty v pořadí 30(*)…1 (24 a XXV jsou alternativy 25/26). "
        "Dies Concurrentes 0–6 čteny ze skenu.",
}

# Delší metodické poznámky pod vybranými tabulkami (rozbalovací <details>).
# Nadpis rozbalovací poznámky (default je obecný).
_TABLE_NOTE_SUMMARY: dict[int, str] = {
    55: "Metodická poznámka: jak časy vznikly (výpočet vs. pozorování, refrakce, drift)",
    60: "Jak tabule funguje a jak je ověřena (dekódování)",
    61: "Jak tabule funguje a jak je ověřena (gregoriánské dvojče f60)",
    3: "Rozbor tabule: původ (Tadeáš Hájek z Hájku), datace, význam sloupců a ověření",
}

_TABLE_NOTE_LONG: dict[int, str] = {
    60: (
        "<p><b>Co tabule udává.</b> Pro každý <b>zlatý počet</b> (1–19, řádky) a <b>nedělní "
        "písmeno</b> (A–G, sloupce) je v buňce <b>dvojice čísel</b>. Tabule patří ke „klíčům“ "
        "pro pohyblivé svátky a její název zní <i>Tabula intervalli</i> — tabule intervalu "
        "(juliánských) Velikonoc.</p>"
        "<p><b>Dekódování a ověření.</b> Rozborem se ukázalo, že <b>první číslo dvojice je "
        "pořadí týdne, v němž leží juliánské Velikonoce</b>: rovná se "
        "<code>⌊(datum Velikonoc, počítáno od 1. března, + 16) / 7⌋</code>. Spočítali jsme "
        "juliánské datum Velikonoc nezávisle (z komputu) pro každou kombinaci zlatého počtu a "
        "nedělního písmene a první číslo <b>souhlasí ve všech 133 buňkách</b> (19 × 7). Druhé "
        "číslo je <b>doplněk</b> (34, resp. 35 minus první) — nese informaci o dni v týdnu "
        "(rozdíl 34/35 podle toho, zda Velikonoce padnou na začátek týdne). Tím je f60 "
        "<b>dekódována i ověřena</b> jako pravá velikonoční intervalová tabule (reprodukovatelné "
        "v <code>tools/verify_computus.py</code>).</p>"
    ),
    61: (
        "<p><b>Gregoriánské dvojče tabule f60.</b> Stejná stavba (v každé buňce dvojice čísel), "
        "ale indexováno <b>epaktou</b> (řádky) a <b>nedělním písmenem</b> (sloupce A–G; dole "
        "převod na „Dies concurrentes“ 0–6) a počítá pro <b>nový (gregoriánský) kalendář</b>. "
        "Platí týž klíč jako u f60: <b>první číslo dvojice = pořadí týdne (gregoriánských) "
        "Velikonoc</b>, druhé je doplněk.</p>"
        "<p><b>Ověření.</b> Spočetli jsme gregoriánské datum Velikonoc nezávisle pro každou "
        "kombinaci (epakta × nedělní písmeno) a první číslo souhlasí v <b>191 z 210 buněk</b>. "
        "Zbylé neshody jsou soustředěny do <b>oblasti epakty 25/XXV</b> — proslulé gregoriánské "
        "zvláštnosti (epakta 25 má dvojí podobu), která posouvá epaktovou osu o řádek; přesné "
        "přiřazení řádků v této zóně je třeba na originále překontrolovat. Princip i většina "
        "tabule jsou tím ale potvrzeny.</p>"
    ),
    3: (
        "<p><b>Co záhlaví říká</b> (jeho věrný přepis je nad tabulkou). „Orloj "
        "<b>celý i poloviční</b>“ jsou dvě počítání hodin, "
        "jež tabule podává vedle sebe a jež nesou i nadpisy číselných sloupců: <b>celý orloj</b> "
        "= české (orlojní) hodiny počítané od západu Slunce přes celých 24 h, <b>poloviční</b> = "
        "obecné hodiny. „<i>Polum L graduů</i>“ = výška pólu 50° (Praha). Klíčové pro dataci: "
        "„<b>před CXVI [116] lety vydaná</b> … Léta 1689“ → původní Hájkova tabule vyšla "
        "<b>1689 − 116 = roku 1573</b>, tj. za Hájkova života (zemřel 1600) a v jeho době "
        "vydávaných minucí; tento list je pozdější <b>opis z roku 1689</b>. (Letopočet je v "
        "záhlaví psán římsky <b>M·DC·LXXXIX</b>; koncové „<b>IX</b>“ = 9, ne „IV“ = 4 — dřívější "
        "čtení „1684“ i „LXVI/66“ byla mylná, ověřeno na skenu při maximálním zvětšení.)</p>"
        "<p><b>Předloha — Hájkova „Tabule dlúhosti dne a noci k spravování orloje“ (1574).</b> "
        "Záhlaví jmenuje nejen autora, ale i dílo: jde o opis tištěné tabule "
        "<b>Dr. Tadeáše Hájka z Hájku</b> (<i>Thaddaeus Hagecius ab Hayek</i>, ~1525–1600, "
        "dvorní matematik Rudolfa II.) <b>„Tabule dlúhosti dne a noci k spravování orloje“ "
        "(1574)</b>. Shoduje se titul (záhlaví f2/f3), účel — Hájek ji zhotovil <b>přímo pro "
        "pražský orloj</b> — výška pólu 50° i datace (záhlaví „od někdy [= nebožtíka]… před CXVI "
        "lety vydaná“ od opisu 1689 → 1573, katalogově 1574; týž tisk). Atribuce platí "
        "<b>doloženě pro tuto tabuli (fol. 3)</b>; nezávisle změřený otisk u <b>fol. 55</b> "
        "(orlojní sluneční tabule pražského, Hájkova typu — ne dovezené cizí efemeridy) se s ní "
        "shoduje, je však z <b>jiné, starší vrstvy (~1641)</b>, takže tam jde o slučitelnost, "
        "ne o tutéž doloženou atribuci. <b>Význam:</b> tato orlojní tabule byla užitkový "
        "jednolist, jaké se dochovávají zcela výjimečně, a dochovaný exemplář originálu 1574 "
        "zatím není doložen (k ověření v Knihopisu / NK ČR) — je-li ztracen, je <b>tento opis "
        "(1689) vzácným, ne-li jediným svědkem jejího obsahu</b>, navíc už gregoriánsky "
        "upraveným. (Týž Hájek přivedl do Prahy Tychona Brahe i Keplera, z nichž vzešly "
        "Rudolfínské tabulky 1627 — orlojní astronom této knihy je však nevyužil; viz pozn. u "
        "fol. 78. Souhrn: <code>docs/hajek-tabule-orloje-1574.md</code>.)</p>"
        "<p><b>„Nyní dle Nového kalendáře spravena.“</b> „Nový kalendář“ = gregoriánský (1582, "
        "v Čechách 1584), „starý“ = juliánský; „spravena“ = upravena, seřízena. Tabule přiřazuje "
        "ke každé <b>délce dne datum</b>, kdy jí Praha dosáhne — a totéž astronomické datum nese "
        "v obou kalendářích jiné číslo (reforma 1582 vypustila 10 dní a vrátila jarní rovnodennost "
        "zpět k 21. březnu). Hájkův originál (1573) byl ve starém kalendáři; tato úprava jen "
        "<b>posunula sloupec dat o ~10 dní na gregoriánské počítání</b> — astronomie (sled délek "
        "dne i poloha Slunce) zůstává táž, mění se jen kalendářní nálepka u řádku. Proto u nás "
        "rovnodennost padá na <b>21. března</b> (sv. Benedikta, den = noc = 12:00, východ 6:00), "
        "zimní slunovrat ~23. prosince a letní ~23. června, a proto naše ověření muselo počítat "
        "<b>v gregoriánském kalendáři</b> (a do minuty sedělo). Úprava „na nový kalendář“ je tedy "
        "nutně po r. 1584 — což ladí s opisem 1689.</p>"
        "<p><b>Co rok 1689 dokládá o orloji.</b> Sám zápis je pramenem k dějinám stroje: pořídit "
        "r. 1689 do orlojní knihy novou, na nový kalendář seřízenou <b>tabuli pro nastavování "
        "orloje</b> (české i obecné hodiny, východ / poledne / západ) má smysl jen tehdy, byl-li "
        "orloj <b>v činnosti a měl svého orlojníka</b>, jenž knihu vedl a stroj seřizoval — "
        "seřizovací tabulky se nedopisují k nefunkčnímu stroji. Pro <b>řídce doložené období mezi "
        "opravami 1659 a 1791</b> je to tak samostatný doklad <b>aktivního provozu a údržby orloje "
        "k roku 1689</b>.</p>"
        "<p><b>Datace.</b> Dvě vrstvy se nyní pěkně srovnají: <b>původní Hájkova tabule = 1573</b> "
        "(1689 − 116), tedy za jeho života a v době jím vydávaných minucí; <b>tento list = opis "
        "z roku 1689</b>. Tomu odpovídají i obraty v záhlaví: „<i>od někdy</i>“ (= nebožtík, lat. "
        "<i>quondam</i>) před jménem dává smysl z pohledu opisovače r. 1689 (Hájek dávno mrtev), "
        "„dle <i>nového</i> kalendáře spravena“ pak řadí úpravu po gregoriánské reformě (1584). "
        "List je <b>přední</b> (fyzicky před Táborského opisem 1587), ale fakticky <b>dopsán na "
        "volný přední list později</b> — běžný jev, který chronologii hlavního korpusu neruší. "
        "K ověření na originále zůstává čtení letopočtu a zda je ruka/inkoust fol. 3 odlišná od "
        "datovaných vrstev (Táborský 1587, komputus ~1641).</p>"
        "<p><b>Struktura — kompaktní perpetuální tabule po krocích délky dne, symetrická.</b> "
        "Tabule není řazená po všech 365 dnech, nýbrž po <b>krocích délky dne á 10 minut</b>: "
        "každý řádek udává jednu délku dne (7:50 v zimě, 8:00, 8:10 … až 16:10 v létě). Protože "
        "<b>táž délka dne nastává dvakrát do roka</b>, má tabule pro každý řádek <b>dvě data</b>: "
        "vlevo <b>jarní</b> (zima → léto, prosinec → červen) a vpravo <b>podzimní</b> (léto → "
        "zima, červen → prosinec), každé s měsícem, dnem a svátkem / vstupem Slunce do znamení. "
        "Tak v jednom listě drží celý rok. Číselné sloupce (v hodinách a minutách) jsou v "
        "rukopise nadepsány <i>Dlúhost dne</i>, <i>Slunce celého orloje</i> a <i>Slunce na díl "
        "orloje</i> (= východ Slunce v <b>českých /orlojních/ hodinách</b> počítaných od západu, "
        "a v <b>obecných hodinách</b>), <i>Poledne celého orloje</i> a <i>Západ celého orloje</i> "
        "— tato záhlaví přejímáme do tabulky doslovně. Rozestupy dat jsou nepravidelné (u "
        "slunovratu se den mění pomalu, ke konci rychleji).</p>"
        "<p><b>Ověření výpočtem.</b> Spojnice „délka dne → datum“ přesně sedí na geometrický "
        "model pro <b>Prahu (φ = 50°) v novém kalendáři</b>: délka dne 7:50 ↔ rukopis 23. XII "
        "(zimní slunovrat, výpočet 21. 12.); 8:00 ↔ 4. I (výp. 4. 1.); 8:10 ↔ 11. I (výp. "
        "10. 1.); 8:20 ↔ 16. I (výp. 14. 1.); 8:30 ↔ 19. I (výp. 19. 1.). Odchylky 1–2 dny "
        "odpovídají rozlišení 10minutového kroku. Den + noc = 24:00; o zimním slunovratu délka "
        "dne 7:50, noci 16:10, východ 8:05 — přesně vypočtené hodnoty pro Prahu. <b>Hájkova "
        "tabule je tím potvrzena jako geometrický výpočet pro Prahu</b> (shodně s otiskem u "
        "fol. 55). Jarní data se v 33 z 51 řádků liší od výpočtu o ±1–2 dny, takže <b>nešlo "
        "generovat ze vzorce, muselo se číst</b>; časové sloupce naopak souhlasí s přepočtem do "
        "minuty (rovnodennost: <i>Dlúhost dne</i> 12:00, <i>Slunce na díl orloje</i> /východ "
        "obecný/ 6:00, <i>Poledne celého orloje</i> 18:00).</p>"
        "<p><b>Přepis vs. ediční výklad.</b> V buňkách tabulky je <b>jen přepis</b> — jména "
        "svatých (mírně normalizovaný pravopis) a zápis „<i>Slunce na</i> [znamení]“, jak stojí "
        "v rukopise. Jména svatých jsou podle kalendářní konvence v <b>genitivu</b> — udávají, "
        "<b>koho/čeho</b> je to den čili svátek (slovo „den/svátek“ se vypouští): „Vojtěcha“ = "
        "/den sv./ Vojtěcha, „Anežky Panny“ = /den sv./ Anežky Panny. Vše ostatní je ediční výklad "
        "a patří sem, ne do tabulky: <b>[?]</b> = nejisté "
        "čtení, které se neshoduje s žádným svatým k danému dni; jména, jež kalendáři odpovídají, "
        "jsou bez otazníku (ověřeno: Anežka 21. 1., Valentin 14. 2., Benedikt 21. 3. = rovnodennost, "
        "Vojtěch 23. 4., Žikmund 2. 5., Václav 28. 9., Diviš 9. 10., Šimona a Judy 28. 10. ad.). "
        "Podzimní denní čísla z rukopisu kanonická data svátků nezávisle potvrzují.</p>"
        "<p><b>Znamení zvířetníku</b> (zápis „Slunce na …“) značí vstup Slunce do znamení, tj. "
        "obratníky a rovnodennosti: ♑ Kozoroh (zimní slunovrat, ~22. 12.), ♒ Vodnář, ♓ Ryby, "
        "♈ Beran (<b>jarní rovnodennost</b>, ~21. 3.), ♉ Býk, ♊ Blíženci, ♋ Rak (<b>letní "
        "slunovrat</b>, ~21. 6.); v podzimní polovině ♌ Lev, ♍ Panna, ♎ Váhy (<b>podzimní "
        "rovnodennost</b>, ~23. 9.), ♏ Štír, ♐ Střelec. <b>České (orlojní) hodiny</b> se počítají "
        "od západu Slunce (západ = 24); proto je u zimního slunovratu poledne v 20:05 a u letního "
        "v 15:55, kdežto v obecných hodinách je poledne stále ve 12:00.</p>"
    ),
    55: (
        "<p>Porovnali jsme tuto tabuli s nezávislým astronomickým výpočtem východu Slunce "
        "pro Prahu (zeměpisná šířka φ ≈ 50,09°). Náš výpočet pracuje s <b>pravým Sluncem</b> "
        "(zdánlivá poloha včetně rovnice středu, dle Meeuse) a tabule s ním souhlasí — viz "
        "níže; skript <code>tools/verify_computus.py</code> je v repozitáři reprodukovatelný a "
        "pracuje se všemi 365 dny tabule.</p>"
        "<p><b>0) Datace: polovina 17. století (kolem r. 1641).</b> Tato astronomicko-"
        "komputistická sekce knihy je mladší než Jablonského opis Táborského zprávy (1587) — "
        "stojí v knize dál a její <b>vlastní datum plyne z příkladů v doprovodné próze</b> "
        "(fol. 62–68), které počítají s rokem <b>1641</b> jako „přítomným“ a 1642 jako "
        "„následujícím“. Tabule i návody tedy vznikly kolem r. 1641; matematický a tabulkový "
        "aparát níže je proto třeba vztahovat k této době, ne k r. 1587.</p>"
        "<p><b>1) Jde o vypočtená, nikoli pozorovaná data.</b> Rozdíl mezi rukopisem a "
        "výpočtem má přes celý rok rozptyl (RMS) jen <b>~0,8 minuty</b> — tedy na úrovni "
        "zaokrouhlení na celé minuty. Pozorované časy východu by se nutně rozcházely o "
        "několik minut (kolísání refrakce s počasím a teplotou, mlhy nad obzorem, chyba "
        "odečtu). Tak těsná shoda po celý rok je dosažitelná jedině <b>výpočtem</b> "
        "z tabulek deklinace Slunce a sférické trigonometrie.</p>"
        "<p><b>2) Sezónní průběh přesně sedí na Prahu.</b> Reziduum (rukopis − výpočet) je "
        "<b>ploché</b> přes všech dvanáct měsíců — nemá žádné měsíční vlnění. To vylučuje "
        "chybu přepisu i chybnou zeměpisnou šířku: kdyby tabule platila pro jinou šířku "
        "nebo měla systematickou chybu čtení, reziduum by se sezónně vlnilo. Tvar křivky "
        "(od ~8:04 v prosinci po ~3:56 v červnu) odpovídá Praze.</p>"
        "<p><b>3) Dobová definice okamžiku východu — bez refrakce.</b> Při moderní definici "
        "východu (horní okraj kotouče na zdánlivém obzoru, tj. −50′ pod ním kvůli "
        "atmosférické refrakci 34′ a poloměru Slunce 16′) vychází rukopis soustavně o "
        "<b>~6–7 minut později</b>. Posuneme-li definici na okamžik, kdy <b>střed Slunce "
        "protne geometrický (matematický) obzor</b> — tedy výška 0° <b>bez refrakce</b> — "
        "reziduum klesne prakticky na nulu (průměr −0,5 min). Tabule tedy počítá "
        "geometrický východ středu Slunce a refrakci nezahrnuje. Refrakci sice už Tycho "
        "Brahe a Kepler v té době tabelovali, ale <b>perpetuální tabule a běžné kalendáře ji "
        "rutinně vynechávaly</b> a držely se geometrické definice — což odpovídá zde "
        "(a naznačuje to konvenční, případně starší předlohu).</p>"
        "<p><b>4) Rovnodennost u 21. března — nový kalendář, perpetuální tabule.</b> Tabule "
        "odpovídá rovnodennosti u <b>21. března</b>, tedy <b>novému (gregoriánskému) kalendáři</b> "
        "— který v Čechách platil od r. 1584 a byl navržen tak, aby rovnodennost u 21. března "
        "držel — nikoli skutečné juliánské poloze Slunce (ta by v polovině 17. stol. byla "
        "o ~10 dní jinde, kolem 11. března jul.). Současně je to typický rys <b>věčné "
        "(perpetuální) tabule</b>, nepřepočítané na konkrétní rok.</p>"
        "<p><b>5) Zbytkový rozptyl ~1–2 min není chyba.</b> Protože jde o výpočet, není "
        "důvod k náhodné chybě; zbylé jednotky minut jsou rozdíl <b>parametrů a "
        "zaokrouhlení</b> mezi dobovým a naším výpočtem: zaokrouhlení na celé minuty, dobová "
        "hodnota šikmosti ekliptiky (~23°30′ vs. dnešních 23°26′) a granularita dobových "
        "slunečních tabulek (deklinace po stupních délky Slunce). Změna šikmosti či drobná "
        "změna přijaté šířky reziduum dále nezlepší — parametry už v podstatě sedí.</p>"
        "<p><b>6) Použili pravé Slunce, ne střední.</b> Necháme-li model počítat s "
        "<b>rovnoměrným</b> (středním) pohybem Slunce, shoda se zhorší (RMS 0,8 → 1,4 min) a "
        "objeví se podzimní odchylka ~+3 min (Zář–Lis) — charakteristický podpis <b>rovnice "
        "středu</b> (nerovnoměrnosti zdánlivého pohybu Slunce, až ±1,9°). Tabule tuto "
        "nerovnoměrnost zahrnuje, tj. opírá se o pořádnou <b>tabulku deklinace po dnech roku</b> "
        "(odvozenou z pravé délky Slunce), ne o jednoduchý lineární přepočet data na deklinaci.</p>"
        "<p><b>Jakým matematickým aparátem se to dalo spočítat (k r. 1641).</b> Trigonometrie "
        "byla dávno hotová i pojmenovaná: sférická od antiky (Ptolemaios, tětivy) a islámské "
        "astronomie (sinová věta, ~1000), v Evropě ji soustavně podal <b>Regiomontanus, De "
        "triangulis omnimodis</b> (~1464, tisk 1533) a slovo „trigonometria“ zavedl "
        "B. Pitiscus už r. 1595. K roku 1641 navíc existovaly <b>logaritmy</b> (Napier 1614, "
        "Briggs 1624) i prosthaferéze (Wittich, Brahe, v Praze Jost Bürgi kolem r. 1600), takže "
        "násobení v níže uvedeném vzorci bylo snadné. Klíčový vzorec je <b>ascensionální "
        "diference</b> (differentia ascensionalis) z pravoúhlého sférického trojúhelníku: "
        "<code>sin(AD) = tg φ · tg δ</code>, neboli <code>cos H = −tg φ · tg δ</code> "
        "(H = polovina denního oblouku při středu Slunce na obzoru). Délka půldne = 90° + AD, "
        "východ = 6<sup>h</sup> − AD/15 (v rovných hodinách). Deklinace δ z délky Slunce: "
        "<code>sin δ = sin ε · sin λ</code>; délku λ pro daný den dávaly hotové tabulky — "
        "<b>Alfonsinské</b> (13. stol.), <b>Pruténské</b> (Reinhold 1551) i nejnovější "
        "<b>Rudolfinské</b> (Kepler 1627) — a samozřejmě efemeridy.</p>"
        "<p><b>Nebylo nutné, aby to orlojník sám počítal — spíš to opsal z hotové tabulky.</b> "
        "Tabule východu/západu a délky dne pro danou šířku byly v 17. století <b>běžný "
        "tištěný obsah</b>: kalendáře a „minuce“ (praktiky), efemeridy a knihy o sféře pro "
        "konkrétní města a šířky. Sám rukopis je ostatně <b>česky psaná praktická příručka</b> "
        "(návody na nedělní písmeno, zlatý počet, epaktu, novoluní, komputus na prstech — "
        "fol. 62–68), tj. kompilace z latinských předloh, ne originální astronomické dílo. "
        "Nejpravděpodobnější scénář proto je, že orlojník (či písař knihy) <b>převzal hotovou "
        "tabulku pro pražskou šířku</b> z tištěného kalendáře / efemeridy a opsal ji; vlastní "
        "výpočet (sférická trigonometrie, pravé Slunce) provedl <b>jednou autor předlohy</b> "
        "— astronom či kalendářník — nikoli nutně místní matematik. Odečet z přístroje to "
        "není: astroláb (a orloj sám je v jádru astroláb) má přesnost ~stupně (~4 min) a "
        "rozptyloval by se, kdežto naše shoda má RMS 0,8 min. „Nomogram“ v moderním smyslu "
        "(zákrytové grafy) je anachronismus (konec 19. stol.); dobovou grafickou obdobou byl "
        "<b>analema</b> (ortografická projekce), ta ale dává nižší přesnost. Postup, kterým "
        "předloha vznikla (per den): (1) datum → délka Slunce λ (Alfonsinské/Pruténské/"
        "Rudolfinské tabulky), (2) λ → deklinace δ, (3) AD ze <code>sin(AD) = tg φ · tg δ</code> "
        "(φ Prahy pevné), (4) východ = 6<sup>h</sup> − AD/15, zaokrouhleno na minutu; obdobně "
        "poledne a západ.</p>"
        "<p><b>Z jaké předlohy mohla být opsána.</b> Tabule patří do dobře doloženého žánru "
        "perpetuálních denních tabulek „<i>Tabula quotidiana per Annum Ortus et Occasus Solis, "
        "Longitudinis item Diei et Noctis, pro elevatione Poli N graduum</i>“ — východ a západ "
        "Slunce a délka dne i noci pro každý den v roce, v hodinách a minutách, počítané zvlášť "
        "pro každou výšku pólu (zeměpisnou šířku). Vycházel v mnoha regionálních variantách: pro "
        "42° (<b>Theodosius Rubeus, Tabulae XII</b> — časy dokonce v „italských“ i „obecných“ "
        "hodinách, tj. přesně to dvojí počítání, jaké potřebuje orloj), pro 49° (exemplář "
        "v moravských historických fondech; <b>Joseph de Tertiis</b>, Paříž 1690, pro 49° "
        "„<i>quae deservire possit G. 48 &amp; 50</i>“ — výslovně použitelná i pro 50°). "
        "Moravský exemplář je výslovně „<i>pro elevatione Poli 49 graduum in Marchionatu "
        "Moraviae</i>“, tedy <b>regionální edice</b>; datem nejblíž stojí <b>Jakob Rosius, "
        "Ephemeris Perpetua</b> (1646, perpetuální kalendář s pravým východem/západem Slunce pro "
        "47°). Pozn.: rozlišují se dva podžánry — naše f55 je řazená po <b>kalendářních dnech</b> "
        "(styl kalendáře/almanachu), kdežto Rosius a Argoli po <b>stupních zvěrokruhu</b> (styl "
        "učebnic sféry). Orlojník ji <b>pravděpodobně opsal</b> z verze pro <b>výšku pólu ~50°</b> "
        "(Praha). (Slavná tabulka "
        "„ortus et "
        "occasus“ v Argoliho efemeridách 1641 je naproti tomu pro <b>hlavní hvězdy</b>, ne "
        "Slunce, a stojí na Tychonových hypotézách — náš zdroj to tedy není.) Náš otisk předlohu "
        "dále zužuje: je <b>bez refrakce</b> — součet východů o obou slunovratech je u rukopisu "
        "přesně 12:00 (3:55 + 8:05 = 720 min), kdežto tabulka s refrakcí (−50′) by dala ~707 min "
        "(3:48 + 7:58). Předloha tedy patří ke <b>geometrické tradici</b>. Konkrétní tištěný "
        "exemplář pro pražskou šířku 50° by se dal hledat v knihovnách (Knihopis, MZK/NKP). "
        "<b>Důležitá stopa</b>: <b>jiná</b> tabule v knize — fol. 3 (délka dne, ovšem opis "
        "z pozdější vrstvy ~1689) — má v záhlaví <b>výslovnou atribuci „od někdy D. Tadeáše "
        "Hájka z Hájku … k vyvýšení Polum L [= 50] graduů … dle nového kalendáře spravena“</b>. "
        "Náš nezávisle změřený otisk f55 (geometrická, výška pólu ~50°, nový kalendář) je "
        "s <b>Hájkovou pražskou tradicí slučitelný</b>, takže tato tabule (východ pro poloviční "
        "orloj) <b>nejspíš pochází z téže tradice</b> — pozor však, f55 je z vrstvy ~1641, "
        "kdežto výslovná atribuce stojí jen u f3; pro f55 jde o důvodný předpoklad, ne o "
        "doloženou shodu.</p>"
        "<p><b>Závěr.</b> Tabule východu (a obdobně poledne a západu) Slunce je <b>produktem "
        "výpočtu, ne měření</b>, a do orlojní knihy <b>byla pravděpodobně opsána z hotové "
        "tištěné tabulky</b> pro pražskou šířku (sekce je datovatelná kolem r. 1641). Vychází ze "
        "sférické trigonometrie (ascensionální diference <code>cos H = −tg φ · tg δ</code>) a "
        "tabulek deklinace <i>pravého</i> Slunce: počítá geometrický východ středu Slunce bez "
        "refrakce, pro výšku pólu ~50° (Praha), v kalendáři s rovnodenností u 21. března "
        "(nový/gregoriánský styl). Náš přepis se s tímto modelem (pravé Slunce) shoduje na "
        "úrovni zaokrouhlení "
        "(RMS 0,8 min), takže je věrný a bez systematické chyby.</p>"
    ),
}


def _split_marginalia(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split clean lines into (main text, marginalia block).

    The marginalia block begins at the first line carrying the ``... na okraji:]`` marker
    and runs to the end (incl. any following later-hand / editorial-note lines). Earlier
    later-hand BODY additions (``[přípis pozdější rukau:] …``) stay in the main text.
    """
    for i, ln in enumerate(lines):
        if "okraji:]" in ln:
            return lines[:i], lines[i:]
    return lines, []


def _marginalia_html(marg_lines: list[str], page_nr: int) -> str:
    """Render the scribal marginalia (brown box) and, if a modern editorial note is
    embedded in the same block (``… — [Ediční pozn.: …]``), lift it into a separate
    colour-distinct (green) box so the two are never mixed. Later-hand keepers' notes
    (``[Pozdější rukou …]``) keep their markers and get the ``later`` accent.
    """
    if not marg_lines:
        return ""
    text = " ".join(ln.strip() for ln in marg_lines).strip()
    if "okraji:]" in text:
        text = text.split("okraji:]", 1)[1].strip()
    # Split off any embedded editorial note → own green box, scribal text stays brown.
    ed_text = ""
    parts = re.split(r"\[[Ee]diční pozn[.:\s]*", text, maxsplit=1)
    if len(parts) > 1:
        text = re.sub(r"\s*[—–-]\s*$", "", parts[0]).strip()
        ed_text = parts[1].rstrip().rstrip("]").strip()
    later = "Pozdější ruk" in text or "pozdější ruk" in text
    cls = "m-note m-orig later" if later else "m-note m-orig"
    out = ""
    if text:
        out += (
            f'<div class="{cls}"><span class="mlabel">Přípisky na okraji</span>'
            f"<p>{_esc(text)}</p></div>"
        )
    if ed_text:
        out += (
            '<div class="m-note m-ed"><span class="mlabel">Ediční poznámka na okraji</span>'
            f"<p>{_apparatus(_esc(ed_text))}</p></div>"
        )
    return out


# Editorial side-notes placed in the same outer margin as the scribal marginalia,
# but colour-distinguished (green) so the reader never mistakes a modern editorial
# remark for an original gloss. Short notes only; long method notes stay in the
# collapsible block under the text. Keyed by folio; ready to be populated.
_MARG_ED: dict[int, list[str]] = {
    22: [
        "Glosy na tomto okraji jsou tematický rejstřík (rukou písaře M. Carchesia, "
        "1587) — orientační záhlaví odstavců, ne nový obsah."
    ],
}


def _marg_ed_html(page_nr: int) -> str:
    notes = _MARG_ED.get(page_nr)
    if not notes:
        return ""
    items = "".join(f"<p>{_apparatus(_esc(t))}</p>" for t in notes)
    return (
        '<div class="m-note m-ed"><span class="mlabel">Ediční poznámka na okraji</span>'
        f"{items}</div>"
    )


# --- Rozbor marginálií (samostatná stránka marginalia.html) -------------------------
_MARG_LAT = ("index", "declinat", "linea", "tabula", "solstit", "solis", "horar",
             "oppositi", "coniuncti", "circul")
_MARG_HIST = ("zvůnek", "táborsk", "tobiáš", "tobiass", "špaček", "obnoven", "zprávce",
              "přistaup", "přistoup", "umřel", "škody", "zase přist")


def _marg_notes(marg_lines: list[str]) -> list[str]:
    """Split the clean marginalia block into individual glosses."""
    text = " ".join(ln.strip() for ln in marg_lines).strip()
    text = re.sub(r"^\[[^\]]*?okraji:\]\s*", "", text)
    text = re.sub(r"\s*\[[^\]]*?:\].*$", "", text)  # drop trailing editorial note if any
    parts = re.split(r"\s—\s|;\s", text.rstrip(" ]."))
    return [p.strip(" .—") for p in parts if p.strip(" .—")]


def _later_additions(clean_lines: list[str]) -> list[str]:
    """Extract later-hand insertions (``[přípis pozdější rukau:] …`` / ``[Pozdější rukou …:]``).

    These are substantial annotations by a later hand (a different layer than the
    1587 copyist's index glosses); kept apart so the marginalia page can show them
    as their own category. Editorial notes appended in [ … ] are cut off.
    """
    adds: list[str] = []
    i, n = 0, len(clean_lines)
    marker = re.compile(r"\[(?:přípis\s+)?pozdější\s+ruk[ao]u?[^\]]*\]\s*(.*)", re.I)
    stop = re.compile(r"\[(?:přípis|pozdější|ediční)", re.I)
    while i < n:
        m = marker.match(clean_lines[i].lstrip())
        if not m:
            i += 1
            continue
        buf = [m.group(1)]
        j = i + 1
        while j < n and clean_lines[j].strip() and not stop.match(clean_lines[j].lstrip()):
            buf.append(clean_lines[j])
            j += 1
        text = " ".join(b.strip() for b in buf).strip()
        text = re.split(r"\s*—?\s*\[[Ee]diční pozn", text)[0].strip(" .—")
        if text:
            adds.append(text)
        i = j
    return adds


def _marg_category(note: str) -> tuple[str, str]:
    """Classify a gloss → (tag, popis)."""
    low = note.lower()
    if low.startswith("nb"):
        return ("NB", "pozdější čtenář (?)")
    if any(k in low for k in _MARG_HIST):
        return ("HIST", "dějiny orloje / orlojníci")
    if any(k in low for k in _MARG_LAT):
        return ("LAT", "latinský odborný termín")
    return ("IDX", "český tematický rejstřík")


def _marg_crops(work_dir: Path, out_dir: Path, page_nr: int) -> list[str]:
    """Crop the folio's marginal glosses from the scan; return relative img paths.

    Reproductions of AHMP scans (small study crops). Uses the marginalia region
    bbox from PAGE XML (else an outer-margin strip), then splits it into ink bands
    = single glosses. One column crop if band detection fails.
    """
    if Image is None:
        return []
    scan = work_dir / "scans" / f"{page_nr:04d}.jpg"
    if not scan.exists():
        return []
    im = Image.open(scan).convert("RGB")
    w, h = im.size
    xmlp = work_dir / "page_xml" / f"{page_nr:04d}.xml"
    bbs = marginalia_bboxes(xmlp.read_text(encoding="utf-8")) if xmlp.exists() else []
    if bbs:
        x0 = max(0, min(b[0][0] for b in bbs) - 12)
        x1 = min(w, max(b[0][2] for b in bbs) + 12)
        y0 = max(0, min(b[0][1] for b in bbs) - 10)
        y1 = min(h, max(b[0][3] for b in bbs) + 10)
    elif page_nr % 2 == 0:  # verso → left margin (inset past binding; before main text)
        x0, x1, y0, y1 = 55, 300, 320, min(h, 3450)
    else:  # recto → right margin (after main text; inset from edge)
        x0, x1, y0, y1 = w - 300, w - 55, 320, min(h, 3450)
    col = im.crop((x0, y0, x1, y1))
    g = col.convert("L")
    cw, ch = g.size
    px = g.load()
    min_dark = max(3, cw // 70)
    rows = [sum(1 for x in range(0, cw, 2) if px[x, y] < 150) >= min_dark for y in range(ch)]
    bands: list[tuple[int, int]] = []
    y, gap = 0, 12
    while y < ch:
        if rows[y]:
            s = y
            while y < ch and (rows[y] or (y + gap < ch and any(rows[y:y + gap]))):
                y += 1
            if 16 <= y - s <= 300:  # a real gloss; drop tiny noise and giant merged bands
                bands.append((s, y))
        else:
            y += 1
    # Drop bands in the top margin: that is the later pencil foliation (leaf number),
    # not a marginal gloss. Marginal notes align with the text block (starts ~y 420).
    bands = [(a, b) for (a, b) in bands if y0 + a >= 410]
    d = out_dir / "img" / "marg"
    d.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    if not bands or len(bands) > 14:  # detection unreliable → no crop (transcription only)
        return []
    for i, (a, b) in enumerate(bands):
        sub = col.crop((0, max(0, a - 6), cw, min(ch, b + 6)))
        if sub.width > 430:
            sub = sub.resize((430, round(sub.height * 430 / sub.width)))
        sub.save(d / f"m{page_nr:04d}_{i}.jpg", quality=85)
        paths.append(f"img/marg/m{page_nr:04d}_{i}.jpg")
    return paths


_MARG_TAGNAMES = {"IDX": "rejstřík", "LAT": "lat. termín", "HIST": "dějiny orloje",
                  "NB": "NB / čtenář"}


def _marginalia_doc(title: str, items: list[dict]) -> str:
    """Standalone analysis page for the marginalia (crops + per-gloss classification)."""
    cnt: dict[str, int] = {}
    for it in items:
        for _t, tag, _d in it["notes"]:
            cnt[tag] = cnt.get(tag, 0) + 1
    summary = " · ".join(
        f"{_MARG_TAGNAMES[k]}: {cnt[k]}" for k in ("IDX", "LAT", "HIST", "NB") if cnt.get(k)
    )
    n_add = sum(len(it.get("adds", [])) for it in items)
    if n_add:
        summary += f" · pozdější přípisky (jiná ruka): {n_add}"
    secs = []
    for it in items:
        figs = "".join(
            f'<img src="{_esc(p)}" alt="marginálie fol. {it["page"]}" loading="lazy">'
            for p in it["imgs"]
        )
        if not figs and it["notes"]:
            figs = "<i>[výřez nedostupný — viz sken v AHMP]</i>"
        notes = "".join(
            f'<li><span class="mtag t-{tag}">{_MARG_TAGNAMES[tag]}</span> {_esc(txt)}</li>'
            for (txt, tag, _desc) in it["notes"]
        )
        body = f'<ol class="marg-notes">{notes}</ol>' if notes else ""
        body += "".join(
            '<p class="marg-add"><span class="mtag t-ADD">pozdější přípisek '
            f'(jiná ruka)</span> {_esc(a)}</p>'
            for a in it.get("adds", [])
        )
        label = f' — <span class="mctx">{_esc(it["label"])}</span>' if it.get("label") else ""
        secs.append(
            f'<section class="marg-item"><h3 id="f{it["page"]:04d}">fol. {it["page"]}{label} '
            f'· <a href="p{it["page"]:04d}.html">přepis folia →</a></h3>'
            f'<div class="marg-row"><div class="marg-figs">{figs}</div>'
            f'<div class="marg-body">{body}</div></div></section>'
        )
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rozbor marginálií — {_esc(title)}</title>
<link rel="stylesheet" href="assets/edition.css"></head>
<body class="mode-dipl">
<header><a class="home" href="index.html">≡</a><h1>Rozbor marginálií</h1></header>
<main>
<section class="tiraz">
<p>Na okrajích folií <b>13–46</b> (Táborského Zpráva) je {sum(len(it['notes']) for it in items)}
okrajových přípisků na {len(items)} foliích. Klasifikace: {summary}. Těžiště rozboru jsou
<b>jejich přepisy a interpretace</b> (výřezy ze skenu jsou jen ilustrativní).</p>
<p><b>1) Rejstříkové glosy — bez nové informace.</b> Drobné okrajové glosy jsou
<b>rejstříkový aparát</b>: krátká hesla, která <b>pojmenovávají, co už říká přilehlý text</b> —
témata výkladu (české značky „O pušce“, „Srovnání obojí počtuov“), latinské odborné termíny
(<i>Index Solis, declinatio solis, Linea oppositionis/coniunctionis, Solstitium, Tabula Horarum
Planetarum</i>) a u závěru dějiny orloje a jeho správců. <b>Žádná z nich nepřidává údaj, který by
nebyl v hlavním textu</b>: i „historický“ shluk u fol. 38–46 — planetní hodiny, „nebožtík“ Tobiáš
a jeho škody, učedník Jakub Špaček, obnovení orloje — <b>doslovně odpovídá tělu textu</b> (ověřeno
proti přepisu týchž folií). Jejich přínos je <b>navigační, interpretační a terminologický</b>,
nikoli faktografický.</p>
<p><b>2) Pozdější přípisky jinou rukou — tady je nová informace.</b> Kromě rejstříku jsou v knize
<b>obsažnější vsuvky pozdější rukou</b> (jiná, mladší ruka než opisovač A), které <b>skutečně něco
přidávají</b>:
<br>• <b>fol. 22 — přestavba měsíční koule:</b> „<i>Nyní jest to jinače spraveno a lehčeji, neboť
žádných koleček není, které by měsícem hýbali… nežli vnitř v tlustosti měsíce jest příprava dosti
sprostá, však předce dosti trefně vymyšlená, tak že samým otočováním se měsíce po sféře v 24
hodinách corpus lunae o 1 grad se pohne, a v 30 dnech celý se obrátí…</i>“ — pisatel zde
dokládá, že <b>původní soukolíový pohon měsíce (popsaný Táborským) byl nahrazen jednodušším
mechanismem uvnitř tělesa měsíce</b>. To je <b>doklad reálné konstrukční změny orloje</b>, jaký
Táborského text nemá. <b>Písmo se s dobrou pravděpodobností shoduje s rukou Astrolabia parvum
(fol. 70–79) a komputistické prózy (fol. 62–68)</b> — tedy <b>orlojníka-astronoma činného
~1641–1642</b> (týž pravý sklon, hnědý inkoust a mísení latiny: <i>corpus lunae</i>, <i>gradus</i>,
<i>sphera</i>). Slovem „<i>nyní</i>“ tak <b>datuje přestavbu měsíce k ~1641–1642</b> (proběhla tedy
mezi Táborského popisem /~1570, opis 1587/ a touto pozdější astronomickou vrstvou). Dataci vrstvy
nezávisle ukotvuje výpočet příkladu z 1. XI 1642 v Astrolabiu (skript
<code>tools/verify_astrolabe_1642.py</code>). <b>Tím revidujeme dřívější přiřazení Mikuláši
Petrovi /~1628/</b>; doporučena expertní verifikace na originále.
<br>• <b>fol. 38 — autorství a List purkmistra:</b> „<i>… léta 1410 … ten orloj … dělal … vide
list purkm[istra] … origl., sub figura 4</i>“ — proti Táborského dataci „mistr Hanuš okolo 1490“
tu pisatel <b>odkazuje na List purkmistra</b> (Littera Maior), totiž na <b>opis z r. 1628 původní
listiny z r. 1410</b>, jíž pražská rada smluvila zhotovení orloje s <b>mistrem Mikulášem z Kadaně</b>
(v téže knize, fol. 51–54; originál listiny v knize není). Tím <b>klade zhotovení orloje k r. 1410
/ Mikulášovi z Kadaně</b>, ne Hanušovi. Písmo je mladší plynulá kurzíva 17. stol. (ne ruka opisovače A z 1587) a odkaz „<i>sub
figura 4</i>“ předpokládá, že List purkmistra už byl v knize a očíslován — přípisek je tedy
<b>pozdější (po r. 1628</b>, kdy List purkmistra do knihy vepsal a očísloval Mikuláš Petr;
podpis na fol. 52: „<i>… 15. 9bri [Novembris] 1628. Mikuláš Petr</i>“). Jde o <b>jinou ruku než
vsuvka o měsíční kouli na fol. 22</b> (ta je ruka C) — writer-ID ani vizuální paleografie obě
vsuvky neztotožnily. Klademe ji proto k <b>pozdějším rukám ≥1628</b>, přičemž <b>B vs C zůstává
nerozhodnuto</b>; obsahově mírně svědčí pro <b>B (Mikuláš Petr</b>, který List purkmistra do knihy
vepsal a křížově naň odkazuje). Rozhodne expertní autopsie. <b>Historický obsah</b> — zhotovení
orloje r. 1410 mistrem Mikulášem z Kadaně — <b>tím dotčen není</b>.</p>
<p><b>Rejstříkové glosy (vč. „historických“): jedna ruka, totožná s opisovačem.</b> Na rozdíl
od obou pozdějších vsuvek výše jsou <b>rejstříkové</b> glosy fol. 13–46 (i ty s historickým obsahem
jako „Tobiáš umřel“) <b>jednou rukou</b> — touž českou novogotickou kurzívou, týmž duktem a inkoustem jako hlavní text
(srovnání „Tobiáš umřel“ / „Jakub Špaček“ / „Index Slunce“ navzájem i s tělem textu). Přisuzujeme
je proto <b>ruce A — Matouši Carchesiovi Jablonskému, opisovači z r. 1587</b>; jde o
<b>autorský/písařský rejstřík</b>, ne o cizí čtenářskou ruku. Odstín inkoustu vychází měřením
proti tělu textu <b>nepatrně světlejší a méně teplý</b> (Δ jasu +13–15, Δ „tepla“ R−B −18 až −34
z 256), což je však <b>zčásti artefakt tenčího tahu</b> — týž železo-duběnkový hnědý inkoust,
psaný jemnějším perem.</p>
<p><b>Ztotožnění s jinými písaři a datace.</b> Marginálie se <b>neshodují s žádnou z pozdějších
rukou</b> knihy — německého Listu purkmistra (1628), komputistické sekce (~1641) ani přední
Hájkovy tabule a přípisku (~1689); ty jsou jiným písmem a fyzicky v jiných částech. Protože
marginálie indexují tělo textu a jsou rukou A, vznikly <b>současně s opisem, tj. r. 1587</b>
(nebo těsně po něm) — tím je lze datovat, na rozdíl od pozdějších přípisků jinde v knize.
Výjimkou mohou být ojedinělé „NB“, jež bývají rukou pozdějšího čtenáře. (Paleografie i
kolorimetrie ze skenu = pracovní hypotéza, ne znalecký posudek; jistota střední.)</p>
<p class="warn"><b>Výřezy</b> jsou drobné studijní reprodukce ze skenů <b>Archivu hlavního města
Prahy</b> (Sbírka rukopisů, inv. č. 7916), uvedené pro ilustraci; souhlas archivu s reprodukcí
v jednání. Závazný je <b>přepis</b>, ne obrázek.</p>
</section>
{"".join(secs)}
</main>
<footer>Rozbor marginálií — pracovní hypotéza ze skenů AHMP. Edice © David Knespl, CC BY 4.0.</footer>
</body></html>"""


# Editorská překreslení nákresů (vlastní rekonstrukce, NE reprodukce skenu).
_F80_TRIANGLE_SVG = (
    '<svg viewBox="0 0 230 330" xmlns="http://www.w3.org/2000/svg" width="220" role="img" aria-label="Pravoúhlý trojúhelník 3-4-5 (3 na 4 = 5)"><g stroke="#2a2a2a" stroke-width="1.1"><polygon points="40,290 190,290 190,90" fill="none" stroke="#2a2a2a" stroke-width="1.6"/><path d="M 178,290 v -12 h 12" fill="none" stroke="#2a2a2a" stroke-width="1.2"/><line x1="90.0" y1="284.0" x2="90.0" y2="296.0"/><line x1="140.0" y1="284.0" x2="140.0" y2="296.0"/><line x1="190.0" y1="284.0" x2="190.0" y2="296.0"/><line x1="196.0" y1="240.0" x2="184.0" y2="240.0"/><line x1="196.0" y1="190.0" x2="184.0" y2="190.0"/><line x1="196.0" y1="140.0" x2="184.0" y2="140.0"/><line x1="196.0" y1="90.0" x2="184.0" y2="90.0"/><line x1="65.2" y1="246.4" x2="74.8" y2="253.6"/><line x1="95.2" y1="206.4" x2="104.8" y2="213.6"/><line x1="125.2" y1="166.4" x2="134.8" y2="173.6"/><line x1="155.2" y1="126.4" x2="164.8" y2="133.6"/></g><g font-family="Georgia,serif" font-size="14" fill="#2a2a2a" font-style="italic"><text x="65" y="310" text-anchor="middle">1</text><text x="115" y="310" text-anchor="middle">2</text><text x="165" y="310" text-anchor="middle">3</text><text x="201" y="269">1</text><text x="201" y="219">2</text><text x="201" y="169">3</text><text x="201" y="119">4</text><text x="42" y="267" text-anchor="middle">1</text><text x="72" y="227" text-anchor="middle">2</text><text x="102" y="187" text-anchor="middle">3</text><text x="132" y="147" text-anchor="middle">4</text><text x="162" y="107" text-anchor="middle">5</text></g></svg>'
)
_FIGURE_SVG: dict[int, str] = {
    80: (
        '<figure class="fig-svg">' + _F80_TRIANGLE_SVG
        + "<figcaption>Pravoúhlý trojúhelník 3 : 4 : 5 z fol. 80 — překreslení nákresu "
        "(editorská rekonstrukce, ne reprodukce skenu). Odvěsny 3 a 4, přepona 5 "
        "(3² + 4² = 5², tj. 9 + 16 = 25) — ilustrace Pythagorovy věty.</figcaption></figure>"
    ),
}


def _page_doc(
    *, title: str, page_nr: int, total: int, regions: list[TextRegion],
    ahmp_url: str | None, teige_passage: str | None, section_label: str = "",
    tables: list[Table] | None = None, figures: list[str] | None = None,
    clean_lines: list[str] | None = None, embed_scan: bool = False,
    table_page: bool = False, binding_note: str = "",
) -> str:
    tables = tables or []
    figures = figures or []
    has_text = any(r.lines and any(line.strip() for line in r.lines) for r in regions)
    has_content = has_text or bool(tables) or bool(figures) or bool(clean_lines) or table_page
    # AHMP rules: any internet publication of a reproduction needs an agreement +
    # <=500px + watermark. Until that is in place, NOTHING is republished — figures are
    # only referenced with an out-link to the AHMP viewer.
    fig_link = (
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">sken v AHMP (fol. {page_nr})</a>'
        if ahmp_url else f"sken v AHMP (fol. {page_nr})"
    )
    fig_note = (
        f'<figure class="fig fig-ref"><figcaption>Na tomto foliu je vyobrazení '
        f"(zde nereprodukováno — viz {fig_link}).</figcaption></figure>"
        if figures else ""
    )
    prev_link = f"p{page_nr-1:04d}.html" if page_nr > 1 else ""
    next_link = f"p{page_nr+1:04d}.html" if page_nr < total else ""
    ahmp = (
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">↗ sken v AHMP (fol. {page_nr})</a>'
        if ahmp_url else ""
    )
    # Optional embedded AHMP viewer (iframe = linking, not republication). Collapsed by
    # default; the scan is served & watermarked by AHMP. Toggle via --embed-scan.
    scan_embed = (
        '<details class="scan-embed"><summary>▣ Zobrazit sken folia z AHMP</summary>'
        f'<iframe src="{_esc(ahmp_url)}" loading="lazy" '
        f'title="Sken fol. {page_nr:04d} — Archiv hl. m. Prahy" '
        'referrerpolicy="no-referrer-when-downgrade"></iframe>'
        '<p class="scan-note">Sken hostuje a vodoznakem značí Archiv hlavního města Prahy. '
        'Nenačte-li se náhled (blokované cookies třetích stran), použij odkaz '
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">↗ otevřít v AHMP</a>.</p>'
        "</details>"
        if (embed_scan and ahmp_url) else ""
    )

    marginalia = ""
    region_margin = ""
    if has_content:
        # Precedence: corrected clean text > Docling table grid > raw per-line HTR.
        if clean_lines:
            main_lines, marg_lines = _split_marginalia(clean_lines)
            do_norm = page_nr not in _NO_NORMALIZE
            body_regions = _clean_block(main_lines, page_nr, do_norm)
            marginalia = _marginalia_html(marg_lines, page_nr)
        elif tables:
            cap = _TABLE_CAPTIONS.get(page_nr)
            note = _TABLE_VERIFY.get(
                page_nr, "přepis z rukopisu; číselné hodnoty ke kontrole proti skenu."
            )
            vcls = "table-note verified" if note.startswith("✓") else "table-note"
            heading_tx = _TABLE_HEADING_TX.get(page_nr)
            cap_html = f'<p class="table-cap">{_esc(cap)}</p>' if cap else ""
            # Above the table: the transcribed manuscript heading if we have one (original
            # text), otherwise the editorial caption. The ✓/verification note and any
            # method commentary always go BELOW, into the collapsible note.
            if heading_tx:
                head = heading_tx
                cap_in_note = cap_html  # editorial caption belongs to the note here
            else:
                head = cap_html
                cap_in_note = ""
            verify_html = f'<p class="{vcls}">{_esc(note)}</p>' if cap else ""
            body_regions = head + "".join(_table_html(t) for t in tables)
            body_regions += _TABLE_PROSE.get(page_nr, "")
            long_note = _TABLE_NOTE_LONG.get(page_nr)
            note_body = cap_in_note + verify_html + (long_note or "")
            if note_body.strip():
                summ = _TABLE_NOTE_SUMMARY.get(page_nr, "Metodická poznámka — rozbor a ověření")
                body_regions += (
                    f'<details class="method-note"><summary>{_esc(summ)}</summary>'
                    f"{note_body}</details>"
                )
        elif table_page:
            link = (
                f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">sken v AHMP (fol. {page_nr})</a>'
                if ahmp_url else f"sken v AHMP (fol. {page_nr})"
            )
            cap = _TABLE_CAPTIONS.get(page_nr, "Komputistická / astronomická tabulka")
            body_regions = (
                f'<div class="table-todo"><b>{_esc(cap)}</b><br>Číselná data tabulky zatím '
                f"nepřepsána (strojové rozpoznání ručně psaných tabulek selhává). Viz {link}.</div>"
            )
            long_note = _TABLE_NOTE_LONG.get(page_nr)
            if long_note:
                body_regions += (
                    '<details class="method-note" open><summary>Záhlaví tabule a původ '
                    "(Tadeáš Hájek z Hájku)</summary>"
                    f"{long_note}</details>"
                )
        else:
            # Per-line HTR path (no corrected clean text). Split marginal regions out
            # of the text flow so they can sit in a dedicated outer margin column,
            # mirroring the manuscript leaf — same two-zone layout as the clean path.
            def _real_lines(r: TextRegion) -> list[str]:
                return [line.strip() for line in r.lines if line.strip()]

            def _is_noise(r: TextRegion) -> bool:
                # A narrow outer-margin strip on which the HTR hallucinated the SAME
                # token on every line (e.g. "Já"×10, "prut,"×13) is layout noise on a
                # blank/ruled edge — not a scribal gloss. Suppress it entirely.
                rl = _real_lines(r)
                return len(rl) >= 2 and len(set(rl)) == 1

            marg_regs: list[TextRegion] = []
            body_regs: list[TextRegion] = []
            for r in regions:
                if r.rtype in _MARGINALIA and _real_lines(r):
                    if _is_noise(r):
                        continue  # drop degenerate margin-strip HTR repetition
                    marg_regs.append(r)
                else:
                    body_regs.append(r)
            body_regions = "\n".join(_region_html(r) for r in body_regs)
            region_margin = "\n".join(_region_html(r) for r in marg_regs)
        body_regions += _FIGURE_SVG.get(page_nr, "")
        page_folded = {
            fold(w) for r in regions for line in r.lines for w in line.split() if len(fold(w)) >= 4
        }
        teige = _teige_html(teige_passage, page_folded)
        if clean_lines:
            # True two-zone leaf: text column + a dedicated outer margin (recto→right,
            # verso→left) holding the scribal marginalia and (colour-distinct) editorial
            # side-notes — mirroring the manuscript page, not floated inside the text.
            vcls = "verso" if page_nr % 2 == 0 else "recto"
            margin_col = marginalia + _marg_ed_html(page_nr)
            folio = (
                f'<div class="folio folio-2col {vcls}">'
                f'<div class="textcol">{fig_note}{body_regions}</div>'
                f'<aside class="margin-col">{margin_col}</aside></div>'
            )
        elif region_margin:
            # Per-line HTR with a detected marginal region: same true two-zone leaf,
            # margin side following recto/verso (recto→right, verso→left).
            vcls = "verso" if page_nr % 2 == 0 else "recto"
            folio = (
                f'<div class="folio folio-2col {vcls}">'
                f'<div class="textcol">{fig_note}{body_regions}</div>'
                f'<aside class="margin-col">{region_margin}</aside></div>'
            )
        else:
            folio = f'<div class="folio">{marginalia}{fig_note}{body_regions}</div>'
        body = (
            folio
            + '<div class="teige-pane"><div class="teige-label">Teige (1570), '
            f"přibližné zarovnání</div>{teige}</div>"
        )
    else:
        body = f'<div class="empty">{_esc(binding_note) if binding_note else "[prázdná strana / vazba]"}</div>'

    body = _zodiac_textstyle(body)
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fol. {page_nr:04d} — {_esc(title)}</title>
<link rel="stylesheet" href="assets/edition.css"></head>
<body class="mode-dipl layout-lined app-on">
<header>
  <a class="home" href="index.html">≡</a>
  <h1>{_esc(title)}</h1>
  <div class="modes">
    <span class="ctl">
      <span class="ctl-lbl">Znění</span>
      <label><input type="radio" name="mode" value="dipl" checked> transliterace</label>
      <label><input type="radio" name="mode" value="norm"> transkripce</label>
      <label><input type="radio" name="mode" value="teige"> edice (Teige)</label>
    </span>
    <span class="ctl">
      <span class="ctl-lbl">Sazba</span>
      <label><input type="radio" name="layout" value="lined" checked> řádky</label>
      <label><input type="radio" name="layout" value="flow"> čtení</label>
    </span>
    <label class="ctl-app"><input type="checkbox" id="appToggle" checked> ediční značky</label>
  </div>
</header>
<nav class="pager">
  <a class="prev" href="{prev_link}"{'' if prev_link else ' hidden'}>← předchozí</a>
  <span class="folno">fol. {page_nr:04d} / {total:04d} &nbsp; {ahmp}</span>
  <a class="next" href="{next_link}"{'' if next_link else ' hidden'}>další →</a>
</nav>
<div class="section-label">{_esc(section_label)}</div>
<main class="leaf">{body}{scan_embed}</main>
<footer>Diplomatický přepis (Transkribus HTR, model 263129). Normalizace heuristická — nutná korektura.
Teige: edice 1901, public domain. Vyobrazení ani skeny se zde nereprodukují — odkazy „sken"
vedou na stabilní permalink archiválie v Archivu hlavního města Prahy (katalog.ahmp.cz);
ten otevře dokument, v prohlížeči pak přejděte na příslušné folio (skeny jsou číslovány shodně).</footer>
<script src="assets/edition.js"></script>
</body></html>"""


_BADGE = (
    ' <span class="teige-badge" title="Táborského zpráva — referenční edice Teige">T</span>'
)


def _toc_item(n: int, snip: str, teige: bool) -> str:
    badge = _BADGE if teige else ""
    return (
        f'<li><a href="p{n:04d}.html">fol. {n:04d}</a>{badge} '
        f'<span class="snip">{_esc(snip)}</span></li>'
    )


# Stav zpracování po částech knihy. Průběžně se aktualizuje (edit → regenerace → deploy).
# klíč stavu: done = hotový čistý přepis · partial = rozpracováno · todo = chybí · na = prázdná
_STATUS_ROWS: list[tuple[str, str, str, str, str]] = [
    ("f1", "předsádka", "—", "na", "—"),
    ("f2–f3", "úvodní astron. tabulky — Hájek z Hájku (přední list, opis ≈ 1689)",
     "D · ~1689", "done",
     "f2 = táž tabule jen předkreslená a nevyplněná, ale s týmž záhlavím a <b>touž rukou jako "
     "f3</b> (kopista r. 1689 list nadepsal a nalinkoval, vyplnil až f3); f3 = symetrická "
     "perpetuální tabule po krocích délky dne (Tadeáš Hájek z Hájku, pól 50°, nový kalendář) — "
     "přepsána věrně a kompletně: jarní i podzimní blok (měsíc, den, svátek, vstupy Slunce) čteny "
     "ze skenu, časy ověřeny výpočtem; německý návod, jak takovou tabuli užít, je dole na f54 — "
     "ale ten platí pro f3 i f55 (tytéž hodnoty), vznikl až po tabuli (≥1641) a je rukou "
     "pozdějšího, německy mluvícího orlojníka. Jediné zbylé [?] je přízvisko jména „Jana“ "
     "u dne 12. XI (sv. Jan Almužník?) — viz ediční pozn. u tabulky"),
    ("f4", "latinský epigram (sedm pahorků pražských)", "C? · ~1641–42", "done",
     "přepsáno + překlad; „Praha jako nový Řím“, bez podpisu. Ruka pracovně připsána "
     "<b>C</b> (táž jako f80; writer-ID + obsah) — jistota střední, viz ediční pozn."),
    ("f5–f12", "Táborský: verš, dedikace, kap. I–VI", "A · 1587", "done", "drobná [?] místa"),
    ("f13–f30", "Táborský: kap. VI–XIII", "A · 1587", "done",
     "marginálie ověřeny ze skenu (f13 nejisté); pozdější vsuvka f22 (přestavba měsíční koule "
     "na samootáčivou) = ruka C ~1641–42"),
    ("f31–f42", "Táborský: kap. XIII–XVIII", "A · 1587", "partial",
     "Teige-ukotveno; diplomatická kontrola po řádcích; pozdější vsuvka f38 (redatace orloje "
     "k r. 1410, „vide list purkmistra“) = jiná pozdější ruka ≥1628 (B/C nerozhodnuto, obsahově spíše B)"),
    ("f43–f49", "Táborský: biografický závěr, verše, kolofony 1570 + 1587", "A · 1587", "done", "—"),
    ("f50", "Tabula Litera dominicalis (N. I)", "C · ~1641–42", "done",
     "cyklus solaris → nedělní písmeno (jul./greg.), 28 řádků, ověřeno vzorcem"),
    ("f51–f52", "List purkmistra 1410 (něm., opsáno 1628)", "B · 1628", "done", "—"),
    ("f53–f54", "List purkmistra — dobový český překlad", "B · 1628", "done",
     "český překlad kompletní (ruka B) — od „My, purkmistr…“ přes datovací doložku 1410 "
     "(„ve čtvrtek před sv. Havlem“, ověřeno: 9. X 1410 = čtvrtek) až po připsaný kancelářský "
     "kolofon 1628 (Mikuláš Petr). Německý návod na f54 (přepočet německé↔orlojní hodiny) — "
     "<b>zvláštní německy píšící ruka</b> (≥1641) — přepsán a přeložen, <b>všechna čísla "
     "příkladu ověřena</b> (f55: 3. máj = 4:43; verify_f54_sunrise.py); orientační zůstávají "
     "jen spojovací německé fráze ([?]/[…])"),
    ("f55–f69", "komputistické/astron. tabulky + próza (sekce ~1641–42)", "C · ~1641–42", "done",
     "vše přepsáno a ověřeno výpočtem: litera dominicalis (f50/56), epakty (f57), vejchod Slunce "
     "(f55), intervallum jul./greg. (f60/61 — týden Velikonoc), festa mobilia jul./greg. (f58/59), "
     "calendarium novoluní po dnech (f66), násobilka (f69) + komputistické prózy f62–65, 67, 68"),
    ("f70–f79", "Astrolabium parvum (~1642, čes. překlad Franze Rittera)", "C · ~1641–42", "done",
     "noční určení času ze stínu Měsíce + oprava astrolábem; datovaný příklad z 1. XI 1642 "
     "ověřen nezávislým výpočtem (tools/verify_astrolabe_1642.py)"),
    ("f80", "dva latinské epigramy (Pythagoras, Archimedes) + nákres trojúhelníku",
     "C? · ~1641–42", "done",
     "přepsáno + překlad (hekatomba; „pohnu zemí“). Ruka pracovně připsána <b>C</b> "
     "(táž jako f4; writer-ID, matematický obsah, poloha hned za Astrolabiem) — jistota střední"),
    ("f81", "předsádka", "—", "na", "—"),
]
_STATUS_BADGE = {
    "done": '<span class="b-done">✅ hotovo</span>',
    "partial": '<span class="b-partial">🔶 rozpracováno</span>',
    "todo": '<span class="b-todo">❌ chybí</span>',
    "na": '<span class="b-na">— vazba/prázdná</span>',
}

# --- orloj1570: originál Táborského (autograf 1570), 30 snímků vč. desek vazby ----------
# Toto je PŘEDLOHA, kterou roku 1587 opsal Carchesius (orlojní kniha 1587 = jiná edice).
# Jen Táborského Zpráva: titulní verš, dedikace, XVIII kapitul, kolofon, závěrečné verše.
_STATUS_ROWS_1570: list[tuple[str, str, str, str, str]] = [
    ("f1", "přední deska vazby — zlacený titul „Sprawa o orlogi pražském“, znak Starého "
     "Města Pražského a letopočet 1570", "—", "na", "renesanční vazba; sken nereprodukován"),
    ("f2", "přední přídeští — archivní exlibris „Ins Stadt-Archiv der Haupt-Stadt Prag "
     "gehörig“", "—", "na", "—"),
    ("f3", "titulní list — úvodní verš a datace (dokončeno „léta drahého patnáctistého "
     "sedmdesátého“)", "Táborský · 1570", "done", "přepsáno"),
    ("f4–f5", "dedikace pánuom purgmistru a raddě Starého Města Pražského", "Táborský · 1570",
     "done", "drobná [?] místa"),
    ("f6–f29", "Zpráva o orloji — XVIII kapitul: chvála a popis orloje, jeho sfér, soukolí "
     "a polouorlojního počtu, tajnosti stroje; dějiny správců (mistr Hanuš, žák Jakub, "
     "Václav Tobiáš) a Táborského druhé zpravování. Na f29 kolofon „Dokonán jest spis tento "
     "šťastně v středu na den sv. Lukáše léta páně 1570“ a závěrečné verše", "Táborský · 1570",
     "partial",
     "HTR (Transkribus 263129) ukotvené na Teigeho edici 1901, korektura po řádcích; "
     "marginálie (rejstříkové glosy) čteny ze skenu a vysazeny do postranní zóny"),
    ("f30", "zadní deska vazby — tepaná kůže se zlaceným medailonem (český lev)", "—", "na",
     "sken nereprodukován"),
]
# Popisky vazebních/prázdných folií pro tělo stránky (jinak generické „[prázdná strana]“).
_BINDING_NOTE_1570: dict[int, str] = {
    1: "[přední deska vazby — zlacený titul „Sprawa o orlogi pražském“, znak Starého Města "
       "Pražského a letopočet 1570; sken viz AHMP]",
    2: "[přední přídeští — archivní exlibris „Ins Stadt-Archiv der Haupt-Stadt Prag gehörig“]",
    30: "[zadní deska vazby — tepaná kůže se zlaceným medailonem s českým lvem; sken viz AHMP]",
}


def _status_first_page(fol: str) -> str:
    """Page link for a status-row folio range, e.g. 'f5–f12' -> 'p0005.html'."""
    m = re.search(r"\d+", fol)
    return f"p{int(m.group()):04d}.html" if m else ""


def _status_html(slug: str = "") -> str:
    is_1570 = "1570" in slug
    status_rows = _STATUS_ROWS_1570 if is_1570 else _STATUS_ROWS
    head_part = "část" if is_1570 else "část knihy"
    rows = "".join(
        f'<tr data-href="{_status_first_page(fol)}">'
        f'<td><a href="{_status_first_page(fol)}">{_esc(fol)}</a></td>'
        f"<td>{_esc(part)}</td>"
        f'<td class="hand">{_esc(hand)}</td>'
        f"<td>{_STATUS_BADGE.get(st, _esc(st))}</td><td>{_esc(rest)}</td></tr>"
        for fol, part, hand, st, rest in status_rows
    )
    if is_1570:
        note = (
            '<p class="status-note"><b>Co zbývá:</b> diplomatická kontrola Zprávy po řádcích '
            "(f6–f29) proti skenu a dočtení sporných marginálií. Vazební a prázdná folia: "
            "f1 (přední deska), f2 (přídeští), f30 (zadní deska). Celý text je autograf "
            "<b>Jana Táborského (1570)</b> — jediná ruka.</p>"
        )
    else:
        note = (
            '<p class="status-note"><b>Stav: textově i tabulkově kompletní</b> — každé folio je '
            "buď opravený přepis, ověřená tabulka, nebo vazba; žádné nepřepsané ani neověřené "
            "místo. Sloupec „ruka · datace“ ukazuje vrstvení konvolutu: <b>A</b> Carchesius 1587 "
            "(jádro), <b>B</b> Mikuláš Petr 1628 (List purkmistra), <b>C</b> orlojník-astronom "
            "~1641–42 (komputus + Astrolabium), <b>D</b> ~1689 (Hájkova tabule). <b>Do finální "
            "kritické edice zbývá:</b> diplomatická kontrola f31–42 po řádcích, expertní revize "
            "německého znění návodu f54 a dořešení zbylých nejistých čtení [?]. Prázdné/předsádky: "
            "f1, f81.</p>"
        )
    return (
        '<table class="status"><caption>Stav zpracování (průběžně aktualizováno)</caption>'
        f"<thead><tr><th>folia</th><th>{head_part}</th><th>ruka · datace</th>"
        f"<th>stav</th><th>zbývá</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>{note}"
    )


def _tiraz_1570(ahmp_a: str) -> str:
    """„O edici“ pro originál Táborského (autograf 1570, AHMP sign. 1867)."""
    return (
        '<section class="tiraz"><h2>O edici</h2>'
        "<p><b>Pramen — autograf Jana Táborského z Klokotské Hory (1570).</b> Archiv hlavního "
        f"města Prahy, Sbírka rukopisů, sign. 1867. {ahmp_a}. Jde o <b>originál</b> Táborského "
        "<i>Zprávy o orloji pražském</i>, dokončený podle vlastního kolofonu <b>v středu na den "
        "sv. Lukáše, tj. 18. října 1570</b> (f29). Rukopis je vázán v skvostné renesanční kožené "
        "vazbě se zlaceným titulem „Sprawa o orlogi pražském“, znakem Starého Města Pražského a "
        "letopočtem 1570 (přední deska, f1); na zadní desce (f30) je zlacený medailon s českým "
        "lvem. Edice zpracovává <b>vlastní text Zprávy</b> (f3–f29): titulní verš, dedikaci, "
        "XVIII kapitul, kolofon a závěrečné verše. Folia f1, f2 a f30 jsou <b>vazba a přídeští</b> "
        "(bez textu Zprávy).</p>"
        '<p class="teige"><b>Vztah k orlojní knize 1587.</b> Tento rukopis je <b>předloha</b>, '
        "kterou roku 1587 opsal staroměstský písař <b>Matouš Carchesius Jablonský</b> do tzv. "
        "orlojní knihy (AHMP, inv. č. 7916) — ta je zpracována jako <b>samostatná edice</b> a od "
        "originálu se místy liší (varianty písaře, pozdější přídavky, komputistické tabulky a "
        "další části). <b>Edici originálu 1570 vydal Josef Teige</b> v Časopise Společnosti přátel "
        "starožitností českých (roč. IX, 1901). Zde tedy Teige vydává <b>tentýž</b> rukopis, "
        "který čteme — slouží proto jako přímá <b>kolační a korekturní opora</b>.</p>"
        "<p><b>Metoda — syntetická edice.</b> Strojové rozpoznání rukopisu (HTR, Transkribus "
        "PyLaia, čeština 263129) tvoří kostru přepisu řádek po řádku; ta je <b>korigována podle "
        "Teigeho edice 1901</b> a sporná místa (zejména marginálie) <b>dočítána ze skenu</b>. "
        "Text lze zobrazit ve <b>třech režimech</b>: <i>transliterace</i> (čtení ukotvené na "
        "řádky rukopisu) / <i>transkripce</i> (diakritická, dle normy Ivan Šťovíček a kol.) / "
        "<i>edice (Teige)</i>.</p>"
        "<p><b>Marginálie.</b> Na okrajích jsou <b>rejstříkové glosy</b> shrnující přilehlý text "
        "(např. „Tabula horarum planetarum“, „Obnovení orloje“, „Tobiáš umřel“, „Táborský "
        "přistúpil“, „Čeho nevyšetřili“, „Jakub Špaček“, „Suma“). V edici jsou vysazeny do "
        "<b>postranní zóny</b> podle strany rukopisu (recto → pravý okraj, verso → levý).</p>"
        '<p class="warn"><b>Stav: rozpracovaná pracovní edice.</b> Normalizace je heuristická a '
        "vyžaduje korekturu; diplomatická kontrola Zprávy po řádcích (f6–f29) proti skenu "
        "probíhá. Zatím neslouží jako citovatelná kritická edice.</p>"
        '<p><b>Práva a licence:</b> skeny ani vyobrazení se zde nereprodukují — odkazy „sken“ '
        "vedou do prohlížeče AHMP (práva k reprodukcím: Archiv hlavního města Prahy). "
        "Text edice © David Knespl, licence CC&nbsp;BY&nbsp;4.0; software EUPL-1.2.</p>"
        "<p><b>Použité zdroje a poděkování.</b> Pramen a skeny: <b>Archiv hlavního města "
        "Prahy</b> (sign. 1867). Strojový přepis: <b>Transkribus</b> (READ-COOP), model PyLaia "
        "263129. Kolace: edice originálu 1570 <b>Josefa Teigeho</b> (1901, public domain). Norma "
        "transkripce: <b>Ivan Šťovíček a kol.</b> Datace a badatelství orloje: <b>Zdeněk "
        "Horský</b>.</p></section>"
    )


def _index_doc(
    title: str,
    sections: list[tuple[str, int, int, str]],
    pages: dict[int, tuple[str, bool]],
    ahmp_permalink: str | None = None,
    work_slug: str = "",
    has_marginalia_page: bool = False,
) -> str:
    ahmp_a = (
        f'<a href="{_esc(ahmp_permalink)}" target="_blank" rel="noopener">'
        "záznam a skeny v katalogu AHMP ↗</a>"
        if ahmp_permalink else "katalog AHMP"
    )
    tiraz = (
        '<section class="tiraz"><h2>O edici</h2>'
        "<p><b>Pramen — jedna svázaná orlojní kniha (zápisy z let ~1587–1689).</b> Archiv "
        f"hlavního města Prahy, Sbírka rukopisů, inv. č. 7916. {ahmp_a}. Nejde o soubor volně "
        "vložených listů: <b>přímým ohledáním originálu v archivu (AHMP) bylo ověřeno, že jde "
        "o jediný původní svázaný celek</b> — <b>prázdný sešit svázaný vcelku a teprve pak "
        "postupně popisovaný</b>, nikoli pozdější tematická převazba. Zápisy proto vznikaly na "
        "<b>předem svázané archy</b> a pořadí folií v hlavním korpusu odpovídá chronologii jejich "
        "vzniku. <b>Jedna výjimka</b>: referenční sluneční tabule na "
        "ponechaných <b>volných předních listech (fol. 2–3) byly dopsány nejpozději</b> (dle "
        "vlastního letopočtu ≈ 1689) — fyzicky jsou první, ale časově poslední, takže pořadí "
        "folií tu chronologii neodráží a <b>protahují celkový rozsah psaní knihy zhruba na "
        "století</b>. Díky chronologii hlavního korpusu jsou <b>datovatelné i pozdější přípisky "
        "jednotlivých pisatelů</b>; právě "
        "na nich stojí přeřazení vzniku orloje k r. 1410 (Z. Horský). Kniha má několik částí: "
        "(1) <b>opis Táborského <i>Zprávy o orloji pražském</i></b> (fol. 5–49), který roku "
        "1587 pořídil staroměstský písař <b>Matouš Carchesius Jablonský</b> (kolofon fol. 47); "
        "(2) <b>opis Listu purkmistra</b> — původní listina je <b>z r. 1410</b> (de facto smlouva "
        "Starého Města s hodinářem Mikulášem z Kadaně na zhotovení orloje), v knize však <b>opis, "
        "který r. 1628 vypsal ze starých knih hořejší kanceláře Mikuláš Petr</b> (podpis fol. 52): "
        "německy (fol. 51–52) i v dobovém českém překladu (fol. 53–54); (3) "
        "<b>komputistické a astronomické tabulky</b> (fol. 2–3, 50, 55–69 — Littera dominicalis, "
        "zlaté číslo, epakta, východ slunce, polouorlojní počet); tabule délky dne / východu / "
        "západu (fol. 3) je dle <b>vlastního záhlaví</b> dílo <b>Tadeáše Hájka z Hájku</b> pro "
        "výšku pólu 50° (Praha), upravené na nový kalendář (opis ≈ 1689); (4) <b>Astrolabium "
        "parvum</b> "
        "(fol. 70–79, ~1642, autorův český překlad Franze Rittera z Norimberku — ruka C); a (5) "
        "<b>pozdější přípisky pisatelů</b> (16.–17. stol.). Edice "
        "zatím zpracovává především část (1) a (2).</p>"
        "<p><b>Metoda — syntetická edice.</b> Text vzniká <b>kombinací zdrojů</b>, ne pouhým "
        "strojovým přepisem: strojové rozpoznání rukopisu (HTR, Transkribus PyLaia — čeština "
        "263129, německý Kurrent 27457; dva nezávislé běhy), ruční korektura čtením skenu, "
        "rozpoznání tabulek (Docling TableFormer) a externí opory — edice originálu 1570 "
        "(J. Teige, 1901), paleografický přepis Listu purkmistra a přepis Astrolabia (orloj.eu). "
        "Výsledek je tedy <b>syntéza</b> více pramenů. Česky psaný text lze zobrazit ve třech "
        "režimech: diplomatický / normalizovaný (diakritický, dle normy Ivan Šťovíček a kol.) / "
        "Teige.</p>"
        '<p class="teige"><b>Pozor na Teigeho — předloha ≠ opis.</b> Teigeho edice (1901) vydává '
        "<b>předlohu, totiž originál Táborského zprávy z r. 1570</b>. Zde se ale zpracovává její "
        "<b>opis Jablonského z r. 1587</b> — <b>jiný svědek</b>, který se od originálu místy liší "
        "(varianty písaře i pozdější přídavky: např. přestavba měsícového soukolí, kolofon "
        "opisovače 1587, „přídavek na spheru“, poznámky pozdějších pisatelů odkazující na List purkmistra 1410). "
        "Proto se text <b>neopravuje podle Teigeho</b>: Teige slouží jen jako <b>čtecí opora a "
        "kolace</b> a <b>odlišnosti opisu se záměrně zachovávají</b> (a značí), nikoli zarovnávají "
        "na originál.</p>"
        '<p class="warn"><b>Stav: rozpracovaná pracovní edice.</b> Normalizace je heuristická a '
        "vyžaduje korekturu; část přípisků na okraji (fol. 13–30) není ověřena proti skenu; oddíl "
        "fol. 31–42 je čtecí oporou ukotven na Teigem. Zatím neslouží jako citovatelná kritická "
        "edice.</p>"
        '<p class="verify"><b>Ověření tabulek výpočtem.</b> Číselné komputistické a astronomické '
        "tabulky byly přepsány ručně (strojové rozpoznání rukopisných číslic selhává) a poté "
        "<b>deterministicky ověřeny nezávislým výpočtem</b> (skript <code>tools/verify_computus.py</code> "
        "v repozitáři; všechny kontroly procházejí): "
        "<b>fol. 50 a 56</b> (<i>Tabula Litera dominicalis</i>, „N. I“) — juliánská i gregoriánská "
        "nedělní písmena souhlasí s výpočtem pro všech 28 let slunečního cyklu; gregoriánský sloupec "
        "platí pro 17. století (1583–1699), což zároveň datuje použitelnost tabulky. "
        "<b>fol. 57</b> (<i>Tabula Epactarum</i>, „N. 2“) — všechny tři gregoriánské sloupce epakt "
        "souhlasí s výpočtem (velikonoční úplněk dle J. Meeuse) pro 19 zlatých počtů ve více "
        "obdobích; juliánský sloupec = gregoriánský + 10 (10denní rozdíl kalendářů), hranice "
        "období odpovídají gregoriánským korekcím. "
        "<b>fol. 55</b> (východ Slunce) — sezónní průběh přesně odpovídá astronomickému "
        "výpočtu pro Prahu (φ ≈ 50,09°, <b>pravé Slunce</b>): residuum je ploché přes celý rok "
        "(tedy bez chyby přepisu i zeměpisné šířky). Tabule počítá východ jako <b>střed Slunce "
        "na geometrickém obzoru bez refrakce</b> (perpetuální tabule refrakci běžně vynechávaly) "
        "— při této definici je odchylka ≤ 2 min; vůči modernímu východu (horní okraj + "
        "refrakce, −50′) je rukopis o ~7 min později. Těsnost shody (RMS ~0,8 min přes 365 dní) "
        "ukazuje, že jde o data <b>vypočtená, ne pozorovaná</b> — nejspíš opsaná z hotové "
        "tištěné tabule; celá sekce je datovatelná kolem r. 1641 (podrobný rozbor v metodické "
        "poznámce u fol. 55). "
        "<b>fol. 69</b> (násobilka) — součiny souhlasí. "
        "<b>fol. 60 a 61</b> (<i>Tabula intervalli Paschae</i>, juliánská a gregoriánská) — "
        "dvojčíslí v buňkách dekódováno (první číslo = pořadí týdne Velikonoc, druhé doplněk): "
        "juliánská <b>f60 souhlasí ve všech 133 buňkách</b>, gregoriánská <b>f61 v 191 z 210</b> "
        "— zbylé neshody leží v zóně <b>epakty 25/XXV</b> (gregoriánská zvláštnost s dvojí "
        "podobou epakty), kterou je třeba dořešit na originále; princip i většina tabule jsou "
        "potvrzeny. (Dřívější verze edice uváděla f60 jako nedekódovanou — překonáno.)</p>"
        "<p><b>Písařské ruce.</b> Kniha je <b>konvolut čtyř hlavních rukou z let ~1587–1689</b>. "
        "<b>A — Matouš Carchesius Jablonský</b> (1587, kolofon fol. 47): opis Táborského "
        "<i>Zprávy</i> fol. 5–49 a její rejstříkové glosy fol. 13–46. <b>B — Mikuláš Petr</b> "
        "(1628, podpis fol. 52): List purkmistra německy (fol. 51–52) i v dobovém českém "
        "překladu (fol. 53–54). <b>C — orlojník-astronom</b> (~1641–1642): komputistické tabulky "
        "a próza (fol. 50, 55–69) a <b>Astrolabium parvum fol. 70–79</b> — <b>nikoli ruka A</b>: "
        "text mluví o Táborském ve 3. osobě, vznikl „poněvadž papír prázdný zůstával“, je to "
        "autorův <b>český překlad Franze Rittera z Norimberku</b> a nese <b>vlastní dataci „1642, "
        "1. Novembris“</b> (fol. 78). <b>D</b> (~1689): přední Hájkova tabule fol. 2–3. Německý "
        "návod k tabuli dole na fol. 54 (≥1641) je <b>nejistý</b> — buď C dvojjazyčně, nebo "
        "zvláštní německá ruka (jiný jazyk = jiné písmo, rukopisně nerozhodnutelné). Latinské "
        "epigramy fol. 4 a 80 (jednou rukou) pracovně připsány <b>ruce C</b> (writer-ID je řadí "
        "ke shluku C, sedí matematický obsah f80 i poloha hned za Astrolabiem, a C latinka "
        "„Corpus lunæ“ f22 / „Novembris“ f78 je s písmem epigramů slučitelná) — jistota střední. "
        "<b>Metoda atribuce:</b> syntéza tří kritérií "
        "— písmo (vizuální paleografie + počítačová <i>writer-ID</i> analýza ~4100 řádkových "
        "výřezů: texturní rysy ResNet-50 → UMAP/HDBSCAN), obsah / jazyk / odkazy a datace "
        "(kolofony, interní roky). Strojová analýza spolehlivě oddělí hrubé rozdíly (německý "
        "Kurrent vyšel jako čistý shluk), na jednotlivou krátkou glosu však nestačí — ta se "
        "rozhoduje paleograficky a obsahově. Jde o <b>pracovní atribuci, ne znalecký posudek</b>.</p>"
        "<p><b>Glosy a pozdější přípisky.</b> <b>Rejstříkové glosy fol. 13–46</b> (hesla "
        "„<i>Index Solis</i>“, „<i>Linea oppositionis/coniunctionis</i>“, „O pušce“, „Václav "
        "Zvůnek, třetí zprávce“, „Tobiáš umřel“ ad.) přisuzujeme <b>ruce A</b> — táž česká "
        "novogotická kurzíva jako hlavní text, týž dukt a mísení české a latinské terminologie; "
        "jde o <b>rejstříkový aparát opisovače</b>, ne cizí přípisky (hesla shrnují vyprávění, ne "
        "vnější události). <b>Dvě pozdější vsuvky 17. století jsou však cizíma rukama:</b> na "
        "<b>fol. 22</b> přípisek „<i>Nyní jest to jinače spraveno… žádných koleček není… samým "
        "otočováním se měsíce… corpus lunae o 1 grad… v 30 dnech celý se obrátí</i>“ dokumentuje "
        "<b>přestavbu měsíční koule na samootáčivou</b> a rukopisně i obsahem patří <b>ruce C</b> "
        "(~1641–42; slovem „nyní“ tu přestavbu datuje); na <b>fol. 38</b> přípisek „<i>…léta 1410… "
        "vide list purkmistra… sub figura 4</i>“ <b>přeřazuje vznik orloje k r. 1410</b> (proti "
        "„mistr Hanuš okolo 1490“ v textu) — pozdější latinsky gramotná ruka (≥1628, předpokládá "
        "vložený a očíslovaný List), <b>odlišná od C; mezi B a C nerozhodnuto</b>. Strojové "
        "shlukování rukopisu (writer-ID) oddělí hrubé rozdíly (německý Kurrent), ale na atribuci "
        "jednotlivé glosy nestačí — ta stojí na paleografii, obsahu a dataci.</p>"
        "<p><b>Odstín inkoustu.</b> Střední barva tahů marginálií proti hlavnímu textu v témž "
        "snímku (fol. 20 a 43) vychází <b>nepatrně světlejší a méně teplá</b> (méně "
        "červenohnědá; Δ jasu +13–15, Δ „tepla“ R−B −18 až −34 z 256). Tento rozdíl je však "
        "<b>zčásti artefaktem tenčího okrajového tahu</b> (úzké písmo „nabírá“ víc papíru), "
        "nikoli nutně jiným inkoustem. Závěr: týž <b>železo-duběnkový hnědý inkoust</b>, "
        "marginálie psané <b>jemnějším perem</b> (snad o málo zředěnější či v rychlejším "
        "samostatném sezení) — slučitelné se vznikem <b>současně s opisem</b> (1587), ne jako "
        "pozdější vrstva. (Paleografie i kolorimetrie ze skenu = pracovní hypotéza, ne znalecký "
        "posudek; jistota střední.)</p>"
        '<p><b>Práva a licence:</b> skeny ani vyobrazení se zde nereprodukují — odkazy „sken" '
        "vedou do prohlížeče AHMP (práva k reprodukcím: Archiv hlavního města Prahy). "
        "Text edice © David Knespl, licence CC&nbsp;BY&nbsp;4.0; software EUPL-1.2.</p>"
        "<p><b>Použité zdroje a poděkování.</b> Pramen a skeny: <b>Archiv hlavního města "
        "Prahy</b>. Strojový přepis: <b>Transkribus</b> (READ-COOP), modely PyLaia 263129 a "
        "27457. Kolace: edice originálu 1570 <b>Josefa Teigeho</b> (1901, public domain). "
        "Přepis Astrolabia parvum (fol. 70–79) přejat z orloj.eu — přepis <b>Pavel Baudisch</b>, "
        "poznámky a model <b>Petr Král</b> a kol. (Český spolek horologický); za orlojnické "
        "konzultace patří dík <b>Petru Skálovi</b> (ČSH). Paleografický přepis německého Listu "
        "purkmistra (fol. 51–52) byl pořízen na zakázku (autorka k doplnění); <b>dobový český "
        "překlad (fol. 53–54)</b> přejat z přepisu <b>Stanislava Macháčka</b> (<i>Nález zprávy "
        "o vytvoření orloje Starého Města r. 1410</i>, Zprávy Komise pro dějiny přírodních, "
        "lékařských a technických věd ČSAV, 10, 1962, s. 21–24); <b>zarovnán na vlastní HTR</b>. "
        "Norma transkripce: "
        "<b>Ivan Šťovíček a kol.</b> "
        "Datace a badatelství: <b>Zdeněk Horský</b> (1988); opis objevil <b>Stanislav "
        "Macháček</b> (1962). Rozpoznání tabulek: <b>Docling</b> (IBM).</p></section>"
    )
    uvod = (
        '<section class="uvod"><h2>Úvod</h2>'
        '<p class="lead">Digitální vědecká edice jediného rukopisu — orlojní knihy '
        "pražského orloje, do níž po celé století "
        "(~1587–1689) psali různí pisatelé — městský i kancelářský písař, orlojník-astronom a opisovač.</p>"
        "<p>Tato edice zpřístupňuje <b>jednu svázanou knihu</b> z Archivu hlavního města "
        "Prahy (Sbírka rukopisů, inv. č. 7916). Není to sborník volně vložených listů, "
        "ale <b>prázdný sešit svázaný vcelku a teprve pak postupně popisovaný</b> — což jsme "
        "ověřili přímým ohledáním originálu v archivu. Kniha je proto <b>konvolut</b>: vrství "
        "v sobě texty od konce 16. do konce 17. století, jak je psali po sobě jdoucí "
        "pisatelé.</p>"
        "<h3>O čem kniha je</h3>"
        "<ul>"
        "<li><b>Jádro (fol. 5–49):</b> opis <i>Zprávy o orloji pražském</i> Jana Táborského, "
        "který roku 1587 pořídil staroměstský písař <b>Matouš Carchesius Jablonský</b> — "
        "základní dobový popis stroje, jeho soukolí, dějin a obsluhy.</li>"
        "<li><b>List purkmistra (fol. 51–54):</b> opis (1628, <b>Mikuláš Petr</b>) listiny "
        "<b>z r. 1410</b> — de facto smlouvy Starého Města s hodinářem <b>Mikulášem z Kadaně</b> "
        "na zhotovení orloje; německy i v dobovém českém překladu.</li>"
        "<li><b>Komputistické a astronomické tabulky (fol. 2–3, 50, 55–69):</b> nedělní písmena, "
        "zlaté číslo, epakty, východ Slunce, počítání nového měsíce a Velikonoc; tabule délky "
        "dne (fol. 3) je opis <b>Hájkovy „Tabule dlúhosti dne a noci k spravování orloje“ "
        "(1574)</b>, zhotovené přímo pro pražský orloj.</li>"
        "<li><b>Astrolabium parvum (fol. 70–79, ~1642):</b> orlojníkův vlastní český překlad "
        "příručky <b>Franze Rittera</b> z Norimberku — jak astrolábem počítat čas, východ a "
        "západ Slunce i Měsíce, včetně řešených příkladů.</li>"
        "<li><b>Pozdější přípisky pisatelů</b> (16.–17. stol.) na okrajích a volných "
        "místech.</li>"
        "</ul>"
        "<h3>Na co jsme přišli</h3>"
        "<ul>"
        "<li><b>Kniha je datovací stroj.</b> Protože byla svázána jako prázdný sešit a "
        "popisována postupně, <b>pořadí folií odráží chronologii vzniku</b> — díky tomu lze "
        "datovat i nedatované přípisky. (Výjimka: přední volné listy fol. 2–3 byly dopsány "
        "<b>nejpozději</b>, ≈ 1689, takže fyzicky první jsou časově poslední.)</li>"
        "<li><b>Čtyři hlavní písařské ruce.</b> Rozlišili jsme je (A Carchesius 1587 · "
        "B Mikuláš Petr 1628 · C orlojník-astronom ~1641–42 · D ~1689) syntézou paleografie, "
        "<b>počítačové analýzy písma</b> a obsahu/datace. Mj. se ukázalo, že <b>Astrolabium "
        "není ruka A</b>, ale vlastní překlad orlojníka C z r. ~1642.</li>"
        "<li><b>Doklad pro vznik orloje r. 1410.</b> Přeřazení vzniku orloje od legendárního "
        "„mistra Hanuše (~1490)“ k r. <b>1410</b> stojí na <b>pozdějším přípisku na fol. 38</b>, "
        "který odkazuje na vložený List purkmistra — to je opora datace Z. Horského.</li>"
        "<li><b>Přesně datované pozorování (1. 11. 1642).</b> Astrolabium nese jediné přesně "
        "datované noční pozorování. <b>Ověřili jsme je výpočtem</b>: Slunce na 8° Štíra, Měsíc "
        "na 1° Ryb, západ Slunce 16:48, kulminace Měsíce ~19:48 — vše souhlasí s moderním "
        "přepočtem na 1–2 minuty a potvrzuje rok 1642 (gregoriánský kalendář).</li>"
        "<li><b>Systematická chyba ze stáří tabulek.</b> Slunce i Měsíc leží shodně o ~1° níže "
        "než pravá poloha. Že je odchylka u obou stejná je <b>průkazem</b>, že nejde o chybu "
        "data ani měření, ale o <b>precesní zastarání předrudolfínských tabulek</b> (o řádově "
        "století starších), z nichž orlojník počítal; v rozdílu poloh Slunce a Měsíce se chyba "
        "vykrátí, takže výsledný čas přesto sedí.</li>"
        "<li><b>Všechny číselné tabulky dekódovány a ověřeny.</b> Komputistické tabulky "
        "(nedělní písmena, epakty, východ Slunce, intervaly Velikonoc, věčný kalendář, "
        "násobilka) jsme rozluštili podle dobových vzorců a <b>nezávisle ověřili buňku po "
        "buňce</b> — včetně obou intervalových tabulí Velikonoc (juliánská f60 souhlasí ve "
        "všech 133 buňkách). Jediná drobná výhrada: u gregoriánského dvojčete <b>f61</b> sedí "
        "191 z 210 buněk, zbylé neshody leží v proslulé zóně <b>epakty 25</b> a čekají na "
        "kontrolu na originále.</li>"
        "<li><b>Dohledané předlohy.</b> Dvě části jsme ztotožnili s konkrétními tisky a porovnali: "
        "<b>Astrolabium parvum</b> je překlad spisu <b>Franze Rittera</b> (Norimberk 1613) — "
        "shodují se pasáže i figury (vč. desky pro pól 50°), orlojník k němu přidal české hodiny "
        "a vlastní příklad 1642; <b>tabule f3</b> je Hájkova <b>„Tabule… k spravování orloje“ "
        "(1574)</b> zhotovená přímo pro orloj, jejíž tištěný originál se zřejmě nedochoval — f3 "
        "je tak pravděpodobně její vzácný svědek.</li>"
        "</ul>"
        "<h3>Metody a nástroje</h3>"
        "<p><b>Syntetická edice.</b> Text nevzniká pouhým strojovým přepisem, ale "
        "<b>kombinací zdrojů</b>: strojové rozpoznání rukopisu (HTR — <b>Transkribus</b> "
        "PyLaia, čeština i německý Kurrent, dva nezávislé běhy), <b>ruční korektura čtením "
        "skenu</b>, rozpoznání tabulek (<b>Docling</b> TableFormer) a externí opory — edice "
        "originálu 1570 (J. Teige, 1901) a přepisy z orloj.eu.</p>"
        "<p><b>Převzaté a zakázkové přepisy.</b> Paleografický přepis <b>německé verze Listu "
        "purkmistra</b> (fol. 51–52, novogotická kurzíva) pořídil <b>na zakázku profesionální "
        "paleograf</b>; <b>dobový český překlad</b> (fol. 53–54) je přepis, který z rukopisu "
        "pořídil a r. 1962 publikoval <b>Stanislav Macháček</b> — jeho přepis jsme zarovnali "
        "na vlastní HTR. Přepis "
        "<b>Astrolabia parvum</b> (fol. 70–79) je převzat z <b>orloj.eu</b> — přepis "
        "<b>Pavel Baudisch</b>, odborné poznámky a analýza <b>Petr Král</b> a kol. (Český "
        "spolek horologický). <b>Každý externí přepis jsme navíc vždy porovnali se strojovým "
        "rozpoznáním (HTR) téhož folia</b> — slouží tak jako vzájemná kontrola, ne jako "
        "nekriticky převzatý text.</p>"
        "<p><b>Ověřování výpočtem.</b> Číselné tabulky byly přepsány ručně (strojové čtení "
        "číslic selhává) a poté <b>deterministicky ověřeny nezávislým výpočtem</b> — dobové "
        "komputistické vzorce a astronomie (Meeus); ověřovací skripty jsou součástí "
        "repozitáře.</p>"
        "<p><b>Počítačová identifikace písaře (writer-ID).</b> Ruce jsme nejdřív roztřídili "
        "<b>vlastním skriptem</b> (<code>cluster_hands.py</code>, otevřený, licence EUPL-1.2), "
        "inspirovaným běžnými postupy <i>writer-identification</i> / <i>script-classification</i>. "
        "Postup: ze <b>4132 řádkových výřezů</b> všech 81 folií se neuronovou sítí <b>ResNet-50</b> "
        "(předtrénovanou na ImageNetu, knihovna <i>torchvision</i>) vzaly <b>texturní rysy</b> ze "
        "střední vrstvy (drží <i>duktus</i> písma, ne obsah), zprůměrovaly přes drobné výřezy podél "
        "tahů a L2-normalizovaly; volitelně se přidala ruční stylometrie (sklon, tloušťka tahu, "
        "hustota inkoustu). Vektory se zobrazily do nízkého rozměru (<b>UMAP</b>) a shlukovaly "
        "(<b>HDBSCAN</b>). Skript <b>spolehlivě oddělí hrubé rozdíly</b> — německý Kurrent "
        "(fol. 51–52) vyšel jako čistý samostatný shluk — a mapuje rejstříky kodexu "
        "(próza × tabulky × němčina). <b>Doložená mez:</b> na atribuci <b>jednotlivé krátké "
        "glosy</b> skript nestačí — cílené nejbližší-ruka srovnání dalo všem kandidátům "
        "podobnost 0,96–0,99 bez odstupu a kontrola selhala (přípisek fol. 22, o němž z písma "
        "víme, že je ruka C, vyšel nejblíž ruce A); na krátkém fragmentu dominuje morfologie "
        "výřezu, ne identita ruky. Writer-ID je proto <b>jen jedno ze tří kritérií</b> atribuce — "
        "jednotlivé přiřazení stojí na paleografii a obsahu/dataci, ne na skriptu. Použitý "
        "open-source základ: PyTorch/<i>torchvision</i> (ResNet-50), <i>umap-learn</i>, "
        "<i>hdbscan</i>.</p>"
        "<p><b>Čtenářské rozhraní.</b> Český text lze zobrazit ve <b>třech režimech</b> "
        "(diplomatický / normalizovaný / Teige), s <b>číslováním řádků podle předlohy</b> "
        "a rozbalovacími edičními poznámkami; okrajové přípisky stojí ve vnější margině "
        "jako v rukopise.</p>"
        '<p class="more">▸ Podrobné vymezení pramene, metody, písařských rukou, '
        "ověření tabulek, práv a poděkování viz <b>O edici</b> níže.</p>"
        "</section>"
    )
    is_1570 = "1570" in work_slug
    if is_1570:
        tiraz = _tiraz_1570(ahmp_a)
        uvod = ""
    blocks = []
    for _kind, lo, hi, label in sections:
        items = "\n".join(
            _toc_item(n, pages[n][0], pages[n][1]) for n in range(lo, hi + 1) if n in pages
        )
        blocks.append(
            f'<section class="toc-section"><h2>{_esc(label)} '
            f'<span class="range">(fol. {lo:04d}–{hi:04d})</span></h2>'
            f'<ol class="toc">{items}</ol></section>'
        )
    n_teige = sum(1 for v in pages.values() if v[1])
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><link rel="stylesheet" href="assets/edition.css"></head>
<body class="mode-dipl">
<header><h1>{_esc(title)}</h1></header>
<main>
{uvod}
{_status_html(work_slug)}
{'' if is_1570 and not has_marginalia_page else '<p class="marg-link">▸ <a href="marginalia.html">Rozbor marginálií</a> — přepisy okrajových přípisků folií 13–46, co přinášejí, identifikace písaře a datace.</p>'}
{tiraz}
<p class="note">{'Autograf Jana Táborského (1570), jeden svázaný celek.' if is_1570 else 'Jedna svázaná kniha (více částí, jeden celek).'} <span class="teige-badge">T</span> = {'folia, k nimž Teigeho edice originálu (1901) poskytuje srovnávací znění' if is_1570 else 'folia s opisem Táborského zprávy, kde existuje referenční edice (Teige 1901); ostatní oddíly referenci nemají'}.
Označeno {n_teige} z {len(pages)} folií. Hranice oddílů jsou odvozené automaticky (heuristika).</p>
{"".join(blocks)}</main>
<footer>{len(pages)} folií. Diplomatická edice z Transkribus HTR.</footer>
<script>document.querySelectorAll('.status tbody tr[data-href]').forEach(function(tr){{tr.addEventListener('click',function(e){{if(e.target.closest('a'))return;location.href=tr.dataset.href;}});}});</script>
</body></html>"""


_CSS = """
:root{--ink:#2b2b2b;--paper:#f7f3ea;--accent:#7a5c2e;}
*{box-sizing:border-box}
body{margin:0;font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:#e9e3d6}
header{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid #cdbf9f;
  padding:.5rem 1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
header h1{font-size:1rem;margin:0;flex:1 1 auto}
header .home{font-size:1.3rem;text-decoration:none;color:var(--accent)}
.modes{display:flex;gap:.9rem;align-items:center;flex-wrap:wrap}
.modes .ctl{display:inline-flex;align-items:center;gap:.5rem;padding:.1rem .55rem;
  background:#f1ead8;border:1px solid #ddd0ad;border-radius:6px}
.modes .ctl-lbl{font-family:system-ui,sans-serif;font-size:.62rem;text-transform:uppercase;
  letter-spacing:.05em;color:#9a8d70}
.modes label{cursor:pointer;font-family:system-ui,sans-serif;font-size:.8rem}
.modes .ctl-app{font-family:system-ui,sans-serif;font-size:.8rem;cursor:pointer}
.modes input{vertical-align:middle}
.pager{max-width:min(97vw,86rem);margin:.6rem auto 0;padding:0 1rem;display:flex;justify-content:space-between;
  align-items:center;font-family:system-ui,sans-serif;font-size:.85rem}
.pager a{color:var(--accent);text-decoration:none}
.pager .folno{color:#6b6256}
.pager a[hidden]{visibility:hidden}
main{max-width:62rem;margin:1rem auto 3rem;padding:0 1rem}
/* folio pages use (almost) the full screen width so lines need not wrap */
main.leaf{max-width:min(97vw,86rem)}
.folio{background:var(--paper);border:1px solid #cdbf9f;border-radius:4px;padding:1.2rem 1.6rem;
  box-shadow:0 1px 3px rgba(0,0,0,.12)}
/* two-zone leaf: text column + a dedicated outer margin (recto→right, verso→left),
   mirroring the manuscript page; marginalia & editorial side-notes live there. */
/* Text column is wide enough that a manuscript line fits without wrapping
   (≈99 % of lines ≤ 121 chars → ~64rem incl. the number gutter); the outer
   margin stays a fixed 15rem. Both hug the left so the margin sits near the text. */
.folio-2col{display:grid;gap:1.7rem;align-items:start;justify-content:start;
  grid-template-columns:minmax(0,64rem) 15rem}
.folio-2col.verso{grid-template-columns:15rem minmax(0,64rem)}
.folio-2col.verso .textcol{grid-column:2;grid-row:1}
.folio-2col.verso .margin-col{grid-column:1;grid-row:1}
.textcol{min-width:0}
.margin-col{min-width:0;font-family:system-ui,sans-serif}
.margin-col:empty{display:none}
.region{margin:0 0 .6rem}
/* notes in the outer margin — original scribal glosses (brown) vs editorial (green) */
.m-note{font-size:.76rem;line-height:1.5;border-radius:4px;padding:.45rem .62rem;margin:0 0 .7rem}
.m-note .mlabel{display:block;font-size:.6rem;letter-spacing:.05em;text-transform:uppercase;
  margin-bottom:.22rem}
.m-note p{margin:.25rem 0 0}
.m-note p:first-of-type{margin-top:0}
.m-orig{background:#f5efe0;border:1px solid #d8ccae;color:#5a5046}
.m-orig .mlabel{color:#9a8d70}
.m-orig.later{border-left:3px solid #5a6b8c}
.m-ed{background:#eaf3ec;border:1px solid #bcd9c2;border-left:3px solid #2f6b3a;color:#39573f}
.m-ed .mlabel{color:#2f6b3a}
/* fallback for raw-region marginalia on non-clean folios */
.region.marginalia{font-family:system-ui,sans-serif;font-size:.8rem;color:#5a5046;background:#f5efe0;
  border:1px solid #d8ccae;border-radius:4px;padding:.45rem .65rem;margin:.4rem 0}
@media(max-width:760px){
  .folio-2col,.folio-2col.verso{grid-template-columns:1fr}
  .folio-2col.verso .textcol,.folio-2col.verso .margin-col{grid-column:1;grid-row:auto}
}
/* --- lineated transcription with margin line numbers (citable) --- */
.lines{position:relative}
.ln{display:block;position:relative;padding-left:2.4rem;line-height:1.75}
.lno{position:absolute;left:0;width:1.9rem;text-align:right;top:.15em;
  font-family:system-ui,sans-serif;font-size:.66rem;color:#b6a982;user-select:none;
  text-decoration:none;cursor:pointer;opacity:0;transition:opacity .12s}
.lno.show{opacity:.85}
.ln:hover .lno{opacity:.85}
a.lno:hover{color:var(--accent);text-decoration:underline}
.ln:target{background:#fbf1cf;border-radius:2px;box-shadow:0 0 0 3px #fbf1cf}
.ln.flash{animation:lnflash 1.1s ease-out}
@keyframes lnflash{0%{background:#f4dd8a}100%{background:transparent}}
.pbreak{display:block;height:.7rem}
/* čtecí (continuous) sazba: join lines into justified prose at a comfortable
   measure (the wide no-wrap column is for the lineated „řádky" view only) */
body.layout-flow .lines{text-align:justify;line-height:1.8;hyphens:auto;max-width:46rem}
body.layout-flow .ln{display:inline;padding-left:0;padding-right:0}
body.layout-flow .ln::after{content:" "}
body.layout-flow .lno{display:none}
body.layout-flow .ln:target{box-shadow:none}
body.layout-flow .pbreak{display:block;height:0;margin-bottom:.85rem}
/* editorial-apparatus marks ([?], expansions); hidden by the „ediční značky" toggle */
.ed{color:#2f6b3a}
body.app-off .ed{display:none}
.ed-note{margin:.9rem 0 .2rem;font-family:system-ui,sans-serif;font-size:.82rem;
  line-height:1.55;background:#eaf3ec;border-left:3px solid #2f6b3a;border-radius:3px;
  padding:.1rem .7rem;color:#39573f}
.ed-note summary{cursor:pointer;font-weight:600;color:#2f6b3a;padding:.35rem 0}
.ed-note p{margin:.4rem 0}
body.app-off .ed-note,body.app-off .clean-flag{display:none}
.heading{font-size:1.05rem;font-weight:bold}
.table-todo{font-family:system-ui,sans-serif;font-size:.85rem;color:#6b6256;background:#f6f1e4;
  border:1px dashed #cdbf9f;border-radius:4px;padding:.7rem .9rem}
.table-todo a{color:#7a5c2e}
/* editorial table caption (not original text) → green, like the side ed-notes */
.table-cap{font-family:system-ui,sans-serif;font-size:.85rem;margin:.2rem 0 .6rem;
  color:#2f6b3a;font-weight:600}
.table-note{font-family:system-ui,sans-serif;font-size:.82rem;color:#39573f;margin:.45rem 0}
.table-note.verified{color:#2f6b3a}
.ms-heading{margin:.3rem 0 .7rem;line-height:1.55}
.ms-prose{margin:1rem 0;padding:.6rem .8rem;background:#f7f3ea;border-left:3px solid #c9b88a;
  line-height:1.6}
.ms-prose-label{display:block;font-family:system-ui,sans-serif;font-size:.72rem;
  text-transform:uppercase;letter-spacing:.04em;color:#8a7d63;margin-bottom:.3rem}
.ms-prose p{margin:.45rem 0}
.ms-prose-ed{font-size:.86rem;color:#39573f}
.zod{font-variant-emoji:text;font-family:"Segoe UI Symbol","Noto Sans Symbols2","DejaVu Sans",
  "Apple Symbols",serif;color:#5a4a2a}
.ms-heading-label{display:block;font-family:system-ui,sans-serif;font-size:.72rem;
  text-transform:uppercase;letter-spacing:.04em;color:#8a7d63;margin-bottom:.25rem}
.method-note{margin:.7rem 0;font-family:system-ui,sans-serif;font-size:.82rem;line-height:1.5;
  background:#eaf3ec;border-left:3px solid #2f6b3a;border-radius:3px;padding:.2rem .7rem}
.method-note summary{cursor:pointer;font-weight:600;color:#2f6b3a;padding:.35rem 0}
.method-note p{margin:.45rem 0}
.method-note code{font-size:.82em;background:#dce8df;padding:0 .2em;border-radius:2px}
.page-table{border-collapse:collapse;margin:.6rem 0;font-family:system-ui,sans-serif;font-size:.85rem}
.page-table td{border:1px solid #cdbf9f;padding:.15rem .4rem;text-align:center;min-width:1.6rem}
.fig-svg{margin:1rem 0;text-align:center}
.fig-svg svg{max-width:240px;height:auto;background:#fffdf8;border:1px solid #e6ddc7;border-radius:4px;padding:.4rem}
.fig-svg figcaption{font-family:system-ui,sans-serif;font-size:.78rem;color:#8a7d63;margin-top:.35rem}
.clean-flag{display:inline-block;background:#3f6b3f;color:#fff;font-family:system-ui,sans-serif;
  font-size:.65rem;border-radius:3px;padding:0 .35rem;margin-bottom:.4rem}
.fig{margin:0 0 1rem;text-align:center}
.fig img{max-width:100%;height:auto;border:1px solid #cdbf9f;border-radius:3px}
.fig figcaption{font-family:system-ui,sans-serif;font-size:.75rem;color:#6b6256;margin-top:.3rem}
.fig figcaption a{color:#7a5c2e}
.scan-embed{max-width:62rem;margin:1.5rem auto;font-family:system-ui,sans-serif;font-size:.8rem}
.scan-embed summary{cursor:pointer;color:#7a5c2e;padding:.4rem .6rem;background:#f3ecdb;
  border:1px solid #cdbf9f;border-radius:4px;user-select:none}
.scan-embed iframe{width:100%;height:80vh;margin-top:.6rem;border:1px solid #cdbf9f;border-radius:3px}
.scan-embed .scan-note{color:#6b6256;font-size:.72rem;margin:.4rem 0 0}
.empty{color:#a99;font-style:italic;font-family:system-ui,sans-serif;padding:1rem}
/* mode switching */
.norm{display:none}
body.mode-norm .dipl{display:none}
body.mode-norm .norm{display:inline}
.teige-pane{display:none}
body.mode-teige .teige-pane{display:block;margin-top:1rem;background:#fff;border:1px solid #cdbf9f;
  border-radius:4px;padding:1rem 1.4rem}
.teige-label{font-family:system-ui,sans-serif;font-size:.75rem;color:#6b6256;margin-bottom:.4rem;
  text-transform:uppercase;letter-spacing:.05em}
.teige-text{line-height:1.6;color:#444}
.teige-text .hit{background:#eef3d8}
.teige-empty{color:#a99;font-style:italic}
.section-label{max-width:min(97vw,86rem);margin:.3rem auto 0;padding:0 1rem;font-family:system-ui,sans-serif;
  font-size:.78rem;color:#7a5c2e;text-transform:uppercase;letter-spacing:.04em}
.tiraz{font-family:system-ui,sans-serif;font-size:.85rem;line-height:1.5;background:#f6f1e4;
  border:1px solid #cdbf9f;border-radius:5px;padding:.8rem 1.1rem;margin:0 0 1.4rem}
.tiraz h2{font-size:1rem;margin:.1rem 0 .5rem;border:0}
.tiraz p{margin:.4rem 0}
.tiraz .warn{background:#fbeed6;border-left:3px solid #b8860b;padding:.4rem .6rem;border-radius:3px}
.tiraz .teige{background:#eef1f6;border-left:3px solid #5a6b8c;padding:.4rem .6rem;border-radius:3px}
.tiraz .verify{background:#eaf3ec;border-left:3px solid #2f6b3a;padding:.4rem .6rem;border-radius:3px}
.tiraz .verify code{font-size:.82em;background:#dce8df;padding:0 .2em;border-radius:2px}
.tiraz a{color:#7a5c2e}
.uvod{font-family:Georgia,'Times New Roman',serif;font-size:.98rem;line-height:1.62;
  background:var(--paper);border:1px solid #cdbf9f;border-radius:5px;padding:1.1rem 1.4rem;margin:0 0 1.4rem}
.uvod h2{font-size:1.3rem;margin:.1rem 0 .3rem;border:0}
.uvod h2+.lead{margin-top:0;color:#6b6256;font-style:italic}
.uvod h3{font-size:1.02rem;margin:1.1rem 0 .3rem;color:#5a4a2e}
.uvod p{margin:.5rem 0}
.uvod ul{margin:.4rem 0;padding-left:1.2rem}
.uvod li{margin:.35rem 0}
.uvod a{color:#7a5c2e}
.uvod code{font-size:.86em;background:#efe7d4;padding:0 .25em;border-radius:2px}
.uvod .more{font-size:.86rem;color:#6b6256;margin-top:1rem}
.status{font-family:system-ui,sans-serif;font-size:.82rem;border-collapse:collapse;width:100%;margin:0 0 1.4rem}
.status caption{text-align:left;font-weight:bold;font-size:1rem;margin-bottom:.4rem;color:#3a342a}
.status th,.status td{border:1px solid #cdbf9f;padding:.3rem .55rem;text-align:left;vertical-align:top}
.status th{background:#efe7d3}
.status tbody tr:nth-child(even){background:#faf6ec}
.status tbody tr[data-href]{cursor:pointer}
.status tbody tr[data-href]:hover{background:#f0e6c8}
.status td a{color:#7a5c2e;text-decoration:none;font-weight:600}
.status td a:hover{text-decoration:underline}
.status td.hand{white-space:nowrap;color:#5a5046;font-size:.8rem;font-variant-numeric:tabular-nums}
.marg-link{font-family:system-ui,sans-serif;font-size:.9rem;margin:.6rem 0 1.2rem;
  padding:.5rem .7rem;background:#f0e6c8;border-left:3px solid #b8860b;border-radius:3px}
.marg-link a{color:#7a5c2e;font-weight:700}
.marg-item{margin:1.1rem 0;padding-top:.6rem;border-top:1px solid #e2d7bb}
.marg-item h3{font-family:system-ui,sans-serif;font-size:.95rem;margin:.2rem 0 .5rem;color:#3a342a}
.marg-item h3 a{font-size:.8rem;font-weight:normal;color:#7a5c2e}
.marg-ctx,.mctx{color:#6b6256;font-weight:normal}
.marg-row{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-start}
.marg-figs{flex:0 0 210px;display:flex;flex-direction:column;gap:5px}
.marg-figs img{max-width:210px;border:1px solid #d8cba8;background:#fff;border-radius:2px;opacity:.95}
.marg-body{flex:1 1 360px}
.marg-notes{margin:0 0 .5rem;padding-left:1.2rem;font-size:.95rem;line-height:1.65}
.marg-notes li{margin:.2rem 0}
.marg-add{font-size:.95rem;line-height:1.6;margin:.5rem 0;padding:.5rem .7rem;
  background:#f3ece0;border-left:3px solid #9c6b3a;border-radius:3px}
.t-ADD{background:#e6d3bf;color:#7a3b1e}
.mtag{display:inline-block;font-family:system-ui,sans-serif;font-size:.68rem;
  text-transform:uppercase;letter-spacing:.03em;padding:.05rem .35rem;border-radius:3px;
  margin-right:.35rem;vertical-align:.08em}
.t-IDX{background:#e7eecd;color:#4a5a1e}
.t-LAT{background:#dde6f0;color:#33506e}
.t-HIST{background:#f0dcd0;color:#7a3b1e}
.t-NB{background:#eee;color:#555}
.status .b-done{color:#2e7d32;font-weight:bold;white-space:nowrap}
.status .b-partial{color:#b8860b;font-weight:bold;white-space:nowrap}
.status .b-todo{color:#a3332b;font-weight:bold;white-space:nowrap}
.status .b-na{color:#999;white-space:nowrap}
.status-note{font-family:system-ui,sans-serif;font-size:.8rem;line-height:1.5;color:#6b6256;
  background:#f6f1e4;border-left:3px solid #b8860b;padding:.5rem .7rem;border-radius:3px;margin:-.8rem 0 1.4rem}
.toc-section h2{font-size:1rem;border-bottom:1px solid #cdbf9f;padding-bottom:.2rem;margin:1.4rem 0 .4rem}
.toc-section h2 .range{font-weight:normal;color:#8a8071;font-size:.85rem}
.note{font-family:system-ui,sans-serif;font-size:.85rem;color:#5a5446;background:var(--paper);
  border:1px solid #cdbf9f;border-radius:4px;padding:.6rem .9rem;max-width:62rem}
.teige-badge{display:inline-block;background:#7a5c2e;color:#fff;font-family:system-ui,sans-serif;
  font-size:.65rem;font-weight:bold;border-radius:3px;padding:0 .3rem;vertical-align:middle}
.toc{font-family:system-ui,sans-serif;font-size:.9rem;columns:2;gap:2rem;margin-top:1rem}
.toc li{margin:.15rem 0}
.toc .snip{color:#8a8071}
footer{max-width:62rem;margin:0 auto;text-align:center;color:#6b6256;font-size:.72rem;padding:1.5rem;
  font-family:system-ui,sans-serif}
#ed-toast{position:fixed;bottom:1.2rem;left:50%;transform:translateX(-50%) translateY(1rem);
  background:#2b2b2b;color:#f7f3ea;font-family:system-ui,sans-serif;font-size:.8rem;
  padding:.5rem .95rem;border-radius:6px;opacity:0;pointer-events:none;z-index:20;
  transition:opacity .18s,transform .18s;box-shadow:0 2px 10px rgba(0,0,0,.25)}
#ed-toast.show{opacity:.97;transform:translateX(-50%) translateY(0)}
"""

_JS = """
(function(){
  const B=document.body;
  function store(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  function load(k){try{return localStorage.getItem(k)}catch(e){return null}}
  function setMode(m){
    B.classList.remove('mode-dipl','mode-norm','mode-teige');B.classList.add('mode-'+m);
    for(const r of document.querySelectorAll('input[name=mode]'))r.checked=(r.value===m);
    store('edmode',m);}
  function setLayout(l){
    B.classList.remove('layout-lined','layout-flow');B.classList.add('layout-'+l);
    for(const r of document.querySelectorAll('input[name=layout]'))r.checked=(r.value===l);
    store('edlayout',l);}
  function setApp(on){
    B.classList.toggle('app-off',!on);
    const c=document.getElementById('appToggle');if(c)c.checked=on;
    store('edapp',on?'1':'0');}
  document.addEventListener('DOMContentLoaded',function(){
    const sm=load('edmode');if(sm)setMode(sm);
    const sl=load('edlayout');if(sl)setLayout(sl);
    const sa=load('edapp');if(sa!==null)setApp(sa==='1');
    for(const r of document.querySelectorAll('input[name=mode]'))r.addEventListener('change',()=>setMode(r.value));
    for(const r of document.querySelectorAll('input[name=layout]'))r.addEventListener('change',()=>setLayout(r.value));
    const c=document.getElementById('appToggle');if(c)c.addEventListener('change',()=>setApp(c.checked));
    let tt;
    function toast(msg){
      let el=document.getElementById('ed-toast');
      if(!el){el=document.createElement('div');el.id='ed-toast';document.body.appendChild(el);}
      el.textContent=msg;el.classList.add('show');
      clearTimeout(tt);tt=setTimeout(()=>el.classList.remove('show'),1900);}
    document.addEventListener('click',function(e){
      const a=e.target.closest('a.lno');if(!a)return;
      e.preventDefault();
      const id=a.getAttribute('href').slice(1);
      const wrap=a.closest('.lines');const fol=wrap?wrap.getAttribute('data-folio'):'';
      const ref='fol. '+fol+', ř. '+a.getAttribute('data-n');
      const url=location.href.split('#')[0]+'#'+id;
      try{history.replaceState(null,'','#'+id)}catch(_){location.hash=id;}
      const t=document.getElementById(id);
      if(t){t.classList.remove('flash');void t.offsetWidth;t.classList.add('flash');}
      const cite=ref+' — '+url;
      if(navigator.clipboard&&navigator.clipboard.writeText){
        navigator.clipboard.writeText(cite).then(()=>toast('Zkopírováno: '+ref)).catch(()=>toast(ref));
      }else toast(ref);
    });
    document.addEventListener('keydown',function(e){
      if(e.target.tagName==='INPUT')return;
      if(e.key==='ArrowLeft'){const a=document.querySelector('.pager .prev');if(a&&!a.hidden)location.href=a.getAttribute('href');}
      if(e.key==='ArrowRight'){const a=document.querySelector('.pager .next');if(a&&!a.hidden)location.href=a.getAttribute('href');}
    });
  });
})();
"""


# AHMP (Bach pragapublica) link policy. AHMP has NO stable per-scan URL:
#  - ``permalink?xid=<XID>`` is the canonical, persistent link, but resolves to the
#    document (scanIndex is ignored server-side — always the first scan);
#  - the per-scan jump ``Zoomify.action…&scanIndex=N`` is a session-bound *action* URL
#    that returns „Platnost stránky vypršela" when opened cold → not a stable citation.
# We therefore link the stable permalink and carry the folio (= scan N) in the link text;
# the reader opens scan N in the viewer. Scans are not republished here.
_AHMP_PERMALINK = "https://katalog.ahmp.cz/pragapublica/permalink"


def _ahmp_xid(permalink: str | None) -> str | None:
    if not permalink or "xid=" not in permalink:
        return None
    return permalink.split("xid=", 1)[1].split("&", 1)[0]


def _folio_ahmp_url(permalink: str | None, page_nr: int) -> str | None:
    """Stable AHMP link for a folio = the canonical document permalink.

    AHMP exposes no stable per-scan URL, so we return the persistent
    ``permalink?xid=<XID>``; the target folio (scan number) is conveyed in the
    link text instead. Scans are not republished — this only links out to AHMP.
    """
    xid = _ahmp_xid(permalink)
    if not xid:
        return None
    return f"{_AHMP_PERMALINK}?xid={xid}"


def build_edition(
    work_dir: Path, *, title: str, ahmp_permalink: str | None = None,
    teige_path: Path | None = None, embed_scan: bool = False,
) -> Path:
    work_dir = Path(work_dir)
    work_slug = work_dir.name
    binding_notes = _BINDING_NOTE_1570 if "1570" in work_slug else {}
    xml_files = sorted((work_dir / "page_xml").glob("*.xml"))
    if not xml_files:
        raise RuntimeError(f"No PAGE XML in {work_dir / 'page_xml'}; run HTR/export first.")

    if ahmp_permalink is None:
        state = work_dir / "state.json"
        if state.exists():
            ref = json.loads(state.read_text(encoding="utf-8")).get("ref", "")
            if ref.startswith("http"):
                ahmp_permalink = ref

    teige_index: TeigeIndex | None = None
    if teige_path and Path(teige_path).exists():
        teige_index = TeigeIndex(Path(teige_path).read_text(encoding="utf-8"))

    out_dir = work_dir / "edition"
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    (out_dir / "assets" / "edition.css").write_text(_CSS, encoding="utf-8")
    (out_dir / "assets" / "edition.js").write_text(_JS, encoding="utf-8")

    total = len(xml_files)
    # Pass 1: parse pages, tables, and compute Teige matches.
    entries: list[
        tuple[int, list[TextRegion], list[Table], str, str | None, list[str], list[str], bool]
    ] = []
    tables_dir = work_dir / "tables"            # raw Docling — only flags a table page
    tables_clean_dir = work_dir / "tables_clean"  # verified, rendered as a grid
    figures_dir = work_dir / "figures"
    for xf in xml_files:
        page_nr = int(xf.stem)
        xml = xf.read_text(encoding="utf-8")
        regions = parse_page_xml(xml)
        # Only verified tables (tables_clean/) are rendered; raw Docling OCR of handwritten
        # table cells is unreliable, so it is NOT shown — it just marks a table page.
        tables: list[Table] = []
        clean_tbl = tables_clean_dir / f"{page_nr:04d}.json"
        if clean_tbl.exists():
            from transcribus.processing.docling_tables import tables_from_json

            tables = tables_from_json(clean_tbl.read_text(encoding="utf-8")) or []
        is_table_page = bool(tables) or (tables_dir / f"{page_nr:04d}.json").exists()
        fig_sidecar = figures_dir / f"{page_nr:04d}.json"
        fig_names = json.loads(fig_sidecar.read_text()) if fig_sidecar.exists() else []
        clean_file = work_dir / "clean" / f"{page_nr:04d}.txt"
        clean_lines = (
            [ln for ln in clean_file.read_text(encoding="utf-8").splitlines()]
            if clean_file.exists() else []
        )
        plain = " ".join(line for r in regions for line in r.lines if line.strip())
        passage = teige_index.align(plain) if (teige_index and plain) else None
        entries.append(
            (page_nr, regions, tables, plain, passage, fig_names, clean_lines, is_table_page)
        )

    matched = {e[0] for e in entries if e[4]}
    sections = derive_sections(matched, total, work_slug=work_slug)
    folio_section = {n: label for _k, lo, hi, label in sections for n in range(lo, hi + 1)}

    # NOTE: no AHMP reproduction is republished (figures or whole pages) — each folio
    # only links out to the AHMP viewer. Embedding would require an AHMP agreement
    # (<=500px longer side + watermark + "internet" purpose stated in the contract).

    # Pass 2: write per-folio pages + index.
    toc: dict[int, tuple[str, bool]] = {}
    marg_items: list[dict] = []
    for page_nr, regions, tables, plain, passage, fig_names, clean_lines, is_tbl in entries:
        doc = _page_doc(
            title=title, page_nr=page_nr, total=total, regions=regions,
            ahmp_url=_folio_ahmp_url(ahmp_permalink, page_nr), teige_passage=passage,
            section_label=folio_section.get(page_nr, ""), tables=tables, figures=fig_names,
            clean_lines=clean_lines, embed_scan=embed_scan, table_page=is_tbl,
            binding_note=binding_notes.get(page_nr, ""),
        )
        (out_dir / f"p{page_nr:04d}.html").write_text(doc, encoding="utf-8")
        # _FOLIO_SNIP a _TABLE_CAPTIONS jsou specifické pro orlojní knihu 1587 —
        # pro originál 1570 je nepoužívej (popisky by neseděly na jeho folia).
        snip = None if "1570" in work_slug else _FOLIO_SNIP.get(page_nr)
        if not snip:
            if binding_notes.get(page_nr):
                snip = binding_notes[page_nr].strip("[]").split(" — ")[0]
            elif (tables or is_tbl) and "1570" not in work_slug:
                snip = _TABLE_CAPTIONS.get(page_nr, "[tabulka]")
            elif plain:
                snip = plain[:80] + "…"
            else:
                snip = "[vyobrazení]" if fig_names else "[prázdná]"
        toc[page_nr] = (snip, passage is not None)
        _main, marg_lines = _split_marginalia(clean_lines)
        notes = _marg_notes(marg_lines)
        adds = _later_additions(clean_lines)
        if notes or adds:
            marg_items.append({
                "page": page_nr, "label": _FOLIO_SNIP.get(page_nr, ""),
                "notes": [(n, *_marg_category(n)) for n in notes],
                "adds": adds,
                "imgs": _marg_crops(work_dir, out_dir, page_nr) if notes else [],
            })

    if marg_items:
        (out_dir / "marginalia.html").write_text(
            _marginalia_doc(title, marg_items), encoding="utf-8"
        )

    index = out_dir / "index.html"
    index.write_text(
        _index_doc(
            title, sections, toc, ahmp_permalink,
            work_slug=work_slug, has_marginalia_page=bool(marg_items),
        ),
        encoding="utf-8",
    )
    return index
