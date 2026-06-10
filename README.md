<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: EUPL-1.2
-->

# transcribus

Automatizovaná pipeline pro zpracování archiválií: **stažení skenů z archivu →
upload na Transkribus → HTR → stažení a vyčištění přepisu → (později) překlad**.

První podporovaný archiv je **AHMP** (Archiv hlavního města Prahy, katalog na
Bach VadeMeCum se Zoomify prohlížečem). HTR běží přes **Transkribus TrpServer REST**
(PyLaia modely, např. 263129 pro češtinu): layout → HTR → export PAGE XML. Přihlášení
je přes readcoop SSO (OAuth2, Bearer token; auto-refresh). Žádný scraping prohlížeče
není potřeba.

## Webová edice — Orlojní kniha (opis 1587)

**Živá edice: <https://csh-cz.github.io/orloj-edice/>**

Digitální edice **celé orlojní knihy** pražského orloje (Archiv hlavního města Prahy,
Sbírka rukopisů, inv. č. 7916) — konvolutu, do něhož se psalo přes celé století
(**1587–1689**): opis *Zprávy o orloji pražském* Jana Táborského (1587, písař **Matouš
Carchesius Jablonský**, fol. 5–49), opis **Listu purkmistra 1410** (Mikuláš Petr, 1628),
**komputistické a astronomické tabulky** (~1641–42), **Astrolabium parvum** (český
překlad F. Rittera, ~1642) a opis **Hájkovy tabule délky dne** (1689). Rozlišeny čtyři
písařské ruce (paleografie + writer-ID + obsah/datace).

Metoda: diplomatický přepis (Transkribus HTR) + ruční korektura + heuristická
normalizace (norma Šťovíček) + **kolace proti Teigeho edici 1901 i přímo proti
autografu 1570**; číselné tabulky **deterministicky ověřeny výpočtem** (skripty
v `tools/`). Stará tužková foliace zachována („st. fol."), vyznačeny chybějící listy.
Podrobnosti v úvodu a tiráži edice. **Rozpracovaná pracovní edice.**

Skeny ani vyobrazení se nereprodukují (práva k reprodukcím: AHMP) — edice na ně
odkazuje per folio do prohlížeče AHMP. Nasazení edice: **`./deploy.sh`** (regenerace
bez vložených skenů → publikace na větvi `gh-pages`).

**Zdrojová data edice** (ručně korigované přepisy a dekódované tabulky) jsou verzovaná
v `work/orloj1587/clean/` a `work/orloj1587/tables_clean/`; zbytek `work/` je
regenerovatelný výstup (gitignored). Ediční **obsah** (poznámky, popisky, stavová
tabulka) žije v `src/transcribus/processing/edition_content.py`, renderovací **engine**
v `edition.py`.

## Pipeline

```
acquire (AHMP)  →  recognize (Metagrapho)  →  clean  →  [translate*]
   skeny/JPG       processId → PAGE XML        Markdown   (pluggable)
```

Každý běh má vlastní *work* adresář s `state.json`; běh je idempotentní a
resumovatelný (přeskočí už hotové fáze).

## Instalace

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # doplň TRANSKRIBUS_USER / TRANSKRIBUS_PASSWORD
```

## Použití

```bash
# ověření přihlášení (0 kreditů)
transcribus login                 # z .env
transcribus login --ask-password  # heslo zadáš ručně (neuloží se)

# jen stažení skenů z AHMP (bez Transkribusu)
transcribus acquire "https://katalog.ahmp.cz/pragapublica/permalink?xid=..." --out work/kniha1 --limit 2

# bulk upload skenů přes FTP + ingest jako dokument (ftp://transkribus.eu, login z .env)
transcribus upload-ftp --out work/kniha1 --coll <collId> --folder kniha1

# celá pipeline (model-id = HTR model z katalogu Transkribusu, pylaia engine)
transcribus run "https://katalog.ahmp.cz/pragapublica/permalink?xid=..." \
    --out work/kniha1 --coll <collId> --model-id <modelId>

# HTR na už nahraném dokumentu (layout -> HTR -> export -> clean)
transcribus htr --out work/kniha1 --coll <collId> --doc <docId> --model-id 263129

# statická HTML edice (diplomatický / normalizovaný / Teige režim)
transcribus edition --out work/kniha1 --title "…" [--teige data/teige_taborsky.txt]
```

Výstup: `work/<zakázka>/text/transcript.md` (+ per-page `.txt` a `page_xml/`).

## Stav / TODO

Otevřené úkoly edice: **`TODO.md`** (nejistá čtení, identita pisatelů C/D, chybějící
listy, předloha f55…). Badatelské podklady a handoffy: **`docs/`**. Verifikační a
kolacní skripty: **`tools/`** (`verify_*` — komputus, astroláb 1642, epakty, f54;
`collate_*` — Carchesius × Teige / × autograf 1570; `build_*` — rekonstrukce tabulek).

Poznámky k pipeline:
- Transkribus klient cílí na Metagrapho `processing/v1`; login stojí 0 kreditů,
  kredity čerpá až `POST /processes` za stránku. `htrId` / `modelId` se zadávají
  ručně (z katalogu modelů na webu Transkribusu).
- Překlad je zatím no-op (`processing/translate.py`); vrstva je připravená jako
  pluggable krok.

## Testy

```bash
pytest
ruff check .
```

## Licence

EUPL-1.2. Autor: David Knespl.
