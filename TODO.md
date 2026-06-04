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
- [ ] **f60 (Tabula intervalli Juliana)** — přepsáno, ale **NEOVĚŘENO**: dvojčíslí v buňkách
      se nepodařilo dekódovat ani ztotožnit s vypočteným juliánským datem Velikonoc. Buď
      jiná sémantika (interval, ne datum), nebo chyba čtení → dekódovat / překontrolovat.
- [ ] **Zbývající husté mřížky** (popsány captiony + odkaz na sken; nepřepsány — vysoké
      riziko chyb při ručním čtení, bez ověřovacího invariantu):
  - [ ] **f58 + f59** — Tabula Festorum Mobilium (pohyblivé svátky, mnoho sloupců dat).
  - [ ] **f61** — Tabula intervalli Gregoriana (epakta × litera; pozn. gregoriánská
        epakta 25/XXV způsobuje ±1řádkovou nejistotu v ose epakt → nutná pečlivá kontrola).
  - [ ] **f66** — epakty/novoluní po dnech roku (hustá číselná tabule, měsíce v záhlaví).
  - [ ] **f3** — délka dne/noci + východ/poledne/západ pro každý den (hustá tabule).
  - [ ] **f2** — předtištěná, z větší části **nevyplněná** tabule (jen hlavička).
  - Doporučení: dotáhnout přes tabulkový HTR model nebo cílenou kontrolu, ne odhadem.
- [ ] **f54** — za českým překladem Listu purkmistra pokračuje **německý komputistický
      návod** (přepočet východu/západu mezi německými a českými hodinami) — nepřepsáno.
- [ ] **f4** — latinský verš („Praga…") — přepis.
- [ ] **f80** — latinsko-český epigram (Pythagoras) — přepis.

## ✅ Zdroj slunečních tabulek NALEZEN — v samotném rukopise (záhlaví f3)
Záhlaví f3 přímo jmenuje původ: tabule délky dne/východu/poledne/západu je „**od někdy
D. Tadeáše Hájka z Hájku** … k vyvýšení **Polum L [= 50] graduů** … dle **nového kalendáře**
spravena, **Léta M.DC.LXXXIV [≈ 1684]**“ (vydaná „před 66 lety“). Tj. **Tadeáš Hájek z Hájku**
(†1600), Praha, pól 50°, gregoriánský kalendář — což přesně potvrzuje nezávislý otisk u f55.
- [ ] Ověřit na originále čtení letopočtu (1674/1684) a údaje „před LXVI (66) lety“ (drobné napětí
      s Hájkovým úmrtím 1600 → pravděpodobně opis převzal i hlavičku staršího tištěného vydání).
- [ ] Přepsat číselnou mřížku f3 (365 dní) a ověřit stejnou metodou jako f55 (`verify_computus.py`).
- [ ] **Dohledat Hájkovu tištěnou tabuli k přímému srovnání.** Hájek 20 let vydával české
      **minuce/pranostiky**; dochovaly se a jsou částečně digitalizované:
  - „Minucí a pranostika … Tadeáše Hájka z Hájku k létu 1567" — **NK ČR**, digitalizováno
    (Europeana / Manuscriptorium); Knihopis eviduje i 1560, 1565, 1598, 1607 (knihoveda.lib.cas.cz).
  - Pro srovnání s naší tabulí je potřeba **post-1584 (nový kalendář)** minuce/tabule (1567 je
    starý kalendář → měla by být ~10 dní sezónně posunutá oproti naší — testovatelná predikce).
  - Hájek byl přímo zapojen do **gregoriánské reformy** (studie Hladký–Šolc) → nová-kalendářní
    tabule od něj je velmi pravděpodobná.
  - Pozor: minuce jsou na konkrétní rok; naše tabule je **perpetuální** (možná samostatný tisk).

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
