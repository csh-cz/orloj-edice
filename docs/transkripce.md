<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: EUPL-1.2
-->

# Transkripční konvence edice

Čistá vrstva přepisu (`work/<zakázka>/clean/NNNN.txt`) se řídí **vědeckou
transkripcí česky psaných novověkých pramenů** podle normy:

> Ivan Šťovíček a kol., *Zásady vydávání novověkých historických pramenů z období
> od počátku 16. století do současnosti*, Archivní správa MV ČR, Praha 2002.

Pravidla jsou kodifikována jako agentní skill **`transkripce-novovekych-pramenu`**
(`~/.claude/skills/transkripce-novovekych-pramenu/`), který je závazný při čištění
HTR výstupu do `clean/`. Stručně:

- **Transkripce, ne transliterace** (prameny po 1500 pro historickou vědu) —
  spřežky se rozřeší podle výslovnosti: `ss`→š, `cz`→č/c, `čz/cž`→č, `rz/rž`→ř,
  `au`→ou, `g`(ve funkci j)→j, dlouhé `ſ`→s, `w/v/u/i/y/j` podle funkce.
- **Modernizuje se** interpunkce, velká písmena, hranice slov, kvantita.
- **Zachovávají se** dobové a nářeční rysy (jsauce, vyrejsovati, spůsobu, sejdau…).
- **Ediční značky**: `[ ]` zásah/doplněk, `[?]` nejisté čtení, `[!]`/`[sic]` chyba
  předlohy, `[…]` vypuštěno, `[.....]` nečitelné.
- **Jiný svědek ≠ oprava podle něj**: u opisu (např. Táborského zpráva vs. Teigeho
  edice originálu 1570) se přepisuje **náš** rukopis věrně a odchylky se zaznamenají
  jako varianty, nemažou se.

## Stav přepisu (work/orloj1587)

- **f5–49 (opis Táborského „Zprávy o orloji Pražském")** — čistá diakritická transkripce
  **hotová** (kap. I–XVIII + biografický závěr, Endecasyllabon, kolofon 1570 a **kolofon
  opisovače Matouše Carchesia Jablonského, písaře pražské kanceláře, 1587** — datace ze
  skenu potvrzuje rok 1587). Metoda: starší HTR doc 1173147 (tatáž archiválie, jiný HTR běh) jako
  základ opisu + Teigeho edice 1570 (`data/teige_taborsky.txt`) jako čtecí opora; varianty
  a přídavky opisu (přestavba měsícového soukolí, „přídavek na spheru", mistr z Norimberka)
  zachovány, ne kolacovány pryč. Pro f31–42 selhalo automatické zarovnání (zkomolený HTR,
  bez Teigeho prahu shod) → Teigeho pasáže dohledány ručně (kap. XIII závěr → XVIII).
- **f70–79 (Astrolabium parvum)** — čistá diakritická transkripce hotová; reference téhož
  svědka: přepis na orloj.eu/cs/astrolabium_parvum.htm.
- **f2, f50–69 (komputistické/astronomické tabulky)** — Littera dominicalis, epakta, zlaté
  číslo, vejchod/západ slunce, polouorlojní počet; modalita = Docling TableFormer, ne
  prozaický přepis. Mezi nimi i česká návodná próza (f65 ukazatel novoluní) k doplnění.
- **f80 (latinsko-český epigram, Pythagoras), f1/f81 (prázdné)** — drobnosti.

### Ediční pozn. ke svědkovi
Starší dokument v Transkribu (1173147) **není jiný opis** — je to tatáž archiválie (opis
1587), jen jiný HTR běh; používá se proto volně jako lepší slovní základ. Teige 1901 edituje
**originál 1570** (jiný svědek), slouží jen jako čtecí kontrola; copy-specific odchylky opisu
se značí, nemažou.

### Opisovač (kolofon f. 47)
Opis pořídil roku **1587** (v úterý na den sv. panny Kateřiny = 25. 11. 1587, což skutečně
připadlo na úterý) **Matouš Carchesius z Jablonného** („Jablonský"), písař staroměstské
městské kanceláře — viz kolofon na f. 47: *„Přepsán ode mne Matouše Carchesia Jablonského,
písaře kanceláře pražské, z poručení pana purgkmistra a pánuov Starého Města pražského…"*

Patrně člen rodiny staroměstských písařů **Carchesiů alias Kraus(ů) z Krausenthalu**
(*carchesium* = lat. „číše", počeštění něm. *Kraus*), doložené nezávisle na orloji:
- J. Teige, *Základy starého místopisu pražského*, Staré Město — staroměstské **kšafty,
  rkp. č. 2205**: k r. **1583** „Martin Carchesius, písař radní"; k r. **1598** „Matouš
  Carchesius jinak Krausz z Krausnthalu, písař přísežný v dolejší kancelláři" (= nejspíš náš
  opisovač);
- J. Malý, *Vlastenský slovník historický* (1877), heslo **Carchesius** — o příbuzném
  spisovateli **Martinu Carchesiovi** (Kraus z Krausenthalu, úředník SMP 1564–1602; *Bič
  židovský* 1604, *Zrcadlo židovské*, *Historie o doktorovi Faustovi* 1611).

Identita opisovače je tedy **věc známá** (jmenuje ho Z. Horský, *Pražský orloj*, 1988 → orloj.eu),
ne nový objev. Otevřený zůstává jen **rozpor predikátu** *z Jablonného/Jablonský* (kolofon +
orlojní literatura) × *z Krausenthalu/Kraus* (místopis + slovník) — k ověření v archivu
(AHMP, Sbírka rukopisů: opis orloje **inv. č. 7916**; kniha kšaftů **č. 2205**). Pro edici je
**závazný kolofon opisu** (Carchesius Jablonský), totožnost s písařem „Kraus z Krausenthalu"
se uvádí jako hypotéza.
