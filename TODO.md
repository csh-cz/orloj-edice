<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: EUPL-1.2
-->

# TODO — Orlojní kniha (opis 1587)

Živá edice: <https://csh-cz.github.io/orloj-edice/> · nasazení: `./deploy.sh`
Stav: **obsahově kompletní** — všech 79 textových/tabulkových folií přepsáno a ověřeno;
zbývají dořešitelné nejistoty a navazující výzkum. (Hotové položky se z tohoto souboru
mažou; úplný stav po částech = tabulka na úvodní stránce edice.)

## Otevřené — text a čtení
- [x] **f54 němčina** — **přečteno ze skenu řádek po řádku** (plný diplomatický přepis;
      „die mittlere Zahl duplirn" = délka dne zdvojením doplňku, lapsus „Untergang" [!],
      oprava „34" nad škrtem). Čísla ověřena (`tools/verify_f54_sunrise.py`). Expertní
      revize německého paleografa už jen volitelná kontrola.
- [ ] **Zbylá `[?]` (~31)** — legitimní paleografické nejistoty: marginálie ruky A (f13–45),
      latina f4, jednotlivá slova v próze (cangla, rynkl, kluštice, Bechyně…), „Jana [?]"
      na f3 (12. XI; datem sv. Jan Almužník, litery přízviska nečitelné). Cílený skenový
      průchod, ideálně v eScriptoriu.
- [ ] **f61 — zóna epakty 25/XXV** — 19/210 buněk nesouhlasí s výpočtem (dvojí podoba
      gregoriánské epakty 25 posouvá řádek); přiřazení řádků dořešit na originále.

## Otevřené — atribuce a identita
- [ ] **f38 (redatace orloje k 1410)** — ruka B vs C nerozhodnuto (obsahově spíše B).
- [ ] **Identita pisatelů C (~1641–42) a D (1689)** — archivní pátrání; kompletní handoff
      prompt s profily a hinty: `docs/handoff-identita-pisatelu-CD.md`. Primárně AHMP
      staroměstské účty 1641–42 a 1689 (plat orlojníkovi), radní manuály, listina 1659.

## Otevřené — kodikologie a předlohy
- [ ] **Chybějící listy** (objev ze staré tužkové foliace): st. fol. 33–34 (mezi naším
      f55/f56) a 42–45 (mezi f68/f70). Fyzicky ověřit na originále v AHMP (ústřižky
      v hřbetu?). V edici vyznačeno bannery na f56/f70; mail Petru Skálovi odeslán/draft.
- [ ] **Hájkova „Tabule dlúhosti dne a noci k spravování orloje" (1574)** — dochování
      originálu: Knihopis prověřen (tabule v něm NENÍ, minuce ano) → zbývá ručně
      Manuscriptorium, katalog starých tisků NK ČR, monografie (Hladký–Šolc; NTM).
      Pokud bez exempláře → f3 je unikátní svědek. Souhrn: `docs/hajek-tabule-orloje-1574.md`.
- [ ] **Předloha tabule f55** (východ Slunce, vrstva ~1641; jiná než f3/Hájek 1574 — viz
      pozn. u f55): najít tištěnou perpetuální tabuli pro elevatio poli 50°. Stopy:
      J. de Tertiis 1690 (49°, „deservire possit 48 & 50", BnF); MZK `mzk.001065121`
      („Ortus et Occasus… 49 Gr.", 1701). Metodika ztotožnění hotová ve
      `tools/verify_computus.py`.

## Otevřené — web / prezentace
- [ ] **Kritický aparát variant do edice** — kolace hotové (`tools/collate_carchesius_teige.py`,
      `tools/collate_1587_1570.py` → `work/orloj1587/collation_*.{json,md}`); promítnout
      varianty k foliím (a doředit `[?]`, kde Teige/autograf dává čtení — vzor f5 „nad tím nespal").
- [ ] **Verza staré foliace** — volitelně zobrazit „list N (verso)" zděděné z recta.
- [ ] **Paleografka Listu purkmistra (f51–52)** — dohledat jméno, potvrdit kredit
      (nahradit „autorka k doplnění").
- [ ] **Kredity „a další"** — konkrétní členové ČSH (Stan Marušák?).
- [ ] **iframe na AHMP** (`--embed-scan` vypnuto) — zvážit dotaz na archiv; volitelně
      výřezy ≤ 500 px + vodoznak po dohodě.
- [ ] **Řádková věrnost 1:1 s rukopisem** — clean řádky ≈ fyzické řádky; přesné zarovnání
      dodá až řádkový GT z eScriptoria.

## Navazující projekty (mimo toto repo)
- [ ] **Originál 1570** (autograf Táborského, AHMP sign. 1867) — 23 sporných řádků
      z `tools/align_teige_lines.py` k diplomatické kontrole; samostatná edice.
- [ ] **Writer-ID vylepšení** — návrh Tier 1–3 (eval harness, VLAD, self-supervised):
      `~/Developer/KrakenOCR/writer_id/NAVRH_vylepseni.md` (zatím neimplementováno).
- [ ] **Kraken/eScriptorium HTR model** (`~/Developer/KrakenOCR`): diplomatický GT
      (~2400 řádků), base model (TRIDIS/German Kurrent), marginálie jako *Commentary*.

## Hotovo (souhrn — detaily v tabulce stavu v edici a v git logu)
- ✅ Kompletní přepis knihy f2–f80 (68 textových folií + 11 tabulek); f1/f81 = desky vazby.
- ✅ Všechny komputistické tabulky dekódovány a deterministicky ověřeny
     (f50/55/56/57/58/59/60/61/66/69; f60 133/133, f61 191/210); verify suite v `tools/`.
- ✅ Kolace: Carchesius × Teige (842 variant, shoda 91,8 %) i × autograf 1570 napřímo;
     f31–42 tím diplomaticky ověřeno (žádné chyby přepisu).
- ✅ Předlohy ztotožněny: Astrolabium parvum = překlad F. Rittera (Norimberk 1613, kolace
     textu i figur); f3 = Hájkova „Tabule… k spravování orloje" (1574).
- ✅ Oprava datace f3: M·DC·LXXXIX = **1689** (ne 1684) → originál Hájka 1573/74.
- ✅ Stará tužková foliace přečtena a zachována (hlavička „st. fol. N"); objev chybějících
     listů (33–34, 42–45) vyznačen v edici.
- ✅ Čtyři písařské ruce (A/B/C/D) + writer-ID; epigramy f4/f80 → pracovně ruka C;
     medailon Mikuláše Petra (f52); profil ruky C; ověřené pozorování 1. XI 1642.
- ✅ Ediční UI: tři osy zobrazení, číslování řádků s citací, dvouzónové folio, Teige režim
     jen na f5–49, kurátorované oddíly (Carchesius = jeden oddíl), úvod-článek.
- ✅ Infrastruktura: clean/ + tables_clean/ verzovány v gitu (zálohováno na GitHub),
     obsah oddělen od enginu (`edition_content.py`), testy 23/23, ruff čistý.
