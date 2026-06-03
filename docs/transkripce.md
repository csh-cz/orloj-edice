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

- **f70–79 (Astrolabium parvum)** — čistá diakritická transkripce hotová; reference
  téhož svědka: přepis na orloj.eu/cs/astrolabium_parvum.htm.
- **f5–30, 43–49 (opis Táborského zprávy)** — zatím HTR draft; přepsat věrně z obrazu
  + kolace variant proti Teigemu (data `data/teige_taborsky.txt`).
- Ostatní (němčina, kalendářní tabulky, poznámky) — HTR / Docling tabulky.
