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
from pathlib import Path

from transcribus.processing.normalize import normalize_text
from transcribus.processing.page_xml import Table, TextRegion, parse_page_xml
from transcribus.processing.teige import TeigeIndex, fold

_MARGINALIA = {"marginalia", "margin-text", "margin"}
_HEADING = {"heading", "header", "title", "caption"}

_SECTION_LABEL = {
    "taborsky": "Opis Táborského zprávy o orloji",
    "jine": "Další části knihy (bez referenční edice)",
}
_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def derive_sections(
    matched: set[int], total: int, *, gap: int = 2
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

    out: list[tuple[str, int, int, str]] = []
    for i, (kind, lo, hi) in enumerate(sections, start=1):
        label = f"Oddíl {_ROMAN[i] if i < len(_ROMAN) else i} — {_SECTION_LABEL[kind]}"
        out.append((kind, lo, hi, label))
    return out


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


# Folia, jejichž jazyk NENÍ čeština (latina, němčina) — česká normalizace by je zkomolila
# (g→j apod.), takže se u nich „normalizovaný" pohled rovná diplomatickému.
_NO_NORMALIZE: frozenset[int] = frozenset({4, 51, 52, 80})


def _line_html(line: str, *, normalize: bool = True) -> str:
    norm = normalize_text(line) if normalize else line
    return (
        '<span class="ln">'
        f'<span class="dipl">{_esc(line)}</span>'
        f'<span class="norm">{_esc(norm)}</span>'
        "</span>"
    )


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
    3: "Tabule dlúhosti dne i noci, vejchodu, poledne a západu Slunce (z celého i polovičního orloje) — kompaktní perpetuální tabule po krocích délky dne á 10 min (zima→léto). Dle záhlaví od Tadeáše Hájka z Hájku, pro výšku pólu 50° (Praha), nový kalendář (opis ≈ 1684); spojnice délka dne→datum ověřena geometrickým výpočtem pro Prahu.",
    50: "Tabula, ex qua Litera Dominicalis desumitur in ingressu cum Cyclo Solari („N. I”) — nedělní písmeno pro každý rok 28letého slunečního cyklu, juliánské i gregoriánské.",
    55: "Tabule vejchodu Slunce wedle polovičního orloje — čas východu pro každý den (1–31) a měsíc (h:min).",
    56: "Tabula, ex qua Litera Dominicalis desumitur („N. I”) — duplikát tabule z fol. 50 (nedělní písmeno, juliánské i gregoriánské).",
    57: "Tabula Epactarum („N. 2”) — epakta pro každý zlatý počet (1–19), juliánská a gregoriánská (období ad 1700 / 1700–1900 / 1900–2200).",
    58: "Tabula Festorum Mobilium Calendarii [novi] — pohyblivé svátky (Septuagesima, Popeleční středa, Velikonoce, Rogationes, Nanebevstoupení, Letnice, Boží tělo, Advent).",
    59: "Tabula Festorum Mobilium (pokrač.) — pohyblivé svátky.",
    60: "Tabula Intervalli [Paschae] in Calendario Juliano — datum velikonočního úplňku/Velikonoc podle zlatého počtu (1–19) a nedělního písmene (A–G).",
    61: "Tabula Intervalli [Paschae] in Calendario Gregoriano — gregoriánské dvojče f60: první číslo dvojice = týden gregoriánských Velikonoc, indexováno epaktou a nedělním písmenem (dole „Dies concurrentes“ 0–6). Dekódováno týmž klíčem jako f60, ověřeno principiálně.",
    62: "O slunečném cyklu (28letém), aneb jak najít nedělní písmeno pro každý rok.",
    63: "Výpočet v obojím — starém i novém — kalendáři (pokrač.).",
    64: "O zlatém počtu — cyklus decennovenalis (19letý lunární), měsíčný cyklus.",
    65: "Ukazatel nového měsíce — návodná próza (česky) k výpočtu novoluní.",
    66: "Tabule k nalezení epakt / novoluní po dnech roku — hustá číselná tabulka (měsíce v záhlaví).",
    67: "Komputus na prstech — výpočet, který měsíc má 31/30/29 dní (Ex Gustavi Selen Cryptographia, fol. 487).",
    68: "Nalezení nového a plného měsíce pro každý měsíc — výpočet z epakt.",
    69: "Malá násobilka (pythagorejská tabule) — trojúhelníková, součiny 2×2 až 10×10.",
}


# Deterministic verification (external computation / astronomy). See tools/verify_computus.py.
_TABLE_VERIFY: dict[int, str] = {
    3: "✓ věrný přepis ze skenu včetně záhlaví. Sloupce nesou <b>rukopisné nadpisy</b>: „Dnové "
        "měsíců“ (den), „Svátkové Posle kalendáře“ (svátek), „Dlúhost dne“, „Slunce celého "
        "orloje“ a „Slunce na díl orloje“ (východ Slunce v českých /orlojních/ a v obecných "
        "hodinách), „Poledne celého orloje“, „Západ celého orloje“ — vlevo pro jarní, vpravo pro "
        "podzimní polovinu roku (táž délka dne nastává dvakrát). V buňkách je <b>jen přepis</b> "
        "(jména svatých a zápis „Slunce na [znamení]“); ediční výklad — názvy znamení, "
        "slunovraty/rovnodennosti, vysvětlení českých hodin — je oddělen v poznámce pod tabulkou. "
        "Jména ověřena proti kalendáři (Anežka 21. 1., Benedikt 21. 3., Vojtěch 23. 4., Žikmund "
        "2. 5., Václav 28. 9., Diviš 9. 10. …); <b>[?]</b> = nejisté čtení, jež se s žádným svatým "
        "k danému dni neshoduje. Časové sloupce souhlasí s přepočtem do minuty (rovnodennost: "
        "dlúhost dne 12:00, východ obecný 6:00, poledne české 18:00; ověřeno ve verify_computus).",
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
}

# Delší metodické poznámky pod vybranými tabulkami (rozbalovací <details>).
# Nadpis rozbalovací poznámky (default je obecný).
_TABLE_NOTE_SUMMARY: dict[int, str] = {
    55: "Metodická poznámka: jak časy vznikly (výpočet vs. pozorování, refrakce, drift)",
    60: "Jak tabule funguje a jak je ověřena (dekódování)",
    61: "Jak tabule funguje a jak je ověřena (gregoriánské dvojče f60)",
    3: "Záhlaví tabule, původ (Tadeáš Hájek z Hájku), struktura a ověření",
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
        "<p><b>Záhlaví tabule (přepis).</b> „<i>Tabule dlúhosti dne i noci, vejchodu, poledne "
        "i západu, obojího — celého i polovičného [orloje] — kterak ten srovnán býti má podle "
        "spravování orloje a jeho hodin, a to přes celý rok položená, [pro českou(?)] zemi a "
        "k vyvýšení Polum L [= 50] graduů, od někdy D. Tadeáše Hájka z Hájku před LXVI [= 66] "
        "lety vydaná, a nyní dle nového kalendáře spravena. Léta M.DC.LXXXIV [≈ 1684].</i>“ "
        "(Jednotlivá slova úvodu a čtení letopočtu jsou ke kontrole na originále.)</p>"
        "<p><b>Tady rukopis sám jmenuje původ tabulky.</b> Tabule délky dne / východu / "
        "poledne / západu Slunce je <b>od „někdy“ (tj. nebožtíka) Dr. Tadeáše Hájka z Hájku</b> "
        "(<i>Thaddaeus Hagecius ab Hayek</i>, ~1525–1600, přední pražský astronom, lékař "
        "Rudolfa II. a Tychonův korespondent), spočtená pro <b>výšku pólu 50°</b> (Praha) a "
        "<b>upravená na nový (gregoriánský) kalendář</b>. Tato atribuce platí <b>doloženě "
        "pro tuto tabuli (fol. 3)</b>. Pěkně se shoduje s <b>nezávislým otiskem, který jsme "
        "změřili u fol. 55</b> (geometrický východ, výška pólu ~50°, nový kalendář): orlojní "
        "sluneční tabule jsou <b>pražského, Hájkova typu</b>, ne dovezené cizí efemeridy. "
        "Pozor však: fol. 55 je z <b>jiné, starší vrstvy (~1641)</b> než tento opis (~1684), "
        "takže pro fol. 55 jde o <b>slučitelnost a důvodný předpoklad</b>, ne o tutéž doloženou "
        "atribuci.</p>"
        "<p><b>Datace a otevřená otázka chronologie.</b> Záhlaví klade vznik <b>po Hájkově "
        "smrti (1600)</b>: označení „<i>od někdy</i>“ před jménem znamená „nebožtík“ (lat. "
        "<i>quondam</i>), a „dle <i>nového</i> kalendáře“ pak po r. 1584. Letopočet se čte jako "
        "„<i>M·DC·LXXXIV</i>“, tj. <b>≈ 1684</b> (čtení k ověření na originále). To je v "
        "<b>napětí s předpokladem, že zápisy v orlojní knize jdou striktně chronologicky</b> "
        "(f3 je přední list, fyzicky před Táborského opisem 1587). Nejpravděpodobnější smíření: "
        "přední listy (fol. 2–3) jsou <b>referenční tabule dopsané na volné přední listy "
        "později</b> než hlavní sekvence — běžný jev, který chronologii hlavního korpusu "
        "neruší. Rozhodující ověření (čeká na ohledání originálu): zda je <b>ruka a inkoust "
        "fol. 3 odlišná</b> od datovaných vrstev (Táborský 1587, komputus ~1641). Původní "
        "Hájkův výpočet tak jako tak spadá do konce 16. století.</p>"
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
        "v rukopise. Vše ostatní je ediční výklad a patří sem, ne do tabulky: <b>[?]</b> = nejisté "
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
        "z pozdější vrstvy ~1684) — má v záhlaví <b>výslovnou atribuci „od někdy D. Tadeáše "
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
    """Render the marginalia as a side note on the codicologically correct margin.

    verso (even folio) → left margin, recto (odd) → right margin. Later-hand keepers'
    notes (``[Pozdější rukou …]``) keep their editorial markers and get a distinct style.
    """
    if not marg_lines:
        return ""
    text = " ".join(ln.strip() for ln in marg_lines).strip()
    if "okraji:]" in text:
        text = text.split("okraji:]", 1)[1].strip()
    side = "side-left" if page_nr % 2 == 0 else "side-right"
    later = " ".join(marg_lines)
    cls = "marginalia later-present" if ("Pozdější ruk" in later or "pozdější ruk" in later) else "marginalia"
    return (
        f'<aside class="{cls} {side}">'
        '<span class="mlabel">Přípisky na okraji</span>'
        f"<p>{_esc(text)}</p></aside>"
    )


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
    table_page: bool = False,
) -> str:
    tables = tables or []
    figures = figures or []
    has_text = any(r.lines and any(line.strip() for line in r.lines) for r in regions)
    has_content = has_text or bool(tables) or bool(figures) or bool(clean_lines) or table_page
    # AHMP rules: any internet publication of a reproduction needs an agreement +
    # <=500px + watermark. Until that is in place, NOTHING is republished — figures are
    # only referenced with an out-link to the AHMP viewer.
    fig_link = (
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">sken v AHMP</a>'
        if ahmp_url else "sken v AHMP"
    )
    fig_note = (
        f'<figure class="fig fig-ref"><figcaption>Na tomto foliu je vyobrazení '
        f"(zde nereprodukováno — viz {fig_link}).</figcaption></figure>"
        if figures else ""
    )
    prev_link = f"p{page_nr-1:04d}.html" if page_nr > 1 else ""
    next_link = f"p{page_nr+1:04d}.html" if page_nr < total else ""
    ahmp = (
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">↗ sken v AHMP</a>'
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
    if has_content:
        # Precedence: corrected clean text > Docling table grid > raw per-line HTR.
        if clean_lines:
            main_lines, marg_lines = _split_marginalia(clean_lines)
            do_norm = page_nr not in _NO_NORMALIZE
            body_regions = (
                '<span class="clean-flag">opravený přepis</span><p class="region paragraph">'
                + "\n".join(_line_html(line, normalize=do_norm) for line in main_lines if line)
                + "</p>"
            )
            marginalia = _marginalia_html(marg_lines, page_nr)
        elif tables:
            cap = _TABLE_CAPTIONS.get(page_nr)
            note = _TABLE_VERIFY.get(
                page_nr, "přepis z rukopisu; číselné hodnoty ke kontrole proti skenu."
            )
            vcls = "table-note verified" if note.startswith("✓") else "table-note"
            head = (
                f'<p class="table-cap"><b>{_esc(cap)}</b> '
                f'<span class="{vcls}">— {_esc(note)}</span></p>'
                if cap else ""
            )
            body_regions = head + "".join(_table_html(t) for t in tables)
            long_note = _TABLE_NOTE_LONG.get(page_nr)
            if long_note:
                summ = _TABLE_NOTE_SUMMARY.get(page_nr, "Metodická poznámka — rozbor a ověření")
                body_regions += (
                    f'<details class="method-note"><summary>{_esc(summ)}</summary>'
                    f"{long_note}</details>"
                )
        elif table_page:
            link = (
                f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">sken v AHMP</a>'
                if ahmp_url else "sken v AHMP"
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
            body_regions = "\n".join(_region_html(r) for r in regions)
        body_regions += _FIGURE_SVG.get(page_nr, "")
        page_folded = {
            fold(w) for r in regions for line in r.lines for w in line.split() if len(fold(w)) >= 4
        }
        teige = _teige_html(teige_passage, page_folded)
        body = (
            f'<div class="folio">{marginalia}{fig_note}{body_regions}</div>'
            f'<div class="teige-pane"><div class="teige-label">Teige (1570), přibližné zarovnání</div>{teige}</div>'
        )
    else:
        body = '<div class="empty">[prázdná strana / vazba]</div>'

    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fol. {page_nr:04d} — {_esc(title)}</title>
<link rel="stylesheet" href="assets/edition.css"></head>
<body class="mode-dipl">
<header>
  <a class="home" href="index.html">≡</a>
  <h1>{_esc(title)}</h1>
  <div class="modes">
    <label><input type="radio" name="mode" value="dipl" checked> Diplomatický</label>
    <label><input type="radio" name="mode" value="norm"> Normalizovaný</label>
    <label><input type="radio" name="mode" value="teige"> Teige</label>
  </div>
</header>
<nav class="pager">
  <a class="prev" href="{prev_link}"{'' if prev_link else ' hidden'}>← předchozí</a>
  <span class="folno">fol. {page_nr:04d} / {total:04d} &nbsp; {ahmp}</span>
  <a class="next" href="{next_link}"{'' if next_link else ' hidden'}>další →</a>
</nav>
<div class="section-label">{_esc(section_label)}</div>
<main>{body}{scan_embed}</main>
<footer>Diplomatický přepis (Transkribus HTR, model 263129). Normalizace heuristická — nutná korektura.
Teige: edice 1901, public domain. Vyobrazení ani skeny se zde nereprodukují — odkazy „sken"
vedou do prohlížeče Archivu hlavního města Prahy (katalog.ahmp.cz).</footer>
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
_STATUS_ROWS: list[tuple[str, str, str, str]] = [
    ("f1", "předsádka", "na", "—"),
    ("f2–f3", "úvodní astron. tabulky — Hájek z Hájku (přední list, opis ≈ 1684)", "partial",
     "f2 nevyplněná předtištěná tabule; f3 = symetrická perpetuální tabule po krocích délky dne "
     "(Tadeáš Hájek z Hájku, pól 50°, nový kalendář) — přepsána věrně a kompletně: jarní i "
     "podzimní blok (měsíc, den, svátek, vstupy Slunce) čteny ze skenu, časy (délka dne/noci, "
     "východ, české poledne, díl) ověřeny výpočtem; jen několik méně zřetelných jmen [?]"),
    ("f4", "latinský epigram (sedm pahorků pražských)", "done",
     "přepsáno + překlad; „Praha jako nový Řím“, bez podpisu"),
    ("f5–f12", "Táborský: verš, dedikace, kap. I–VI", "done", "drobná [?] místa"),
    ("f13–f30", "Táborský: kap. VI–XIII", "done", "marginálie ověřeny ze skenu (f13 nejisté)"),
    ("f31–f42", "Táborský: kap. XIII–XVIII", "partial",
     "Teige-ukotveno; diplomatická kontrola po řádcích"),
    ("f43–f49", "Táborský: biografický závěr, verše, kolofony 1570 + 1587", "done", "—"),
    ("f50", "Tabula Litera dominicalis (N. I)", "done",
     "cyklus solaris → nedělní písmeno (jul./greg.), 28 řádků, ověřeno vzorcem"),
    ("f51–f52", "List purkmistra 1410 (něm., opsáno 1628)", "done", "—"),
    ("f53–f54", "List purkmistra — dobový český překlad", "partial",
     "český překlad hotov; německý návod na f54 (přepočet německé↔orlojní hodiny) — český souhrn "
     "doplněn, strojový DE základ (PyLaia) mimo edici, plný diplomatický DE přepis čeká na Titan"),
    ("f55–f69", "komputistické/astron. tabulky + próza (sekce ~1641)", "partial",
     "ověřeno výpočtem: f55 (vejchod, astron.), f57 (epakty, Meeus), f50/f56 (litera), "
     "f60 (intervallum jul. — dekódováno: týden Velikonoc, 133/133), f69 (násobilka) + "
     "prózy f62–65, 67, 68; f61 (intervallum greg.) dekódováno (dvojče f60, 191/210, zóna epakty "
     "25/XXV k dořešení); zbývají husté mřížky f58/59 (festa mob.) a f66 (epakty po dnech)"),
    ("f70–f79", "Astrolabium parvum", "done", "—"),
    ("f80", "dva latinské epigramy (Pythagoras, Archimedes) + nákres trojúhelníku", "done",
     "přepsáno + překlad (hekatomba; „pohnu zemí“)"),
    ("f81", "předsádka", "na", "—"),
]
_STATUS_BADGE = {
    "done": '<span class="b-done">✅ hotovo</span>',
    "partial": '<span class="b-partial">🔶 rozpracováno</span>',
    "todo": '<span class="b-todo">❌ chybí</span>',
    "na": '<span class="b-na">— prázdná</span>',
}


def _status_html() -> str:
    rows = "".join(
        f"<tr><td>{_esc(fol)}</td><td>{_esc(part)}</td>"
        f"<td>{_STATUS_BADGE.get(st, _esc(st))}</td><td>{_esc(rest)}</td></tr>"
        for fol, part, st, rest in _STATUS_ROWS
    )
    return (
        '<table class="status"><caption>Stav zpracování (průběžně aktualizováno)</caption>'
        "<thead><tr><th>folia</th><th>část knihy</th><th>stav</th><th>zbývá</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        '<p class="status-note"><b>Co v knize ještě chybí:</b> f31–42 (diplomatická kontrola '
        "Táborského po řádcích), f54 (plný německý návod), f58/59 (Tabula festorum mobilium) a "
        "f66 (epakty po dnech) — husté rukopisné číselné mřížky k přepisu tabulkovým HTR. (f3 je "
        "přepsáno věrně a kompletně včetně jarních i podzimních svátků a měsíců.) "
        "Prázdné/předsádky: f1, f2, f81.</p>"
    )


def _index_doc(
    title: str,
    sections: list[tuple[str, int, int, str]],
    pages: dict[int, tuple[str, bool]],
    ahmp_permalink: str | None = None,
) -> str:
    ahmp_a = (
        f'<a href="{_esc(ahmp_permalink)}" target="_blank" rel="noopener">'
        "záznam a skeny v katalogu AHMP ↗</a>"
        if ahmp_permalink else "katalog AHMP"
    )
    tiraz = (
        '<section class="tiraz"><h2>O edici</h2>'
        "<p><b>Pramen — jedna svázaná orlojní kniha (zápisy z let ~1587–1684).</b> Archiv "
        f"hlavního města Prahy, Sbírka rukopisů, inv. č. 7916. {ahmp_a}. Nejde o soubor volně "
        "vložených listů: ohledáním archiválie bylo ověřeno, že je to <b>jediný svázaný celek</b> "
        "a že zápisy vznikaly postupně na <b>předem svázané archy</b> — pořadí zápisů v hlavním "
        "korpusu tedy odpovídá chronologii. <b>Jedna výjimka</b>: referenční sluneční tabule na "
        "ponechaných <b>volných předních listech (fol. 2–3) byly dopsány nejpozději</b> (dle "
        "vlastního letopočtu ≈ 1684) — fyzicky jsou první, ale časově poslední, takže pořadí "
        "folií tu chronologii neodráží a <b>protahují celkový rozsah psaní knihy zhruba na "
        "století</b>. Díky chronologii hlavního korpusu jsou <b>datovatelné i pozdější přípisky "
        "správců orloje</b>; právě "
        "na nich stojí přeřazení vzniku orloje k r. 1410 (Z. Horský). Kniha má několik částí: "
        "(1) <b>opis Táborského <i>Zprávy o orloji pražském</i></b> (fol. 5–49), který roku "
        "1587 pořídil staroměstský písař <b>Matouš Carchesius Jablonský</b> (kolofon fol. 47); "
        "(2) <b>opis Listu purkmistra z r. 1410</b> (de facto smlouva Starého Města s hodinářem "
        "Mikulášem z Kadaně na zhotovení orloje) — německy (fol. 51–52, opsáno 1628) i v dobovém "
        "českém překladu (fol. 53–54); (3) "
        "<b>komputistické a astronomické tabulky</b> (fol. 2–3, 50, 55–69 — Littera dominicalis, "
        "zlaté číslo, epakta, východ slunce, polouorlojní počet); tabule délky dne / východu / "
        "západu (fol. 3) je dle <b>vlastního záhlaví</b> dílo <b>Tadeáše Hájka z Hájku</b> pro "
        "výšku pólu 50° (Praha), upravené na nový kalendář (opis ≈ 1684); (4) <b>Astrolabium "
        "parvum</b> "
        "(fol. 70–79); a (5) <b>pozdější přípisky správců orloje</b> (16.–17. stol.). Edice "
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
        "opisovače 1587, „přídavek na spheru“, poznámky správců odkazující na List purkmistra 1410). "
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
        "Naproti tomu <b>fol. 60</b> (<i>Tabula intervalli in Calendario Juliano</i>) se ověřit "
        "<b>zatím nepodařilo</b>: dvojčíslí v buňkách se nepodařilo dekódovat ani ztotožnit "
        "s vypočteným juliánským datem Velikonoc — proto je v edici označeno jako neověřené.</p>"
        '<p><b>Práva a licence:</b> skeny ani vyobrazení se zde nereprodukují — odkazy „sken" '
        "vedou do prohlížeče AHMP (práva k reprodukcím: Archiv hlavního města Prahy). "
        "Text edice © David Knespl, licence CC&nbsp;BY&nbsp;4.0; software EUPL-1.2.</p>"
        "<p><b>Použité zdroje a poděkování.</b> Pramen a skeny: <b>Archiv hlavního města "
        "Prahy</b>. Strojový přepis: <b>Transkribus</b> (READ-COOP), modely PyLaia 263129 a "
        "27457. Kolace: edice originálu 1570 <b>Josefa Teigeho</b> (1901, public domain). "
        "Přepis Astrolabia parvum (fol. 70–79) přejat z orloj.eu — přepis <b>Pavel Baudisch</b>, "
        "poznámky a model <b>Petr Král</b> a kol. (Český spolek horologický); za orlojnické "
        "konzultace patří dík <b>Petru Skálovi</b> (ČSH). Paleografický přepis německého Listu "
        "purkmistra (fol. 51–52) byl pořízen na zakázku (autorka k doplnění); dobový český "
        "překlad (fol. 53–54) poskytl D. Knespl. Norma transkripce: <b>Ivan Šťovíček a kol.</b> "
        "Datace a badatelství: <b>Zdeněk Horský</b> (1988); opis objevil <b>Stanislav "
        "Macháček</b> (1962). Rozpoznání tabulek: <b>Docling</b> (IBM).</p></section>"
    )
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
{_status_html()}
{tiraz}
<p class="note">Jedna svázaná kniha (více částí, jeden celek). <span class="teige-badge">T</span> = folia s opisem
Táborského zprávy, kde existuje referenční edice (Teige 1901); ostatní oddíly referenci nemají.
Označeno {n_teige} z {len(pages)} folií. Hranice oddílů jsou odvozené automaticky (heuristika).</p>
{"".join(blocks)}</main>
<footer>{len(pages)} folií. Diplomatická edice z Transkribus HTR.</footer>
</body></html>"""


_CSS = """
:root{--ink:#2b2b2b;--paper:#f7f3ea;--accent:#7a5c2e;}
*{box-sizing:border-box}
body{margin:0;font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:#e9e3d6}
header{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid #cdbf9f;
  padding:.5rem 1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
header h1{font-size:1rem;margin:0;flex:1 1 auto}
header .home{font-size:1.3rem;text-decoration:none;color:var(--accent)}
.modes label{margin-right:.7rem;cursor:pointer;font-family:system-ui,sans-serif;font-size:.82rem}
.pager{max-width:62rem;margin:.6rem auto 0;padding:0 1rem;display:flex;justify-content:space-between;
  align-items:center;font-family:system-ui,sans-serif;font-size:.85rem}
.pager a{color:var(--accent);text-decoration:none}
.pager .folno{color:#6b6256}
.pager a[hidden]{visibility:hidden}
main{max-width:62rem;margin:1rem auto 3rem;padding:0 1rem}
.folio{background:var(--paper);border:1px solid #cdbf9f;border-radius:4px;padding:1.2rem 1.6rem;
  box-shadow:0 1px 3px rgba(0,0,0,.12)}
.region{margin:0 0 .6rem}
.marginalia{font-family:system-ui,sans-serif;font-size:.78rem;line-height:1.45;color:#5a5046;
  background:#f5efe0;border:1px solid #d8ccae;border-radius:4px;
  padding:.45rem .65rem;width:31%;margin:.15rem 0 .7rem}
.marginalia.side-right{float:right;margin-left:1.1rem;clear:right}
.marginalia.side-left{float:left;margin-right:1.1rem;clear:left}
.marginalia .mlabel{display:block;font-size:.62rem;letter-spacing:.05em;text-transform:uppercase;
  color:#9a8d70;margin-bottom:.2rem}
.marginalia p{margin:0}
.marginalia.later-present{border-left:3px solid #5a6b8c}
@media(max-width:640px){.marginalia{float:none;width:auto;margin:.4rem 0}}
.ln{display:block;line-height:1.6}
.heading{font-size:1.05rem;font-weight:bold}
.table-todo{font-family:system-ui,sans-serif;font-size:.85rem;color:#6b6256;background:#f6f1e4;
  border:1px dashed #cdbf9f;border-radius:4px;padding:.7rem .9rem}
.table-todo a{color:#7a5c2e}
.table-cap{font-family:system-ui,sans-serif;font-size:.85rem;margin:.2rem 0 .5rem}
.table-cap .table-note{color:#8a7d63;font-weight:normal;font-size:.78rem}
.table-cap .table-note.verified{color:#2f6b3a}
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
.section-label{max-width:62rem;margin:.3rem auto 0;padding:0 1rem;font-family:system-ui,sans-serif;
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
.status{font-family:system-ui,sans-serif;font-size:.82rem;border-collapse:collapse;width:100%;margin:0 0 1.4rem}
.status caption{text-align:left;font-weight:bold;font-size:1rem;margin-bottom:.4rem;color:#3a342a}
.status th,.status td{border:1px solid #cdbf9f;padding:.3rem .55rem;text-align:left;vertical-align:top}
.status th{background:#efe7d3}
.status tbody tr:nth-child(even){background:#faf6ec}
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
"""

_JS = """
(function(){
  function apply(m){document.body.className='mode-'+m;
    for(const r of document.querySelectorAll('input[name=mode]'))r.checked=(r.value===m);
    try{localStorage.setItem('edmode',m)}catch(e){}}
  const saved=(function(){try{return localStorage.getItem('edmode')}catch(e){return null}})();
  document.addEventListener('DOMContentLoaded',function(){
    if(saved)apply(saved);
    for(const r of document.querySelectorAll('input[name=mode]'))
      r.addEventListener('change',()=>apply(r.value));
    document.addEventListener('keydown',function(e){
      if(e.target.tagName==='INPUT')return;
      if(e.key==='ArrowLeft'){const a=document.querySelector('.pager .prev');if(a&&!a.hidden)location.href=a.getAttribute('href');}
      if(e.key==='ArrowRight'){const a=document.querySelector('.pager .next');if(a&&!a.hidden)location.href=a.getAttribute('href');}
    });
  });
})();
"""


# AHMP image viewer (Bach/Zoomify). The bare ``permalink?xid=…`` landing page IGNORES
# scanIndex; the actual per-scan deep-link is the ``Zoomify.action`` viewer, which honours
# scanIndex and works cold (no jsessionid needed — the server creates a session). scanIndex
# is our folio number (verified: scanIndex=3 → fol. 3 day-length table; scanIndex=70 → fol. 70).
# entityType/entityRef are constants of this archiválie (inv. č. 7916, internal id 143558).
_AHMP_VIEWER = "https://katalog.ahmp.cz/pragapublica/Zoomify.action"
_AHMP_ENTITY_TYPE = "10092"
_AHMP_ENTITY_REF = "%28%5En%29%28%28%28localArchiv%2C%5En%2Chot_%29%28unidata%29%29%28143558%29%29"


def _ahmp_xid(permalink: str | None) -> str | None:
    if not permalink or "xid=" not in permalink:
        return None
    return permalink.split("xid=", 1)[1].split("&", 1)[0]


def _folio_ahmp_url(permalink: str | None, page_nr: int) -> str | None:
    """Per-folio deep-link to the scan in the AHMP Zoomify viewer (opens that folio).

    Uses the ``Zoomify.action`` viewer with ``scanIndex=<folio>`` (= our page number),
    which jumps straight to the folio. (The bare permalink landing page ignores
    scanIndex.) Scans are not republished here — this only links out to AHMP.
    """
    xid = _ahmp_xid(permalink)
    if not xid:
        return None
    return (
        f"{_AHMP_VIEWER}?xid={xid}&entityType={_AHMP_ENTITY_TYPE}"
        f"&entityRef={_AHMP_ENTITY_REF}&scanIndex={page_nr}"
    )


def build_edition(
    work_dir: Path, *, title: str, ahmp_permalink: str | None = None,
    teige_path: Path | None = None, embed_scan: bool = False,
) -> Path:
    work_dir = Path(work_dir)
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
    sections = derive_sections(matched, total)
    folio_section = {n: label for _k, lo, hi, label in sections for n in range(lo, hi + 1)}

    # NOTE: no AHMP reproduction is republished (figures or whole pages) — each folio
    # only links out to the AHMP viewer. Embedding would require an AHMP agreement
    # (<=500px longer side + watermark + "internet" purpose stated in the contract).

    # Pass 2: write per-folio pages + index.
    toc: dict[int, tuple[str, bool]] = {}
    for page_nr, regions, tables, plain, passage, fig_names, clean_lines, is_tbl in entries:
        doc = _page_doc(
            title=title, page_nr=page_nr, total=total, regions=regions,
            ahmp_url=_folio_ahmp_url(ahmp_permalink, page_nr), teige_passage=passage,
            section_label=folio_section.get(page_nr, ""), tables=tables, figures=fig_names,
            clean_lines=clean_lines, embed_scan=embed_scan, table_page=is_tbl,
        )
        (out_dir / f"p{page_nr:04d}.html").write_text(doc, encoding="utf-8")
        snip = (plain[:80] + "…") if plain else (
            "[tabulka]" if (tables or is_tbl) else ("[vyobrazení]" if fig_names else "[prázdná]")
        )
        toc[page_nr] = (snip, passage is not None)

    index = out_dir / "index.html"
    index.write_text(_index_doc(title, sections, toc, ahmp_permalink), encoding="utf-8")
    return index
