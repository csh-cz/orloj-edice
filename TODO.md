<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: EUPL-1.2
-->

# TODO — digitální edice orloje (opis 1587)

Živá edice: <https://csh-cz.github.io/orloj-edice/> · nasazení: `./deploy.sh`

## Přepis — zbývající části knihy
- [ ] **Tabulky f2, f3, f50, f55–69** (komputistické/astronomické — Littera dominicalis,
      zlaté číslo, epakta, východ/západ slunce, polouorlojní počet) → Docling TableFormer.
- [ ] **f65** — česká návodná próza (ukazatel novoluní) uvnitř tabulkové sekce.
- [ ] **f54** — za českým překladem Listu purkmistra pokračuje **německý komputistický
      návod** (přepočet východu/západu mezi německými a českými hodinami) — nepřepsáno.
- [ ] **f4** — latinský verš („Praga…") — přepis.
- [ ] **f80** — latinsko-český epigram (Pythagoras) — přepis.

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
