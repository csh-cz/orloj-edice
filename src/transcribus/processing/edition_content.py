# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Editorial CONTENT of the orloj edition (AHMP inv. 7916 + the 1570 autograph).

Everything here is curated scholarly content — captions, editorial notes, folio
snips, status rows, foliation maps, section structure — kept separate from the
rendering engine in ``edition.py``. Edit this file to change what the edition
says; edit ``edition.py`` to change how it renders.
"""

from __future__ import annotations

# Kurátorované členění orlojní knihy 1587 (AHMP inv. č. 7916) — explicitní, ne
# heuristické: celý Carchesiův opis Táborského zprávy je JEDEN oddíl (f5–49).
_SECTIONS_1587: list[tuple[str, int, int, str]] = [
    ("vazba", 1, 1, "Vazba — přední deska"),
    ("hajek", 2, 3, "Přední list — Hájkova tabule délky dne (opis ≈ 1689)"),
    ("epigram", 4, 4, "Latinský epigram — sedm pražských pahorků"),
    ("taborsky", 5, 49, "Táborského Zpráva o orloji pražském — opis Matouše Carchesia (1587)"),
    ("komputus", 50, 50, "Komputus — Tabula Litera dominicalis"),
    ("list", 51, 54, "List purkmistra 1410 — opis Mikuláše Petra (1628)"),
    ("komputus", 55, 69, "Komputistické a astronomické tabulky (~1641–42)"),
    ("astrolabium", 70, 79, "Astrolabium parvum — český překlad Franze Rittera (~1642)"),
    ("epigram", 80, 80, "Latinské epigramy — Pythagoras, Archimedes"),
    ("vazba", 81, 81, "Vazba — zadní deska"),
]

# Folia, jejichž jazyk NENÍ čeština (latina, němčina) — česká normalizace by je zkomolila
# (g→j apod.), takže se u nich „normalizovaný" pohled rovná diplomatickému.
_NO_NORMALIZE: frozenset[int] = frozenset({4, 51, 52, 54, 62, 80})

# Starší (původní) foliace TUŽKOU — čísluje LISTY, psaná na rectu, takže verso/prázdné
# strany číslo nemají (to není mezera). Přečteno ze skenů (pravý horní roh). Naše „folio"
# = index skenu; tato mapa skenový index → tužkové číslo listu se zachovává jako historický
# údaj. Přední blok (f5–49) je pravidelný; v zadní části (f50+) je foliace nepravidelná a
# má diskontinuitu (mezi f68=41 a f70=46), proto se čísla jen čtou, nedopočítávají.
_PENCIL_FOLIO: dict[int, str] = {
    2: "4",
    5: "6", 7: "7", 9: "8", 11: "9", 13: "10", 15: "11", 17: "12", 19: "13", 21: "14",
    23: "15", 25: "16", 27: "17", 29: "18", 31: "19", 33: "20", 35: "21", 37: "22",
    39: "23", 41: "24", 43: "25", 45: "26", 47: "27", 49: "28",
    50: "29", 51: "30", 53: "31", 55: "32", 56: "35", 58: "36", 60: "37", 62: "38",
    64: "39", 66: "40",
    68: "41", 70: "46", 72: "47", 74: "48", 76: "49", 77: "50", 79: "51", 80: "52",
}

# Přerušení staré (tužkové) foliace = podle ní v knize CHYBÍ listy. Klíč = naše folio,
# PŘED nímž mezera je; hodnota = popis. Patrně ztracené listy (k ověření na originále —
# ústřižky v hřbetu). Viz docs / mail Petru Skálovi.
_MISSING_BEFORE: dict[int, str] = {
    56: "Podle staré (tužkové) foliace zde mezi listy 32 a 35 <b>chybějí dva listy "
        "(st. fol. 33–34)</b> — patrně ztracené. Obsahově padly doprostřed komputistického "
        "oddílu (mezi tabuli východu Slunce a Litera dominicalis). <b>Hypotéza:</b> oba listy "
        "jsou poloviny <b>jednoho přeloženého archu — nejvnitřnějšího dvojlistu složky</b> se "
        "středem mezi listy 33|34 (okolní listy 31, 32 i 35, 36 jsou všechny dochované). "
        "Vnitřní dvojlist drží jen šitím v přehybu a vypadává vcelku; mluví to spíše pro "
        "uvolnění/vyjmutí celého archu než pro vyřezání jednotlivých stránek. Ověřitelné na "
        "originále: vypadl-li střední dvojlist, nebudou v hřbetu žádné pahýly, jen obnažený "
        "střed složky se šitím.  V literatuře výpadek zaznamenán není (Macháček 1962 jej nezmiňuje a udává „rukopis mající 51 listů“ — což naznačuje, že listy tehdy možná ještě byly; Horský 1988 k ověření). Podrobně docs/chybejici-listy.md. Naše foliace dle skenů je souvislá; chybí jen v původní knize.",
    70: "Podle staré (tužkové) foliace zde mezi listy 41 a 46 <b>chybějí čtyři listy "
        "(st. fol. 42–45)</b> — patrně ztracené. Padly na přechod mezi koncem komputistického "
        "oddílu a začátkem Astrolabia parvum. <b>Hypotéza:</b> mezera přesně odpovídá "
        "<b>dvěma nejvnitřnějším dvojlistům kvaternu listů 40–47</b> (dvojice 42+45 a 43+44): "
        "všechny čtyři vnější listy složky — 40, 41, 46 a 47 — jsou dochované a chybí právě "
        "střed. Vnitřní dvojlisty drží jen šitím v přehybu a vypadávají vcelku; mluví to spíše "
        "pro uvolnění/vyjmutí celých archů než pro vyřezání jednotlivých stránek. Ověřitelné "
        "na originále: vypadly-li střední dvojlisty, nebudou v hřbetu žádné pahýly (při "
        "vyřezávání by naopak zůstaly čtyři).  V literatuře výpadek zaznamenán není (Macháček 1962 jej nezmiňuje a udává „rukopis mající 51 listů“ — což naznačuje, že listy tehdy možná ještě byly; Horský 1988 k ověření). Podrobně docs/chybejici-listy.md. Naše foliace dle skenů je souvislá; chybí jen "
        "v původní knize.",
}

# Popisky tabulkových folií (z hlaviček; data zatím nepřepsána). Komputistický aparát.
_TABLE_CAPTIONS: dict[int, str] = {
    2: "Tabule dlúhosti dne i noci, vejchodu, poledne a západu — předkreslená (z větší části nevyplněná) tabule pro zpravování orloje.",
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
    2: "Předkreslená (z větší části nevyplněná) tabule pro zpravování orloje",
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
    51: "List purkmistra 1410 — německy (opsáno 1628)",
    52: "List purkmistra 1410 — německy (pokrač.)",
    53: "List purkmistra 1410 — dobový český překlad",
    54: "List purkmistra — český překlad; německý návod přepočtu hodin",
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
        "zatím není doložen — v Knihopisu jsou vedeny Hájkovy minuce, ale tato orlojní tabule "
        "v něm chybí (zbývá ruční dohledání v Manuscriptoriu a katalogu starých tisků NK ČR); "
        "je-li ztracen, je <b>tento opis "
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

# --- Rozbor marginálií (samostatná stránka marginalia.html) -------------------------
_MARG_LAT = ("index", "declinat", "linea", "tabula", "solstit", "solis", "horar",
             "oppositi", "coniuncti", "circul")

_MARG_HIST = ("zvůnek", "táborsk", "tobiáš", "tobiass", "špaček", "obnoven", "zprávce",
              "přistaup", "přistoup", "umřel", "škody", "zase přist")

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

# Stav zpracování po částech knihy. Průběžně se aktualizuje (edit → regenerace → deploy).
# klíč stavu: done = hotový čistý přepis · partial = rozpracováno · todo = chybí · na = prázdná
_STATUS_ROWS: list[tuple[str, str, str, str, str]] = [
    ("f1", "předsádka", "—", "na", "—"),
    ("f2–f3", "úvodní astron. tabulky — Hájek z Hájku (přední list, opis ≈ 1689)",
     "D · ~1689", "done",
     "f2 = táž tabule jen předkreslená a nevyplněná, ale s týmž záhlavím a <b>touž rukou jako "
     "f3</b> (kopista r. 1689 list nadepsal a nalinkoval, vyplnil až f3); f3 = symetrická "
     "perpetuální tabule po krocích délky dne — <b>opis Hájkovy „Tabule dlúhosti dne a noci "
     "k spravování orloje“ (1574)</b>, pól 50°, upraveno na nový kalendář; originál tisku "
     "v Knihopisu nedoložen, f3 patrně vzácný svědek — "
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
    ("f31–f42", "Táborský: kap. XIII–XVIII", "A · 1587", "done",
     "ověřeno <b>kolací proti Teigeho edici i přímo proti autografu 1570</b> (porovnáno každé "
     "slovo; <code>collate_carchesius_teige.py</code>, <code>collate_1587_1570.py</code>) + "
     "vizuální kontrolou skenu — <b>žádné chyby přepisu</b>. Odlišnosti jsou skutečné dobové "
     "varianty opisu × originálu (au/ú, ej/aj, ů/uo, zodyaku, jsau/sou); že se týchž záměn opis "
     "liší i od autografu, ne jen od Teige, potvrzuje, že jde o genuinní rozdíl 1587×1570, "
     "nikoli o Teigeho editorskou normalizaci. Pozdější vsuvka f38 (redatace orloje k r. 1410, "
     "„vide list purkmistra“) = jiná pozdější ruka ≥1628 (B/C nerozhodnuto, obsahově spíše B)"),
    ("f43–f49", "Táborský: biografický závěr, verše, kolofony 1570 + 1587", "A · 1587", "done", "—"),
    ("f50", "Tabula Litera dominicalis (N. I)", "C · ~1641–42", "done",
     "cyklus solaris → nedělní písmeno (jul./greg.), 28 řádků, ověřeno vzorcem"),
    ("f51–f52", "List purkmistra 1410 (něm., opsáno 1628)", "B · 1628", "done", "—"),
    ("f53–f54", "List purkmistra — dobový český překlad", "B · 1628", "done",
     "český překlad kompletní (ruka B) — od „My, purkmistr…“ přes datovací doložku 1410 "
     "(„ve čtvrtek před sv. Havlem“, ověřeno: 9. X 1410 = čtvrtek) až po připsaný kancelářský "
     "kolofon 1628 (Mikuláš Petr). Německý návod na f54 (přepočet německé↔orlojní hodiny) — "
     "<b>zvláštní německy píšící ruka</b> (≥1641) — <b>plný diplomatický přepis čtením skenu "
     "řádek po řádku</b> (mj. „die mittlere Zahl duplirn“ = délka dne zdvojením doplňku; "
     "lapsus „Untergang“ [!]; oprava „34“ nad škrtem) a <b>všechna čísla příkladu ověřena</b> "
     "(f55: 3. máj = 4:43; verify_f54_sunrise.py)"),
    ("f55–f69", "komputistické/astron. tabulky + próza (sekce ~1641–42)", "C · ~1641–42", "done",
     "vše přepsáno a ověřeno výpočtem: litera dominicalis (f50/56), epakty (f57), vejchod Slunce "
     "(f55), intervallum Velikonoc (f60 jul. souhlasí 133/133; f61 greg. 191/210 — zóna epakty "
     "25 k dořešení na originále), festa mobilia jul./greg. (f58/59), "
     "calendarium novoluní po dnech (f66), násobilka (f69) + komputistické prózy f62–65, 67, 68"),
    ("f70–f79", "Astrolabium parvum (~1642, čes. překlad Franze Rittera)", "C · ~1641–42", "done",
     "noční určení času ze stínu Měsíce + oprava astrolábem; datovaný příklad z 1. XI 1642 "
     "ověřen nezávislým výpočtem (tools/verify_astrolabe_1642.py). Doložen jako překlad "
     "Ritterova <i>Astrolabia</i> (Norimberk 1613) — kolace pasáží i figur (viz článek u f70)"),
    ("f80", "dva latinské epigramy (Pythagoras, Archimedes) + nákres trojúhelníku",
     "C? · ~1641–42", "done",
     "přepsáno + překlad (hekatomba; „pohnu zemí“). Ruka pracovně připsána <b>C</b> "
     "(táž jako f4; writer-ID, matematický obsah, poloha hned za Astrolabiem) — jistota střední"),
    ("f81", "předsádka", "—", "na", "—"),
]

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
