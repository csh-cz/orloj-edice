# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Generate a static HTML edition (one file per folio) from PAGE XML.

Features:
  - page-per-folio (index.html + pNNNN.html) with prev/next + keyboard nav
  - view modes: Diplomatický / Normalizovaný / Teige (srovnání)
  - structure-aware rendering: regions typed marginalia / heading are placed
    accordingly (falls back to paragraph when untagged)
  - images are not republished — each page links out to the AHMP viewer
  - Teige (1570) passage shown side-by-side via best-effort alignment

Shared CSS/JS live under edition/assets/.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from transcribus.processing.normalize import normalize_text
from transcribus.processing.page_xml import Table, TextRegion, parse_page_xml, parse_tables
from transcribus.processing.teige import TeigeIndex, fold

_MARGINALIA = {"marginalia", "margin-text", "margin"}
_HEADING = {"heading", "header", "title", "caption"}

_SECTION_LABEL = {
    "taborsky": "Opis Táborského zprávy o orloji",
    "jine": "Další části knihy (bez referenční edice)",
}
_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def derive_sections(
    matched: set[int], total: int, *, gap: int = 2
) -> list[tuple[str, int, int, str]]:
    """Group folios into sections from the Teige-match blocks.

    Contiguous matched folios (small gaps bridged) form a Táborský section; the
    stretches between them are 'other writings'. Returns (kind, lo, hi, label).
    """
    # Merge matched folios into intervals, bridging gaps <= ``gap``.
    intervals: list[list[int]] = []
    for n in sorted(matched):
        if intervals and n - intervals[-1][1] <= gap + 1:
            intervals[-1][1] = n
        else:
            intervals.append([n, n])

    sections: list[tuple[str, int, int]] = []
    cur = 1
    for lo, hi in intervals:
        if cur < lo:
            sections.append(("jine", cur, lo - 1))
        sections.append(("taborsky", lo, hi))
        cur = hi + 1
    if cur <= total:
        sections.append(("jine", cur, total))
    if not intervals:
        sections = [("jine", 1, total)]

    out: list[tuple[str, int, int, str]] = []
    for i, (kind, lo, hi) in enumerate(sections, start=1):
        label = f"Oddíl {_ROMAN[i] if i < len(_ROMAN) else i} — {_SECTION_LABEL[kind]}"
        out.append((kind, lo, hi, label))
    return out


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _line_html(line: str) -> str:
    return (
        '<span class="ln">'
        f'<span class="dipl">{_esc(line)}</span>'
        f'<span class="norm">{_esc(normalize_text(line))}</span>'
        "</span>"
    )


def _region_html(region: TextRegion) -> str:
    inner = "\n".join(_line_html(line) for line in region.lines if line)
    if not inner:
        return ""
    if region.rtype in _MARGINALIA:
        return f'<aside class="region marginalia">{inner}</aside>'
    if region.rtype in _HEADING:
        return f'<h3 class="region heading">{inner}</h3>'
    return f'<p class="region paragraph">{inner}</p>'


def _table_html(table: Table) -> str:
    """Render a TableRegion as an HTML <table>, honouring row/col spans."""
    by_pos = {(c.row, c.col): c for c in table.cells}
    occupied: set[tuple[int, int]] = set()
    rows_html = []
    for r in range(table.n_rows()):
        tds = []
        for c in range(table.n_cols()):
            if (r, c) in occupied:
                continue
            cell = by_pos.get((r, c))
            if cell is None:
                tds.append("<td></td>")
                continue
            for dr in range(cell.row_span):
                for dc in range(cell.col_span):
                    occupied.add((r + dr, c + dc))
            span = ""
            if cell.row_span > 1:
                span += f' rowspan="{cell.row_span}"'
            if cell.col_span > 1:
                span += f' colspan="{cell.col_span}"'
            tds.append(f"<td{span}>{_esc(cell.text)}</td>")
        rows_html.append("<tr>" + "".join(tds) + "</tr>")
    return '<table class="page-table">' + "".join(rows_html) + "</table>"


def _teige_html(passage: str | None, page_folded: set[str]) -> str:
    if not passage:
        return (
            '<div class="teige-empty">Mimo Táborského zprávu — tato část knihy '
            "nemá referenční edici (Teige vydal pouze Táborského text).</div>"
        )
    out = []
    for token in passage.split(" "):
        f = fold(token)
        cls = "hit" if f and f in page_folded else ""
        out.append(f'<span class="{cls}">{_esc(token)}</span>' if cls else _esc(token))
    return '<div class="teige-text">' + " ".join(out) + "</div>"


def _page_doc(
    *, title: str, page_nr: int, total: int, regions: list[TextRegion],
    ahmp_url: str | None, teige_passage: str | None, section_label: str = "",
    tables: list[Table] | None = None, figures: list[str] | None = None,
    clean_lines: list[str] | None = None, embed_scan: bool = False,
) -> str:
    tables = tables or []
    figures = figures or []
    has_text = any(r.lines and any(line.strip() for line in r.lines) for r in regions)
    has_content = has_text or bool(tables) or bool(figures) or bool(clean_lines)
    # AHMP rules: any internet publication of a reproduction needs an agreement +
    # <=500px + watermark. Until that is in place, NOTHING is republished — figures are
    # only referenced with an out-link to the AHMP viewer.
    fig_link = (
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">sken v AHMP</a>'
        if ahmp_url else "sken v AHMP"
    )
    fig_note = (
        f'<figure class="fig fig-ref"><figcaption>Na tomto foliu je vyobrazení '
        f"(zde nereprodukováno — viz {fig_link}).</figcaption></figure>"
        if figures else ""
    )
    prev_link = f"p{page_nr-1:04d}.html" if page_nr > 1 else ""
    next_link = f"p{page_nr+1:04d}.html" if page_nr < total else ""
    ahmp = (
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">↗ sken v AHMP</a>'
        if ahmp_url else ""
    )
    # Optional embedded AHMP viewer (iframe = linking, not republication). Collapsed by
    # default; the scan is served & watermarked by AHMP. Toggle via --embed-scan.
    scan_embed = (
        '<details class="scan-embed"><summary>▣ Zobrazit sken folia z AHMP</summary>'
        f'<iframe src="{_esc(ahmp_url)}" loading="lazy" '
        f'title="Sken fol. {page_nr:04d} — Archiv hl. m. Prahy" '
        'referrerpolicy="no-referrer-when-downgrade"></iframe>'
        '<p class="scan-note">Sken hostuje a vodoznakem značí Archiv hlavního města Prahy. '
        'Nenačte-li se náhled (blokované cookies třetích stran), použij odkaz '
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">↗ otevřít v AHMP</a>.</p>'
        "</details>"
        if (embed_scan and ahmp_url) else ""
    )

    if has_content:
        # Precedence: corrected clean text > Docling table grid > raw per-line HTR.
        if clean_lines:
            body_regions = (
                '<span class="clean-flag">opravený přepis</span><p class="region paragraph">'
                + "\n".join(_line_html(line) for line in clean_lines if line)
                + "</p>"
            )
        elif tables:
            body_regions = "".join(_table_html(t) for t in tables)
        else:
            body_regions = "\n".join(_region_html(r) for r in regions)
        page_folded = {
            fold(w) for r in regions for line in r.lines for w in line.split() if len(fold(w)) >= 4
        }
        teige = _teige_html(teige_passage, page_folded)
        body = (
            f'<div class="folio">{fig_note}{body_regions}</div>'
            f'<div class="teige-pane"><div class="teige-label">Teige (1570), přibližné zarovnání</div>{teige}</div>'
        )
    else:
        body = '<div class="empty">[prázdná strana / vazba]</div>'

    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fol. {page_nr:04d} — {_esc(title)}</title>
<link rel="stylesheet" href="assets/edition.css"></head>
<body class="mode-dipl">
<header>
  <a class="home" href="index.html">≡</a>
  <h1>{_esc(title)}</h1>
  <div class="modes">
    <label><input type="radio" name="mode" value="dipl" checked> Diplomatický</label>
    <label><input type="radio" name="mode" value="norm"> Normalizovaný</label>
    <label><input type="radio" name="mode" value="teige"> Teige</label>
  </div>
</header>
<nav class="pager">
  <a class="prev" href="{prev_link}"{'' if prev_link else ' hidden'}>← předchozí</a>
  <span class="folno">fol. {page_nr:04d} / {total:04d} &nbsp; {ahmp}</span>
  <a class="next" href="{next_link}"{'' if next_link else ' hidden'}>další →</a>
</nav>
<div class="section-label">{_esc(section_label)}</div>
<main>{body}{scan_embed}</main>
<footer>Diplomatický přepis (Transkribus HTR, model 263129). Normalizace heuristická — nutná korektura.
Teige: edice 1901, public domain. Vyobrazení ani skeny se zde nereprodukují — odkazy „sken"
vedou do prohlížeče Archivu hlavního města Prahy (katalog.ahmp.cz).</footer>
<script src="assets/edition.js"></script>
</body></html>"""


_BADGE = (
    ' <span class="teige-badge" title="Táborského zpráva — referenční edice Teige">T</span>'
)


def _toc_item(n: int, snip: str, teige: bool) -> str:
    badge = _BADGE if teige else ""
    return (
        f'<li><a href="p{n:04d}.html">fol. {n:04d}</a>{badge} '
        f'<span class="snip">{_esc(snip)}</span></li>'
    )


# Stav zpracování po částech knihy. Průběžně se aktualizuje (edit → regenerace → deploy).
# klíč stavu: done = hotový čistý přepis · partial = rozpracováno · todo = chybí · na = prázdná
_STATUS_ROWS: list[tuple[str, str, str, str]] = [
    ("f1", "předsádka", "na", "—"),
    ("f2–f3", "úvodní astronomické tabulky", "todo", "tabulky (Docling)"),
    ("f4", "latinský verš", "todo", "přepis"),
    ("f5–f12", "Táborský: verš, dedikace, kap. I–VI", "done", "drobná [?] místa"),
    ("f13–f30", "Táborský: kap. VI–XIII", "done", "marginálie neověřené ze skenu"),
    ("f31–f42", "Táborský: kap. XIII–XVIII", "partial",
     "Teige-ukotveno; diplomatická kontrola po řádcích"),
    ("f43–f49", "Táborský: biografický závěr, verše, kolofony 1570 + 1587", "done", "—"),
    ("f50", "komputistická tabulka", "todo", "tabulka (Docling)"),
    ("f51–f52", "List purkmistra 1410 (něm., opsáno 1628)", "done", "—"),
    ("f53–f54", "List purkmistra — dobový český překlad", "done", "f54: pokrač. něm. návod"),
    ("f55–f69", "komputistické/astron. tabulky + próza (f65)", "todo",
     "tabulky (Docling) + próza f65"),
    ("f70–f79", "Astrolabium parvum", "done", "—"),
    ("f80", "latinsko-český epigram (Pythagoras)", "todo", "přepis"),
    ("f81", "předsádka", "na", "—"),
]
_STATUS_BADGE = {
    "done": '<span class="b-done">✅ hotovo</span>',
    "partial": '<span class="b-partial">🔶 rozpracováno</span>',
    "todo": '<span class="b-todo">❌ chybí</span>',
    "na": '<span class="b-na">— prázdná</span>',
}


def _status_html() -> str:
    rows = "".join(
        f"<tr><td>{_esc(fol)}</td><td>{_esc(part)}</td>"
        f"<td>{_STATUS_BADGE.get(st, _esc(st))}</td><td>{_esc(rest)}</td></tr>"
        for fol, part, st, rest in _STATUS_ROWS
    )
    return (
        '<table class="status"><caption>Stav zpracování (průběžně aktualizováno)</caption>'
        "<thead><tr><th>folia</th><th>část knihy</th><th>stav</th><th>zbývá</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _index_doc(
    title: str,
    sections: list[tuple[str, int, int, str]],
    pages: dict[int, tuple[str, bool]],
    ahmp_permalink: str | None = None,
) -> str:
    ahmp_a = (
        f'<a href="{_esc(ahmp_permalink)}" target="_blank" rel="noopener">'
        "záznam a skeny v katalogu AHMP ↗</a>"
        if ahmp_permalink else "katalog AHMP"
    )
    tiraz = (
        '<section class="tiraz"><h2>O edici</h2>'
        "<p><b>Pramen — jedna svázaná orlojní kniha (zápisy z let 1587–1642).</b> Archiv "
        f"hlavního města Prahy, Sbírka rukopisů, inv. č. 7916. {ahmp_a}. Nejde o soubor volně "
        "vložených listů: ohledáním archiválie bylo ověřeno, že je to <b>jediný svázaný celek</b> "
        "a že zápisy vznikaly postupně na <b>předem svázané archy</b> — pořadí zápisů tedy odpovídá "
        "chronologii. Díky tomu jsou <b>datovatelné i pozdější přípisky správců orloje</b>; právě "
        "na nich stojí přeřazení vzniku orloje k r. 1410 (Z. Horský). Kniha má několik částí: "
        "(1) <b>opis Táborského <i>Zprávy o orloji pražském</i></b> (fol. 5–49), který roku "
        "1587 pořídil staroměstský písař <b>Matouš Carchesius Jablonský</b> (kolofon fol. 47); "
        "(2) <b>opis Listu purkmistra z r. 1410</b> (de facto smlouva Starého Města s hodinářem "
        "Mikulášem z Kadaně na zhotovení orloje) — německy (fol. 51–52, opsáno 1628) i v dobovém "
        "českém překladu (fol. 53–54); (3) "
        "<b>komputistické a astronomické tabulky</b> (fol. 2, 50, 55–69 — Littera dominicalis, "
        "zlaté číslo, epakta, východ slunce, polouorlojní počet); (4) <b>Astrolabium parvum</b> "
        "(fol. 70–79); a (5) <b>pozdější přípisky správců orloje</b> (16.–17. stol.). Edice "
        "zatím zpracovává především část (1) a (2).</p>"
        "<p><b>Metoda — syntetická edice.</b> Text vzniká <b>kombinací zdrojů</b>, ne pouhým "
        "strojovým přepisem: strojové rozpoznání rukopisu (HTR, Transkribus PyLaia — čeština "
        "263129, německý Kurrent 27457; dva nezávislé běhy), ruční korektura čtením skenu, "
        "rozpoznání tabulek (Docling TableFormer) a externí opory — edice originálu 1570 "
        "(J. Teige, 1901), paleografický přepis Listu purkmistra a přepis Astrolabia (orloj.eu). "
        "Výsledek je tedy <b>syntéza</b> více pramenů. Česky psaný text lze zobrazit ve třech "
        "režimech: diplomatický / normalizovaný (diakritický, dle normy Ivan Šťovíček a kol.) / "
        "Teige.</p>"
        '<p class="teige"><b>Pozor na Teigeho — předloha ≠ opis.</b> Teigeho edice (1901) vydává '
        "<b>předlohu, totiž originál Táborského zprávy z r. 1570</b>. Zde se ale zpracovává její "
        "<b>opis Jablonského z r. 1587</b> — <b>jiný svědek</b>, který se od originálu místy liší "
        "(varianty písaře i pozdější přídavky: např. přestavba měsícového soukolí, kolofon "
        "opisovače 1587, „přídavek na spheru“, poznámky správců odkazující na List purkmistra 1410). "
        "Proto se text <b>neopravuje podle Teigeho</b>: Teige slouží jen jako <b>čtecí opora a "
        "kolace</b> a <b>odlišnosti opisu se záměrně zachovávají</b> (a značí), nikoli zarovnávají "
        "na originál.</p>"
        '<p class="warn"><b>Stav: rozpracovaná pracovní edice.</b> Normalizace je heuristická a '
        "vyžaduje korekturu; část přípisků na okraji (fol. 13–30) není ověřena proti skenu; oddíl "
        "fol. 31–42 je čtecí oporou ukotven na Teigem. Zatím neslouží jako citovatelná kritická "
        "edice.</p>"
        '<p><b>Práva a licence:</b> skeny ani vyobrazení se zde nereprodukují — odkazy „sken" '
        "vedou do prohlížeče AHMP (práva k reprodukcím: Archiv hlavního města Prahy). "
        "Text edice © David Knespl, licence CC&nbsp;BY&nbsp;4.0; software EUPL-1.2.</p></section>"
    )
    blocks = []
    for _kind, lo, hi, label in sections:
        items = "\n".join(
            _toc_item(n, pages[n][0], pages[n][1]) for n in range(lo, hi + 1) if n in pages
        )
        blocks.append(
            f'<section class="toc-section"><h2>{_esc(label)} '
            f'<span class="range">(fol. {lo:04d}–{hi:04d})</span></h2>'
            f'<ol class="toc">{items}</ol></section>'
        )
    n_teige = sum(1 for v in pages.values() if v[1])
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><link rel="stylesheet" href="assets/edition.css"></head>
<body class="mode-dipl">
<header><h1>{_esc(title)}</h1></header>
<main>
{_status_html()}
{tiraz}
<p class="note">Jedna svázaná kniha (více částí, jeden celek). <span class="teige-badge">T</span> = folia s opisem
Táborského zprávy, kde existuje referenční edice (Teige 1901); ostatní oddíly referenci nemají.
Označeno {n_teige} z {len(pages)} folií. Hranice oddílů jsou odvozené automaticky (heuristika).</p>
{"".join(blocks)}</main>
<footer>{len(pages)} folií. Diplomatická edice z Transkribus HTR.</footer>
</body></html>"""


_CSS = """
:root{--ink:#2b2b2b;--paper:#f7f3ea;--accent:#7a5c2e;}
*{box-sizing:border-box}
body{margin:0;font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:#e9e3d6}
header{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid #cdbf9f;
  padding:.5rem 1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
header h1{font-size:1rem;margin:0;flex:1 1 auto}
header .home{font-size:1.3rem;text-decoration:none;color:var(--accent)}
.modes label{margin-right:.7rem;cursor:pointer;font-family:system-ui,sans-serif;font-size:.82rem}
.pager{max-width:62rem;margin:.6rem auto 0;padding:0 1rem;display:flex;justify-content:space-between;
  align-items:center;font-family:system-ui,sans-serif;font-size:.85rem}
.pager a{color:var(--accent);text-decoration:none}
.pager .folno{color:#6b6256}
.pager a[hidden]{visibility:hidden}
main{max-width:62rem;margin:1rem auto 3rem;padding:0 1rem}
.folio{background:var(--paper);border:1px solid #cdbf9f;border-radius:4px;padding:1.2rem 1.6rem;
  box-shadow:0 1px 3px rgba(0,0,0,.12)}
.region{margin:0 0 .6rem}
.ln{display:block;line-height:1.6}
.heading{font-size:1.05rem;font-weight:bold}
.marginalia{float:right;width:32%;margin:0 0 .4rem 1rem;padding-left:.6rem;border-left:2px solid #cdbf9f;
  color:#5a5446;font-size:.9em;font-style:italic}
.page-table{border-collapse:collapse;margin:.6rem 0;font-family:system-ui,sans-serif;font-size:.85rem}
.page-table td{border:1px solid #cdbf9f;padding:.15rem .4rem;text-align:center;min-width:1.6rem}
.clean-flag{display:inline-block;background:#3f6b3f;color:#fff;font-family:system-ui,sans-serif;
  font-size:.65rem;border-radius:3px;padding:0 .35rem;margin-bottom:.4rem}
.fig{margin:0 0 1rem;text-align:center}
.fig img{max-width:100%;height:auto;border:1px solid #cdbf9f;border-radius:3px}
.fig figcaption{font-family:system-ui,sans-serif;font-size:.75rem;color:#6b6256;margin-top:.3rem}
.fig figcaption a{color:#7a5c2e}
.scan-embed{max-width:62rem;margin:1.5rem auto;font-family:system-ui,sans-serif;font-size:.8rem}
.scan-embed summary{cursor:pointer;color:#7a5c2e;padding:.4rem .6rem;background:#f3ecdb;
  border:1px solid #cdbf9f;border-radius:4px;user-select:none}
.scan-embed iframe{width:100%;height:80vh;margin-top:.6rem;border:1px solid #cdbf9f;border-radius:3px}
.scan-embed .scan-note{color:#6b6256;font-size:.72rem;margin:.4rem 0 0}
.empty{color:#a99;font-style:italic;font-family:system-ui,sans-serif;padding:1rem}
/* mode switching */
.norm{display:none}
body.mode-norm .dipl{display:none}
body.mode-norm .norm{display:inline}
.teige-pane{display:none}
body.mode-teige .teige-pane{display:block;margin-top:1rem;background:#fff;border:1px solid #cdbf9f;
  border-radius:4px;padding:1rem 1.4rem}
.teige-label{font-family:system-ui,sans-serif;font-size:.75rem;color:#6b6256;margin-bottom:.4rem;
  text-transform:uppercase;letter-spacing:.05em}
.teige-text{line-height:1.6;color:#444}
.teige-text .hit{background:#eef3d8}
.teige-empty{color:#a99;font-style:italic}
.section-label{max-width:62rem;margin:.3rem auto 0;padding:0 1rem;font-family:system-ui,sans-serif;
  font-size:.78rem;color:#7a5c2e;text-transform:uppercase;letter-spacing:.04em}
.tiraz{font-family:system-ui,sans-serif;font-size:.85rem;line-height:1.5;background:#f6f1e4;
  border:1px solid #cdbf9f;border-radius:5px;padding:.8rem 1.1rem;margin:0 0 1.4rem}
.tiraz h2{font-size:1rem;margin:.1rem 0 .5rem;border:0}
.tiraz p{margin:.4rem 0}
.tiraz .warn{background:#fbeed6;border-left:3px solid #b8860b;padding:.4rem .6rem;border-radius:3px}
.tiraz .teige{background:#eef1f6;border-left:3px solid #5a6b8c;padding:.4rem .6rem;border-radius:3px}
.tiraz a{color:#7a5c2e}
.status{font-family:system-ui,sans-serif;font-size:.82rem;border-collapse:collapse;width:100%;margin:0 0 1.4rem}
.status caption{text-align:left;font-weight:bold;font-size:1rem;margin-bottom:.4rem;color:#3a342a}
.status th,.status td{border:1px solid #cdbf9f;padding:.3rem .55rem;text-align:left;vertical-align:top}
.status th{background:#efe7d3}
.status tbody tr:nth-child(even){background:#faf6ec}
.status .b-done{color:#2e7d32;font-weight:bold;white-space:nowrap}
.status .b-partial{color:#b8860b;font-weight:bold;white-space:nowrap}
.status .b-todo{color:#a3332b;font-weight:bold;white-space:nowrap}
.status .b-na{color:#999;white-space:nowrap}
.toc-section h2{font-size:1rem;border-bottom:1px solid #cdbf9f;padding-bottom:.2rem;margin:1.4rem 0 .4rem}
.toc-section h2 .range{font-weight:normal;color:#8a8071;font-size:.85rem}
.note{font-family:system-ui,sans-serif;font-size:.85rem;color:#5a5446;background:var(--paper);
  border:1px solid #cdbf9f;border-radius:4px;padding:.6rem .9rem;max-width:62rem}
.teige-badge{display:inline-block;background:#7a5c2e;color:#fff;font-family:system-ui,sans-serif;
  font-size:.65rem;font-weight:bold;border-radius:3px;padding:0 .3rem;vertical-align:middle}
.toc{font-family:system-ui,sans-serif;font-size:.9rem;columns:2;gap:2rem;margin-top:1rem}
.toc li{margin:.15rem 0}
.toc .snip{color:#8a8071}
footer{max-width:62rem;margin:0 auto;text-align:center;color:#6b6256;font-size:.72rem;padding:1.5rem;
  font-family:system-ui,sans-serif}
"""

_JS = """
(function(){
  function apply(m){document.body.className='mode-'+m;
    for(const r of document.querySelectorAll('input[name=mode]'))r.checked=(r.value===m);
    try{localStorage.setItem('edmode',m)}catch(e){}}
  const saved=(function(){try{return localStorage.getItem('edmode')}catch(e){return null}})();
  document.addEventListener('DOMContentLoaded',function(){
    if(saved)apply(saved);
    for(const r of document.querySelectorAll('input[name=mode]'))
      r.addEventListener('change',()=>apply(r.value));
    document.addEventListener('keydown',function(e){
      if(e.target.tagName==='INPUT')return;
      if(e.key==='ArrowLeft'){const a=document.querySelector('.pager .prev');if(a&&!a.hidden)location.href=a.getAttribute('href');}
      if(e.key==='ArrowRight'){const a=document.querySelector('.pager .next');if(a&&!a.hidden)location.href=a.getAttribute('href');}
    });
  });
})();
"""


def _folio_ahmp_url(permalink: str | None, page_nr: int) -> str | None:
    """Per-folio stable link to the scan in the AHMP viewer.

    Appends ``scanIndex=<folio>`` to the document permalink. The bare permalink always
    opens the correct unit in the AHMP viewer; the viewer may deep-link to the folio
    via scanIndex (client-side). Scans are not republished here.
    """
    if not permalink:
        return None
    sep = "&" if "?" in permalink else "?"
    return f"{permalink}{sep}scanIndex={page_nr}"


def build_edition(
    work_dir: Path, *, title: str, ahmp_permalink: str | None = None,
    teige_path: Path | None = None, embed_scan: bool = False,
) -> Path:
    work_dir = Path(work_dir)
    xml_files = sorted((work_dir / "page_xml").glob("*.xml"))
    if not xml_files:
        raise RuntimeError(f"No PAGE XML in {work_dir / 'page_xml'}; run HTR/export first.")

    if ahmp_permalink is None:
        state = work_dir / "state.json"
        if state.exists():
            ref = json.loads(state.read_text(encoding="utf-8")).get("ref", "")
            if ref.startswith("http"):
                ahmp_permalink = ref

    teige_index: TeigeIndex | None = None
    if teige_path and Path(teige_path).exists():
        teige_index = TeigeIndex(Path(teige_path).read_text(encoding="utf-8"))

    out_dir = work_dir / "edition"
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    (out_dir / "assets" / "edition.css").write_text(_CSS, encoding="utf-8")
    (out_dir / "assets" / "edition.js").write_text(_JS, encoding="utf-8")

    total = len(xml_files)
    # Pass 1: parse pages, tables, and compute Teige matches.
    entries: list[
        tuple[int, list[TextRegion], list[Table], str, str | None, list[str], list[str]]
    ] = []
    tables_dir = work_dir / "tables"
    figures_dir = work_dir / "figures"
    for xf in xml_files:
        page_nr = int(xf.stem)
        xml = xf.read_text(encoding="utf-8")
        regions = parse_page_xml(xml)
        tables = parse_tables(xml)
        # Docling table sidecar (TableFormer) takes precedence when present.
        sidecar = tables_dir / f"{page_nr:04d}.json"
        if sidecar.exists():
            from transcribus.processing.docling_tables import tables_from_json

            docling_tables = tables_from_json(sidecar.read_text(encoding="utf-8"))
            if docling_tables:
                tables = docling_tables
        fig_sidecar = figures_dir / f"{page_nr:04d}.json"
        fig_names = json.loads(fig_sidecar.read_text()) if fig_sidecar.exists() else []
        clean_file = work_dir / "clean" / f"{page_nr:04d}.txt"
        clean_lines = (
            [ln for ln in clean_file.read_text(encoding="utf-8").splitlines()]
            if clean_file.exists() else []
        )
        plain = " ".join(line for r in regions for line in r.lines if line.strip())
        passage = teige_index.align(plain) if (teige_index and plain) else None
        entries.append((page_nr, regions, tables, plain, passage, fig_names, clean_lines))

    matched = {e[0] for e in entries if e[4]}
    sections = derive_sections(matched, total)
    folio_section = {n: label for _k, lo, hi, label in sections for n in range(lo, hi + 1)}

    # NOTE: no AHMP reproduction is republished (figures or whole pages) — each folio
    # only links out to the AHMP viewer. Embedding would require an AHMP agreement
    # (<=500px longer side + watermark + "internet" purpose stated in the contract).

    # Pass 2: write per-folio pages + index.
    toc: dict[int, tuple[str, bool]] = {}
    for page_nr, regions, tables, plain, passage, fig_names, clean_lines in entries:
        doc = _page_doc(
            title=title, page_nr=page_nr, total=total, regions=regions,
            ahmp_url=_folio_ahmp_url(ahmp_permalink, page_nr), teige_passage=passage,
            section_label=folio_section.get(page_nr, ""), tables=tables, figures=fig_names,
            clean_lines=clean_lines, embed_scan=embed_scan,
        )
        (out_dir / f"p{page_nr:04d}.html").write_text(doc, encoding="utf-8")
        snip = (plain[:80] + "…") if plain else (
            "[tabulka]" if tables else ("[vyobrazení]" if fig_names else "[prázdná]")
        )
        toc[page_nr] = (snip, passage is not None)

    index = out_dir / "index.html"
    index.write_text(_index_doc(title, sections, toc, ahmp_permalink), encoding="utf-8")
    return index
