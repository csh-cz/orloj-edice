<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: CC-BY-4.0
-->

# Handoff pro indexačního agenta — doplnit orlojní zdroje do OpenSearch

> Prompt + podklad. Předej indexačnímu agentovi (ten, který spravuje stack `horologie-*`).
> Připraveno 2026-06 v rámci edice orlojní knihy (`csh-cz/orloj-edice`).

## Prompt (zadej agentovi)

> Spravuješ OpenSearch stack **`horologie-opensearch`** (Docker, host **`localhost:9210`** →
> kontejner 9200; dashboards 5611, MinIO 9110/9111). Index je **hybridní fulltext** pražských
> historických pramenů k pražskému orloji: každý dokument má pole **`text`** (čtený text),
> **`dense`** + **`sparse`** (BGE-M3 embeddingy — dense 1024 + sparse rank_features), a metadata
> **`edice`** (název zdroje/edice), **`source_ref`** (citace/lokace pramene), **`year`**,
> **`scan`** (id stránky/segmentu), volitelně **`bbox`/`column`/`house`**. Embeddingy generuj
> stejným postupem jako stávající dokumenty (BGE-M3 hybrid, dense+sparse).
>
> **Úkol:** přidej do indexu **sekundární i primární zdroje, které jsme použili při edici
> orlojní knihy a které v korpusu zatím chybějí** (ověřeno: hledání jmen Macháček/Horský/Skála/
> Ritter/Hájek/Ďurčanský vrací 0 zásahů). Cílem je, aby šly tyto zdroje prohledávat spolu
> s pramennými edicemi (Teige, Tomek, berní knihy…) a sémanticky propojovat s indexem
> `orloj-zaznamy`. U každého zdroje vyplň `edice`, `source_ref` (přesná citace), `year`;
> dlouhé texty segmentuj po stránkách/odstavcích jako u stávajících edic. Kde zdroj NENÍ
> digitálně dostupný, založ aspoň **stub dokument** s bibliografickou citací a poznámkou
> „fulltext nedostupný — k doplnění", ať je zdroj v indexu dohledatelný.
>
> Zdroje a jejich dostupnost jsou v tabulce níže. Mnohé mají záznam v **Zotero** (klíče
> uvedeny); fulltext ber z Zotero attachmentu / `get_content`, jinak z uvedeného online
> zdroje. Po doběhnutí vypiš, co se podařilo zaindexovat (počty dokumentů) a co zůstalo jako
> stub.

## Co už v korpusu JE (neduplikovat)

| index | dok. | obsah |
|---|---|---|
| `tomek-mistopis` | 41761 | Tomek, Základy starého místopisu Pražského (1865) |
| `teige-mistopis` | 12147 | Teige, Základy starého místopisu pražského — Staré Město |
| `tadra-akta` | 2898 | Tadra, Soudní akta konsistoře pražské III (1392–98) |
| `edice-externi` | 2501 | externí plné texty (mj. Tomek Základy — archive.txt) |
| `liber-vetustissimus-edice` | 2055 | Liber vetustissimus (Pátková 2011) |
| `cirkevni-prameny` | 1418 | Libri confirmationum ad beneficia eccl. Pragensem |
| `berni-knihy-patkova-1079` | 1046 | Berní knihy SM 1427–1434 (Pátková) |
| `cim-praha-1886` | 925 | Čelakovský, Codex iuris municipalis I — Privilegia měst pražských |
| `kniha-pametni-992` | 538 | Kniha pamětní (Liber Tertius), AHMP rkp. 992, 1417–1480 |
| `seznamy-mestanu` | 237 | Teige, Seznamy měšťanů pražských — Staré Město |
| `berni-knihy-1427` | 234 | AHMP rkp. 20: Berní knihy SM |
| `lehner-1911` | 117 | Lehner, Die mittelalterliche Tageseinteilung… |
| `tomek-ccm-1844` | 23 | Tomek, Kniha Starého Města pražského od r. 1310 (ČČM 18, 1844) |
| `ahisto` | 17 | Acta judiciaria + Archiv pražské metropolitní kapituly (via AHISTO) |
| **`orloj-zaznamy`** | 6 | **jádro** — ručně autopsované primární záznamy k orloji 1366–1410 (radniční orloj, listina 1410 z rkp. 7916, katedrální orloj). Nové zdroje se mají sémanticky vázat sem. |

(Počty dokumentů k 2026-06; ignoruj systémové `.kibana*`, `.opensearch-*`, `top_queries-*`.)

## Zdroje k doplnění (priorita shora)

| zdroj | citace | Zotero | dostupnost / odkud vzít text |
|---|---|---|---|
| **Ďurčanský 2006** | M. Ďurčanský, *(studie o staroměstských financích / knihách finančních příkazů rady SM)*, Folia Historica Bohemica **22**, 2006 | — (není v Zotero) | dohledat PDF (ČAV / FHB); zdroj jmen u opravy orloje 1659 (hodinář **Jan Jiří Miller**, malíř **O. O. Petr**) a rodu Petrů. **Vysoká priorita** (jediný zdroj Millera). |
| **Macháček 1962** | S. Macháček, *Nález zprávy o vytvoření orloje Starého Města r. 1410*, Zprávy Komise pro dějiny přírodních, lékařských a technických věd ČSAV **10**, 1962, s. 21–24 | `PCXNHQ8T` (fulltext v poznámce) | popis rukopisu 7916 („51 listů"), datace; klíč k otázce chybějících listů. |
| **Horský 1988** | Z. Horský, *Pražský orloj*, Praha: Panorama 1988 | `EJZ42CCC` (bez fulltextu) | OCR z tištěné knihy; zvl. s. 106–108 (oprava 1659) a popis rukopisu ~s. 137. |
| **Horský – Procházka 1964** | Z. Horský – E. Procházka, *Pražský orloj*, 1964 | `R68FP2W8` (PDF, jen EN résumé) | zaindexovat aspoň résumé; česká verze k dohledání. |
| **Skála (astroláb)** | P. Skála, *Vývoj podoby astrolábu pražského orloje* (studie ČSH / orloj.eu) | `I9RFMMK9` | fulltext z Zotero; rozbor astrolábu, opravy, ikonografie. |
| **Rosický 1923** | V. Rosický, *Staroměstský orloj v Praze*, 1923 | `7MXHCXS6` | posloupnost správců orloje (Švorcpachové, Klein); v indexu jen 2 náhodné zásahy → plný text chybí. |
| **Ritter 1613** | F. Ritter, *Astrolabium*, Norimberk 1613 | `G5BF8DBZ` (attach. `NMY7GVWH`, bez OCR těla) | předloha Astrolabia parvum (f70–79); e-rara/ETH Zürich. OCR německého originálu by umožnil přímou kolaci v indexu. |
| **Hájek — tabule/minuce** | Tadeáš Hájek z Hájku, *Tabule dlúhosti dne a noci k spravování orloje* (1574) + dochované minuce | `T8DSJXZT` (tabule) | předloha f3; Knihopis tabuli nevede (f3 = patrně unikát). Stub + odkaz na docs/hajek-tabule-orloje-1574.md. |

## Kontext (proč to indexujeme)

- Edice orlojní knihy (AHMP, Sbírka rukopisů, inv. č. 7916) — viz `csh-cz/orloj-edice`,
  `docs/` a `ATRIBUCE_1587.md` v `~/Developer/KrakenOCR/writer_id/`.
- Index `orloj-zaznamy` (6 ručně autopsovaných primárních záznamů 1366–1410) je jádro; tyto
  sekundární zdroje k němu mají doplnit dohledatelnou literaturu (datace, posloupnost správců,
  předlohy, popisy rukopisu).
- Otevřené badatelské otázky, jimž indexace pomůže: **identita pisatelů C (~1641–42) a D (1689)**
  (kandidáti Švorcpach, Miller; viz `docs/handoff-identita-pisatelu-CD.md`), **chybějící listy**
  rukopisu (viz `docs/chybejici-listy.md`), **předlohy** f3 (Hájek 1574) a f70–79 (Ritter 1613).
