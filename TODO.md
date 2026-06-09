<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: EUPL-1.2
-->

# TODO — digitální edice orloje (opis 1587)

Živá edice: <https://csh-cz.github.io/orloj-edice/> · nasazení: `./deploy.sh`

## Přepis — zbývající části knihy
- [x] **Tabulky přepsané ručně** (Docling na rukopisné číslice selhal) — **ověřeno
      deterministicky** (`tools/verify_computus.py`, všechny kontroly OK):
  - f50 + f56 (Litera dominicalis N. I) — jul. i greg. nedělní písmena = nezávislý výpočet
    pro všech 28 let; greg. sloupec platí pro 17. stol. (1583–1699).
  - f57 (Tabula Epactarum N. 2) — všechny 3 greg. sloupce epakt = výpočet (Meeus) pro 19
    zlatých počtů; jul. sloupec = greg. + 10.
  - f55 (východ Slunce) — astronomicky, Praha φ ≈ 50,09°, rozdíl ≤ 7 min.
  - f69 (násobilka) — součiny.
  - Próza f62–65, 67, 68.
- [x] **f60 (Tabula intervalli Juliana)** — **DEKÓDOVÁNO A OVĚŘENO**: první číslo dvojice =
      pořadí týdne juliánských Velikonoc ⌊(datum Velikonoc od 1.3. + 16)/7⌋, souhlasí ve všech
      **133/133** buňkách (19 zlatých počtů × 7 nedělních písmen); druhé číslo = doplněk (34/35 − X).
      Reprodukovatelné ve `verify_computus.py` (verify_f60_easter).
- [x] **f61 (Tabula intervalli Gregoriana)** — **DEKÓDOVÁNO** (gregoriánské dvojče f60): první
      číslo = týden gregoriánských Velikonoc, ověřeno 191/210 buněk; zbytek = zóna epakty 25/XXV
      (přesné přiřazení řádků k dořešení na originále).
- [~] **f54** — německý komputistický návod (přepočet německé↔orlojní hodiny): **přepsán
      v edici** (čtení ze skenu + PyLaia German Kurrent jako základ) **i s českým překladem**;
      strukturu i všechna čísla potvrzuje vložený příklad na 3. 5. (východ 4:48 → poledne české
      16:48 → východ český 9:36 → délka dne 14:24), shodný s tabulí f3. Zbývá jen **expertní
      revize přesného německého znění** spojovacích vět ([?]/[…]).
- [x] **Husté mřížky — VŠECHNY PŘEPSÁNY A OVĚŘENY** (Transkribus Titan + komputistika; žádný
      placeholder v edici už nezbývá):
  - [x] **f3** — přepsáno věrně a **kompletně** jako **symetrická tabule délky dne**: jarní blok
        (vlevo, pros→čvn) i podzimní blok (vpravo, čvn→pros) s **měsícem, dnem, svátkem a vstupy
        Slunce** čtenými ze skenu; číselné sloupce (délka dne čtená, délka noci, východ, **české
        /orlojní/ poledne** 20:05→18:00→15:55, odpolední díl) ověřeny výpočtem. Jarní data se v
        33/51 řádků liší od výpočtu (čteno, ne generováno); podzimní denní čísla potvrzují kanonická
        data svátků. „Nové měsíce“ = omyl, samostatný sloupec novoluní neexistuje. Zbývá jen pár
        méně zřetelných jmen [?].
  - [x] **f58 + f59** — Tabula Festorum Mobilium (jul./greg.) — **přepsáno Titanem a OVĚŘENO**:
        35 řádků (Velikonoce 22.III–25.IV), svátky = pevné posuny od Velikonoc (f58 96 %, f59 99 %
        shoda s OCR; zbytek = „9/10“→10); litera, zlatý počet (jul. PFM), epakta (103−E mod 30 + výjimka
        24/25/XXV), Advent dopočítány vzorcem. `tools/build_festa_table.py`, `tools/verify_festa_mobilia.py`.
  - [x] **f66** — Calendarium perpetuum (epakty/novoluní + feriální písmeno po dnech) — **HOTOVO
        A OVĚŘENO**: Litera = ABCDEFG[(den v roce−1) mod 7]; Epacta klesá po dnech (30=*) s vynecháním
        epakty 25 v 29denních lunárních měsících (II,IV,VI,VIII,IX,XI; VIII/IX = saltus). Kotva:
        novoluní epakty 23 v III = 8.III (= PFM−13). Shoduje se se skenem buňka po buňce (I–IV i X–XII).
        `tools/build_f66_table.py`.
  - [x] **f61** — Tabula Intervalli Paschae gregoriánská — **HOTOVO A OVĚŘENO**: plný cell-grid
        (epakty 30(*)…1 × nedělní písmena A–G), buňka = „týden doplněk“; týden = ⌊(greg. Velikonoce
        od 1.III +16)/7⌋, doplněk = (35 pro A, jinak 34) − týden; epakta → velikonoční úplněk → 1. neděle.
        Shoduje se se skenem buňka po buňce (epakta *,29,28,27,26·XXV,25·24…) i s Titan distribucí;
        Dies Concurrentes 0–6 ze skenu. `tools/build_f61_table.py`.
  - **Cesta:** spustit Titan ve webovém Transkribu (kredity na účtu jsou; API token na TrHtr
    nemá nárok — 403), pak naimportovat přes `get_page_xml` (funguje).
  - **f2** — předkreslená, z větší části nevyplněná tabule (jen hlavička) → nic k přepisu.
- [x] **f4** — latinský epigram o sedmi pražských pahorcích („Praha jako nový Řím") — přepsáno + překlad.
- [x] **f80** — dva latinské epigramy (Pythagoras: hekatomba; Archimedes: „pohnu zemí") + nákres
      pravoúhlého trojúhelníku — přepsáno + překlad. (Pozn.: NE latinsko-český, jak dříve uvedeno.)

## ✅ Zdroj slunečních tabulek NALEZEN — v samotném rukopise (záhlaví f3)
Záhlaví f3 přímo jmenuje původ: tabule délky dne/východu/poledne/západu je „**od někdy
D. Tadeáše Hájka z Hájku** … k vyvýšení **Polum L [= 50] graduů** … dle **nového kalendáře**
spravena, **Léta M.DC.LXXXIV [= 1684]**“ (vydaná **„před CXVI [116] lety“ → 1568**). Tj.
**Tadeáš Hájek z Hájku** (†1600), Praha, pól 50°, gregoriánský kalendář — což přesně potvrzuje
nezávislý otisk u f55. Datace sedí: originál 1568 (Hájek živ), tento list = opis 1684.
- [ ] Ověřit na originále čtení letopočtu (1684) a údaje „před CXVI (116) lety“ → originál 1568
      (čteno CXVI, ne LXVI; tím napětí s úmrtím 1600 mizí — Hájek r. 1568 žil).
- [ ] **Dohledat Hájkovu tištěnou tabuli k přímému srovnání.** Hájek 20 let vydával české
      **minuce/pranostiky**; dochovaly se a jsou částečně digitalizované:
  - „Minucí a pranostika … Tadeáše Hájka z Hájku k létu 1567" — **NK ČR**, digitalizováno
    (Europeana / Manuscriptorium); Knihopis eviduje i 1560, 1565, 1598, 1607 (knihoveda.lib.cas.cz).
  - Pro srovnání s naší tabulí je potřeba **post-1584 (nový kalendář)** minuce/tabule (1567 je
    starý kalendář → měla by být ~10 dní sezónně posunutá oproti naší — testovatelná predikce).
  - Hájek byl přímo zapojen do **gregoriánské reformy** (studie Hladký–Šolc) → nová-kalendářní
    tabule od něj je velmi pravděpodobná.
  - Pozor: minuce jsou na konkrétní rok; naše tabule je **perpetuální** (možná samostatný tisk).
  - **Ověřeno přímo (Google Books, vid=NKP:1002291334 = minuce 1565, id YMVhAAAAcAAJ):** Hájkova
    roční minuce má kalendář s astrosymboly (znamení, aspekty), **NE** sloupec východu/délky dne
    na minuty. Tj. f3-tabule není v (této) minuci → hledat **samostatnou perpetuální tabuli** nebo
    Hájkovu kalendářně-reformní práci (~1584, nový kalendář). Google Books stránky umím číst přímo
    (reader API click3 → obrázky); Manuscriptorium hub je JS-only, Google Books API má denní limit.
  - Handoff: dej `vid`/`id` Google Books, nebo Manuscriptorium „pid"/IIIF, nebo screenshot tabule.

## (původně) Dohledání předlohy tabulky východu/délky dne (f55, sekce ~1641)
Forenzně určeno (viz `tools/verify_computus.py` a poznámka u f55): **počítaná**, ne měřená;
**pravé Slunce**; **bez refrakce** (slunovratová symetrie přesně 720 min); výška pólu **~50°**
(fit 49,98° — spíš „kulatých“ 50° než pražských 50°5′ → naznačuje **přejatou generickou
tabuli**, ne pražský výpočet); rovnodennost 21. 3. (nový/gregoriánský kalendář). Žánr:
„*Tabula quotidiana per Annum Ortus et Occasus Solis, Longitudinis item Diei et Noctis, pro
elevatione Poli N graduum*“.
- [ ] Najít **tištěný exemplář pro elevatio poli 50°** a porovnat číslo po čísle.
- Stopy (vše ověřeno, že existuje žánr; 50° verze nedohledána automaticky):
  - **Joseph de Tertiis**, *De gradu horoscopante*, Paříž 1690 — pro 49°, „*quae deservire
    possit G. 48 & 50*“ (digitalizováno: Europeana / BnF). Geneticky nejblíž 50°.
  - **MZK** (Morav. zem. knihovna), záznam `mzk.001065121`: „Ortus et Occasus Solis … ad
    Elevationem Poli 49 Gr.“, tisk 1701 — žánr přímo v ČR (portál historickefondy.cz teď
    erroruje; zkusit Kramerius MZK / fyzicky).
  - **Theodosius Rubeus**, *Tabulae XII* (42°) — má „italské“ i „obecné“ hodiny (orlojní dvojí počet).
  - Vyloučeno: **Argoli**, *Ephemerides 1641–1700* — jeho „ortus et occasus à gr. 1 ad 60“
    je pro **hvězdy**, ne Slunce, a tychonovský (s refrakcí).
  - Kde hledat 50°: **Knihopis**, digitální knihovny **MZK/NKP**, fondy **Strahova** a
    **Klementina**; pražské kalendáře/efemeridy 17. stol. pro elevatio poli 50°.
  - Až bude sken k dispozici (URL/soubor): hotová metodika v `tools/verify_computus.py`
    (geometrie/refrakce/šířka) → okamžité ztotožnění.

## Dolaďování hotových částí (f5–49)
- [ ] **f31–42** — diplomatická kontrola po řádcích (text je *Teige-ukotvený*; ověřit
      proti skenu, ideálně v eScriptoriu).
- [ ] **Marginálie — zbytkové `[?]`**: f13 (nejisté čtení glosu); jednotlivé nejistoty
      f14/f15/f22/f25/f26 ad. → finální slovní přesnost v eScriptoriu (zoom na obraze).
- [ ] **Drobná `[?]` napříč f5–49** (paleografické nejistoty: cangla, rynkl, kluštice,
      mizině, Bechyně, „Dvadcet kop", …).

## Web / edice — prezentace a práva
- [x] **Edičně-typografická vrstva** (hotovo): tři nezávislé osy v hlavičce
      (Znění: diplomatické/normalizované/Teige · Sazba: řádky/čtení · ediční značky on/off),
      číslování řádků po 5 s citovatelnou kotvou `pNNlN` (klik = kopie citace „fol. N, ř. M"),
      závěrečné `[Ediční pozn.]` vyzvednuté do kolabovaného `<details>`. Vše perzistováno
      v localStorage.
- [x] **Dvouzónové „folio" jako předloha** (hotovo): u prozaických folií text v hlavním
      sloupci + samostatný vnější okraj (recto→vpravo, verso→vlevo), kam jdou marginálie
      **mimo** běžící text; čísla řádků na okrajové straně textu. Okraj nese dvě kategorie
      barevně odlišené: původní písařské glosy (hnědá `m-orig`) vs editorské okrajové
      poznámky (zelená `m-ed`, kanál `_MARG_ED`, zatím seed f22). Tabulková/prázdná folia
      zůstávají plné šířky; pod ~760 px se okraj sklápí pod text.
- [ ] **Pravá diplomatická řádková věrnost (1:1 s rukopisem)** — clean řádky ≈ fyzické
      řádky, ne přesně; přesné zarovnání dodá až řádkový GT z eScriptoria (viz Kraken sekce).
- [ ] **Paleografka Listu purkmistra (f51–52)** — dohledat jméno; potvrdit, zda chce
      kredit → nahradit „autorka k doplnění", případně nechat bez kreditu.
- [ ] **Kredity „a další"** — případně doplnit (Stan Marušák; konkrétní členové ČSH).
- [ ] **iframe na AHMP** — zatím vypnuto (`--embed-scan`). Zvážit dotaz na AHMP (framing);
      volitelně výřezy vyobrazení ≤ 500 px + vodoznak po dohodě s archivem.

## Kraken / eScriptorium — HTR model (projekt `~/Developer/KrakenOCR`)
- [ ] **Diplomatický GT** — import `gt/` do eScriptoria, oprava ~2400 řádků
      (= zároveň nejpřísnější revize textu po řádcích).
- [ ] **Base model** — `kraken get` (TRIDIS / German Kurrent) → první fine-tune ze seedu
      (`gt_seed/`: f6, f51–52).
- [ ] **Marginálie** jako regiony typu *Commentary* při tvorbě GT.
- [ ] **KrakenOCR na GitHub** (samostatné repo) — až bude model.

## Hotovo (pro přehled)
- ✅ Přepis Táborského zprávy f5–49 (verš, dedikace, kap. I–XVIII, závěr, kolofony).
- ✅ List purkmistra 1410 — německy f51–52, český překlad f53–54.
- ✅ Astrolabium parvum f70–79.
- ✅ Marginálie f13–46 ověřené ze skenu; zobrazení jako sidenote (verso/recto parita).
- ✅ Web edice (tiráž, metoda, práva, zdroje, tabulka stavu) na GitHub Pages.
- ✅ Komputistické tabulky f50/f55/f56/f57/f60/f69 přepsány a (kde lze) ověřeny vzorcem;
     próza komputu f62–65, 67, 68.
