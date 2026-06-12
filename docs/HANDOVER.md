<!--
SPDX-FileCopyrightText: 2026 David Knespl
SPDX-License-Identifier: CC-BY-4.0
-->

# HANDOVER — session „Orlojní kniha" (stav k 2026-06-12)

Pokračování práce na digitální edici orlojní knihy. Tento soubor = kontext pro novou
session. Po přečtení smaž/aktualizuj.

## Co je tento projekt

- **Edice orlojní knihy** (AHMP, Sbírka rukopisů, inv. č. 7916; permalink
  `xid=E1BD466FB72711DF820F00166F1163D4`) — konvolut 1587–1689, čtyři písařské ruce
  (A=Carchesius 1587, B=Mikuláš Petr 1628, C=orlojník-astronom ~1641–42, D=1689).
- **Live:** <https://csh-cz.github.io/orloj-edice/> · deploy: `./deploy.sh` (force-push
  gh-pages). Repo = GitHub `csh-cz/orloj-edice`, **push na main OK** (sole maintainer),
  commit trailer `Co-Authored-By: Claude <model> <noreply@anthropic.com>`.
- Jazyk: čeština v chatu; kód/commity anglicky. Uživatel = David Knespl.

## Klíčová místa v repu

- `work/orloj1587/clean/*.txt` + `tables_clean/*.json` — **ručně korigovaný zdroj edice,
  VERZOVÁNO v gitu** (zbytek work/ ignorován). Konvence v clean: `[Ediční pozn.: …]` →
  rozbalovací aparát (blok končí prázdnou řádkou!); `[Překlad: …]` → **in-flow překladový
  blok** (plná šířka, zelený proužek); `* * *` → oddělovač textů (hr ✦); `[přípisy na
  okraji:]` → marginálie.
- `src/transcribus/processing/edition.py` — **engine** (render, CSS, JS; 1609 ř.);
  `edition_content.py` — **obsah** (popisky, poznámky, _STATUS_ROWS, _SECTIONS_1587,
  _PENCIL_FOLIO, _MISSING_BEFORE…). POZOR na rovné uvozovky v Py stringách (→ „").
- `tools/verify_*.py` (komputus, astroláb 1642, epakty f68, f54) — vše prochází;
  `tools/collate_carchesius_teige.py` + `collate_1587_1570.py` → výstupy
  `work/orloj1587/collation_*.{json,md}`.
- `docs/`: `hajek-tabule-orloje-1574.md` (f3 = opis Hájkovy tabule 1574, Knihopis ji
  nevede → f3 patrně unikátní svědek), `handoff-identita-pisatelu-CD.md` (prompt pro
  archivního agenta), `transkripce.md`.
- Testy: `pytest` 23/23, `ruff` čistý. Teige režim jen f5–49; kurátorované oddíly jen
  pro slug „1587".
- Sousední repo `~/Developer/KrakenOCR/writer_id/` (vlastní git): cluster_hands.py,
  ATRIBUCE_1587.md (autoritativní atribuce), NAVRH_vylepseni.md (Tier 1–3, neimpl.).

## Čerstvě hotovo (tato session, vše commitnuto+pushnuto, HEAD=687cc9e+)

- f54 němčina **přečtena ze skenu řádek po řádku** (klíč: „die mittlere Zahl duplirn" =
  délka dne zdvojením doplňku; lapsus „Untergang" [!]; „34" nad škrtem). Render: němčina
  jako číslovaný text za kolofonem, oddělovač, aparát dole.
- **Doslovné in-flow překlady všech cizojazyčných pasáží**: f4, f51, f52, f54 (2×), f62
  (lat. verš), f80 (2×) — 8 bloků, plná šířka.
- **Stará tužková foliace** přečtena ze skenů → `_PENCIL_FOLIO` (hlavička „st. fol. N";
  čísluje LISTY na rectech). Doplněno uživatelem: f56=35, f58=36.
- **Objev: chybějí listy** st. fol. **33–34** (mezi f55/f56) a **42–45** (mezi f68/f70).
  Bannery na f56/f70 (`_MISSING_BEFORE`) vč. **hypotézy středních dvojlistů**: 33+34 =
  nejvnitřnější dvojlist své složky; 42–45 = DVA nejvnitřnější dvojlisty kvaternu listů
  40–47 (vnější 40,41,46,47 vše dochováno). Predikce: žádné pahýly v hřbetu.
- Infra: clean/tables_clean verzovány; obsah/engine split; testy opraveny; README+TODO
  osvěženy; opravy: 1684→**1689** (f3, M·DC·LXXXIX), „List purkmistra" sg., „pisatelé"
  místo „orlojníci", medailon Mikuláše Petra na f52 (nar. ~1589, písař hořejší kanceláře,
  pramen PPL I–451 / Teige Místopis I/1 s. 285).

## ROZDĚLANÉ — okamžité další kroky (uživatel řekl „napiš si handover, restartuji")

1. **Rešerše „jsou vypadlé listy publikované?" — dokončeno zjištění, NEZAPSÁNO:**
   - Macháček 1962 (Zotero `PCXNHQ8T`, fulltext v note): výpadek NEzmiňuje; píše
     „rukopis mající **51 listů**", „Zpráva Táborského končí na **27. listu**" (= naše
     tužková foliace, kolofon 1587 = list 27 = sken f47). 51 ≫ ~46 (stav s výpadkem) →
     **slabá/střední indicie, že listy v 1962 ještě byly** (ale mohl číslo odvodit
     z poslední foliace — neprůkazné).
   - Horský: 1964 máme jen EN résumé (nic); **1988 *Pražský orloj* bez fulltextu —
     ověřit fyzicky** (Skála cituje foto s. 137). Skála (astroláb) foliaci neřeší.
     Katalog AHMP počet ff. neuvádí (a datuje jednotku 1587–1642, 1689 vrstvu nezná).
   - **Závěr: nález je patrně náš + otázka, zda ztráta nenastala až po 1962.**
   - **TODO:** (a) zanést tuto rešerši do docs (nový soubor např.
     `docs/chybejici-listy.md` nebo rozšířit bannery/TODO), (b) doplnit do draftu mailu
     Petrovi odstavec o Macháčkových 51 listech + prosbu ověřit Horský 1988.
2. **Mail Petru Skálovi** — draft hotový v konverzaci (chybějící listy + bifoliová
   hypotéza + prosba o autopsii hřbetu u f55/56 a f68/70 + čelo knihy listy 1–3).
   NEODESLÁN (čeká na adresu/kanál od uživatele). Přidat bod 1b výše.

## Otevřený backlog (z TODO.md)

- ~31 `[?]` (marginálie ruky A f13–45, latina f4, „Jana [?]" f3) — skenový průchod.
- f61 zóna epakty 25 (19/210 buněk) na originále.
- f38 atribuce B vs C; identita pisatelů C a D (handoff prompt připraven).
- Hájek 1574 — dochování (Manuscriptorium/NK ČR ručně); předloha f55 (tabule pólu 50°).
- Kritický variantní aparát z kolací do stránek edice; verza „list N (verso)";
  paleografka Listu purkmistra (kredit); 1570 originál (23 sporných řádků); writer-ID
  Tier 1; eScriptorium GT.

## Pasti / poučení

- Edit tool na edition.py občas selže na whitespace → použít Python replace přes Bash.
- `_clean_block`: ed-note blok končí prázdnou řádkou; každý `[Ediční pozn.]`/`[Pozn.]`
  = samostatný <p>.
- Kolace 1587×Teige ignoruje pravopis (fold) — varianty au/ú, ej/aj jsou GENUINNÍ
  rozdíly 1587×1570 (ověřeno i přímou kolací proti autografu), ne Teigeho normalizace.
- Preview screenshot občas vrací prázdno — ověřovat grep-em HTML.
- f2 = jen nalinkovaná nevyplněná tabule (potvrzeno uživatelem, neřešit).
- Rok f3 = 1689 (IX, ne IV) — definitivně, neměnit.
