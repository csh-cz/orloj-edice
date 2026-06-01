<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: EUPL-1.2
-->

# transcribus

Automatizovaná pipeline pro zpracování archiválií: **stažení skenů z archivu →
upload na Transkribus → HTR → stažení a vyčištění přepisu → (později) překlad**.

První podporovaný archiv je **AHMP** (Archiv hlavního města Prahy, katalog na
Bach VadeMeCum se Zoomify prohlížečem). HTR běží přes **Transkribus Metagrapho
API** (`processing/v1`): obrázek dovnitř (base64) → PAGE XML ven, bez správy
kolekcí/dokumentů. API kredity stojí o ~50 % méně než UI kredity. Přihlášení je
přes readcoop SSO (OAuth2, Bearer token). Žádný scraping prohlížeče není potřeba.

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

- AHMP Zoomify mapping (`src/transcribus/sources/ahmp.py`) je postaven na
  ověřeném vzoru Bach VadeMeCum, ale přesné URL pro `Zoomify.action` se finalizují
  proti jednomu živému permalinku — viz docstring v modulu.
- Transkribus klient cílí na Metagrapho `processing/v1` (ověřeno proti veřejnému
  OpenAPI). Login (`transcribus login`) stojí 0 kreditů; kredity čerpá teprve
  `POST /processes` za stránku.
- `htrId` / `lineDetection.modelId` se zadávají ručně — Metagrapho nemá endpoint
  pro výpis modelů; ID se berou z katalogu modelů na webu Transkribusu.
- Překlad je zatím no-op (`processing/translate.py`); vrstva je připravená jako
  pluggable krok (Claude / DeepL).

## Testy

```bash
pytest
ruff check .
```

## Licence

EUPL-1.2. Autor: David Knespl.
