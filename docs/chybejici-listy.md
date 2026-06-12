<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: CC-BY-4.0
-->

# Chybějící listy orlojní knihy (st. fol. 33–34 a 42–45)

**Status:** badatelský zápis, 2026-06. Týká se: AHMP, Sbírka rukopisů, inv. č. 7916.
V edici vyznačeno bannery u fol. 56 a 70; stará foliace v hlavičce každého folia
(„st. fol."), mapa v `edition_content.py` (`_PENCIL_FOLIO`, `_MISSING_BEFORE`).

## 1. Nález

Stará **tužková foliace** (čísluje listy, psaná na rectech) má proti dnešnímu pořadí
skenů dvě přerušení — **v knize chybí celkem 6 listů**:

| mezera | mezi listy (st. fol.) | mezi našimi skeny | kontext obsahu |
|---|---|---|---|
| A | **33–34** (2 listy) | f55 / f56 | uvnitř komputu: mezi tabulí východu Slunce a Litera dominicalis |
| B | **42–45** (4 listy) | f68 / f70 | přechod komputus → Astrolabium parvum |

Naše foliace dle skenů je souvislá; listy chybějí ve fyzické knize. Foliace tedy
**předchází ztrátě** (jinak by čísla běžela souvisle) — nebo foliátor čísla přeskočil,
což vyvrací bifoliový rozbor níže.

## 2. Hypotéza: vypadlé střední dvojlisty složek

Obě mezery přesně odpovídají **ztrátě nejvnitřnějších dvojlistů (bifolií)** složek:

**Mezera B = dva střední dvojlisty kvaternu listů 40–47** (sedí dokonale):

```
složka 40–47:   40 ↔ 47   ✓ (f66)   ✓ (f72)
                41 ↔ 46   ✓ (f68)   ✓ (f70)
                42 ↔ 45   ✗         ✗
                43 ↔ 44   ✗         ✗
```

Všechny čtyři vnější listy dochovány, chybí přesně střed složky.

**Mezera A = nejvnitřnější dvojlist** složky se středem mezi listy 33|34 (okolní listy
31, 32, 35, 36 vše dochováno; velikost složky odsud neurčitelná — binion 32–35 i
kvatern 30–37 sedí stejně).

Vnitřní dvojlisty drží jen šitím v přehybu a **vypadávají vcelku** — mluví to spíše pro
uvolnění/vyjmutí celých přeložených archů než pro vyřezávání jednotlivých stránek.

**Testovatelná predikce (autopsie hřbetu u f55/56 a f68/70):**
- vypadlé střední dvojlisty → **žádné pahýly**, jen obnažený střed složky se šitím;
- vyřezávané jednotlivé listy → pahýly protilehlých polovin (u mezery B čtyři).

## 3. Je výpadek už publikován? (rešerše 2026-06)

Prověřeno — **podle všeho NE, jde o náš nález:**

- **Macháček 1962** (*Nález zprávy o vytvoření orloje…*, Zprávy Komise ČSAV 10/1962;
  Zotero `PCXNHQ8T`, fulltext v poznámce) — výpadek **nezmiňuje**. Důležité údaje:
  - „Je to **rukopis mající 51 listů**, vázaný v kůži…“
  - „Zpráva Táborského **končí na 27. listu**“ — sedí na tutéž tužkovou foliaci
    (kolofon 1587 = list 27 = náš sken f47) → Macháček pracoval s foliací, kterou čteme.
  - **Indicie k dataci ztráty:** s našimi 6 chybějícími listy by kniha měla ~43
    číslovaných listů (s předními ~46); kompletní řada dává 49 (s předními ~52).
    Macháčkových **51 je výrazně blíž kompletnímu stavu** → listy v r. 1962 možná
    ještě byly. *Pozor:* nevíme, jak počítal — mohl číslo odvodit z poslední foliace,
    aniž listy přepočítal; indicie slabá až střední, ne důkaz. **Otevírá ale otázku,
    zda ztráta nenastala až po r. 1962, tj. v péči archivu.**
- **Horský & Procházka 1964** — máme jen anglické résumé (8 s., Zotero `R68FP2W8`):
  popis kodexu neobsahuje. Česká studie ve fulltextu nedostupná.
- **Horský 1988** (*Pražský orloj*, Panorama; Zotero `EJZ42CCC`, bez fulltextu) —
  **neověřeno; největší šance na zmínku** (s knihou pracoval, Skála cituje foto
  s. 137). → ověřit fyzicky.
- **Skála** (*Vývoj podoby astrolábu*, Zotero `I9RFMMK9`) — foliaci/chybění neřeší.
- **Katalog AHMP** — fyzický popis (počet ff.) online neuvádí; jednotku datuje
  „1587–1642“ (vrstvu 1689 nezná — drobnost k nahlášení archivu).

## 4. Co dál

1. **Autopsie v AHMP** (Petr Skála / badatelna): hřbet u f55/56 a f68/70 (pahýly ano/ne);
   čelo knihy (tužková řada začíná „4“ na f2 → listy 1–3 = předsádky? další ztráta?);
   přepočet listů vs. Macháčkových „51“.
2. **Horský 1988** — projít popis rukopisu (s. ~137 a okolí).
3. Po autopsii aktualizovat bannery f56/f70 (hypotéza → potvrzeno/vyvráceno).

## Prameny

- AHMP, Sbírka rukopisů, inv. č. 7916; permalink `xid=E1BD466FB72711DF820F00166F1163D4`.
- S. Macháček, Nález zprávy o vytvoření orloje Starého Města r. 1410, Zprávy Komise
  pro dějiny přírodních, lékařských a technických věd ČSAV 10, 1962, s. 21–24.
- Z. Horský – E. Procházka, Pražský orloj, 1964 (EN résumé); Z. Horský, Pražský orloj,
  Praha 1988.
- Edice: <https://csh-cz.github.io/orloj-edice/> (fol. 56, 70).
