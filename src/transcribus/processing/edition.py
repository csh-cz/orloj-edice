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
import re
from pathlib import Path

from transcribus.processing.edition_content import (  # noqa: F401
    _BINDING_NOTE_1570,
    _F80_TRIANGLE_SVG,
    _FIGURE_SVG,
    _FOLIO_SNIP,
    _MARG_ED,
    _MARG_HIST,
    _MARG_LAT,
    _MISSING_BEFORE,
    _NO_NORMALIZE,
    _PENCIL_FOLIO,
    _SECTIONS_1587,
    _STATUS_ROWS,
    _STATUS_ROWS_1570,
    _TABLE_CAPTIONS,
    _TABLE_HEADING_TX,
    _TABLE_NOTE_LONG,
    _TABLE_NOTE_SUMMARY,
    _TABLE_PROSE,
    _TABLE_VERIFY,
)
from transcribus.processing.normalize import normalize_text
from transcribus.processing.page_xml import (
    Table,
    TextRegion,
    marginalia_bboxes,
    parse_page_xml,
)
from transcribus.processing.teige import TeigeIndex, fold

try:  # Pillow is optional; without it the marginalia page is skipped (no crops).
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

_MARGINALIA = {"marginalia", "margin-text", "margin"}
_HEADING = {"heading", "header", "title", "caption"}

_SECTION_LABEL = {
    "taborsky": "Opis Táborského zprávy o orloji",
    "jine": "Další části knihy (bez referenční edice)",
}
_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def derive_sections(
    matched: set[int], total: int, *, gap: int = 2, work_slug: str = ""
) -> list[tuple[str, int, int, str]]:
    """Group folios into sections.

    For the 1587 orloj book use the curated `_SECTIONS_1587` (Carchesius = one
    section). Any other work (incl. the 1570 autograph) derives sections from the
    Teige-match blocks — the curated list is orloj-specific and must not leak into
    other documents built with this pipeline. Returns (kind, lo, hi, label).
    """
    if "1587" in work_slug:
        return [(k, lo, min(hi, total), lbl) for k, lo, hi, lbl in _SECTIONS_1587 if lo <= total]
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

    # Originál 1570 = jeden souvislý text (Zpráva); „jiné“ oddíly jsou jen vazba/přídeští.
    label_1570 = {
        "taborsky": "Zpráva o orloji pražském (1570)",
        "jine": "Vazba a přídeští",
    }
    is_1570 = "1570" in work_slug
    out: list[tuple[str, int, int, str]] = []
    for i, (kind, lo, hi) in enumerate(sections, start=1):
        if is_1570:
            label = label_1570[kind]
        else:
            label = f"Oddíl {_ROMAN[i] if i < len(_ROMAN) else i} — {_SECTION_LABEL[kind]}"
        out.append((kind, lo, hi, label))
    return out


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


# Editorial apparatus inside the running text: everything in square brackets is an
# editorial intervention (expansion „[Novembris]", uncertain reading „[?]", gloss
# „[= 116]"). Wrap each so the reader can dim/hide them (the „Ediční značky" toggle)
# for uninterrupted reading. Applied to already-escaped HTML (brackets aren't escaped).
_ED_RE = re.compile(r"\[[^\]]*\]")


def _apparatus(escaped: str) -> str:
    return _ED_RE.sub(lambda m: f'<span class="ed">{m.group(0)}</span>', escaped)


_ZODIAC = "♈♉♊♋♌♍♎♏♐♑♒♓"


def _zodiac_textstyle(s: str) -> str:
    """Wrap zodiac signs so they render as monochrome text glyphs, not color emoji.

    Adds the U+FE0E text-presentation selector and a .zod span (CSS forces text).
    """
    for ch in _ZODIAC:
        s = s.replace(ch, f'<span class="zod">{ch}\ufe0e</span>')
    return s


def _line_html(
    line: str, *, normalize: bool = True, page_nr: int = 0, n: int | None = None
) -> str:
    """Render one transcription line (diplomatic + normalized span).

    When ``n`` is given the line gets a citable id (``pNNlN``) and a margin
    line-number gutter; the number itself is shown only every 5th line (edition
    convention), but every line is individually anchorable for citation.
    """
    norm = normalize_text(line) if normalize else line
    dip = _apparatus(_esc(line))
    nor = _apparatus(_esc(norm))
    if n is None:
        return (
            f'<span class="ln"><span class="dipl">{dip}</span>'
            f'<span class="norm">{nor}</span></span>'
        )
    lid = f"p{page_nr}l{n}"
    cls = "lno show" if n % 5 == 0 else "lno"
    gutter = (
        f'<a class="{cls}" href="#{lid}" data-n="{n}" '
        f'title="Kopírovat citaci řádku">{n}</a>'
    )
    return (
        f'<span class="ln" id="{lid}" data-n="{n}">{gutter}'
        f'<span class="dipl">{dip}</span>'
        f'<span class="norm">{nor}</span></span>'
    )


def _clean_block(main_lines: list[str], page_nr: int, do_norm: bool) -> str:
    """Render corrected clean text as numbered lines + a collapsed editorial note.

    Blank lines become paragraph breaks. Trailing ``[Ediční pozn.: …]`` / ``[Pozn. …]``
    lines are lifted out of the running text into a collapsible apparatus block so they
    don't interrupt reading.
    """
    ed_start = re.compile(r"^\[(?:[Ee]diční pozn|[Pp]ozn[.:])")
    text_lines: list[str] = []
    ed_lines: list[str] = []
    in_ed = False
    for ln in main_lines:
        if not in_ed and ed_start.match(ln.lstrip()):
            in_ed = True
        (ed_lines if in_ed else text_lines).append(ln)

    out = [
        '<span class="clean-flag">opravený přepis</span>',
        f'<div class="lines" data-folio="{page_nr}">',
    ]
    n = 0
    for ln in text_lines:
        if not ln.strip():
            out.append('<span class="pbreak"></span>')
            continue
        n += 1
        out.append(_line_html(ln, normalize=do_norm, page_nr=page_nr, n=n))
    out.append("</div>")

    ed_text = " ".join(s.strip() for s in ed_lines if s.strip())
    if ed_text:
        ed_text = re.sub(r"^\[(?:[Ee]diční pozn|[Pp]ozn)[.:\s]*", "", ed_text).rstrip("] ")
        out.append(
            '<details class="ed-note"><summary>Ediční poznámka</summary>'
            f"<p>{_apparatus(_esc(ed_text))}</p></details>"
        )
    return "".join(out)


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


def _split_marginalia(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split clean lines into (main text, marginalia block).

    The marginalia block begins at the first line carrying the ``... na okraji:]`` marker
    and runs to the end (incl. any following later-hand / editorial-note lines). Earlier
    later-hand BODY additions (``[přípis pozdější rukau:] …``) stay in the main text.
    """
    for i, ln in enumerate(lines):
        if "okraji:]" in ln:
            return lines[:i], lines[i:]
    return lines, []


def _marginalia_html(marg_lines: list[str], page_nr: int) -> str:
    """Render the scribal marginalia (brown box) and, if a modern editorial note is
    embedded in the same block (``… — [Ediční pozn.: …]``), lift it into a separate
    colour-distinct (green) box so the two are never mixed. Later-hand keepers' notes
    (``[Pozdější rukou …]``) keep their markers and get the ``later`` accent.
    """
    if not marg_lines:
        return ""
    text = " ".join(ln.strip() for ln in marg_lines).strip()
    if "okraji:]" in text:
        text = text.split("okraji:]", 1)[1].strip()
    # Split off any embedded editorial note → own green box, scribal text stays brown.
    ed_text = ""
    parts = re.split(r"\[[Ee]diční pozn[.:\s]*", text, maxsplit=1)
    if len(parts) > 1:
        text = re.sub(r"\s*[—–-]\s*$", "", parts[0]).strip()
        ed_text = parts[1].rstrip().rstrip("]").strip()
    later = "Pozdější ruk" in text or "pozdější ruk" in text
    cls = "m-note m-orig later" if later else "m-note m-orig"
    out = ""
    if text:
        out += (
            f'<div class="{cls}"><span class="mlabel">Přípisky na okraji</span>'
            f"<p>{_esc(text)}</p></div>"
        )
    if ed_text:
        out += (
            '<div class="m-note m-ed"><span class="mlabel">Ediční poznámka na okraji</span>'
            f"<p>{_apparatus(_esc(ed_text))}</p></div>"
        )
    return out


def _marg_ed_html(page_nr: int) -> str:
    notes = _MARG_ED.get(page_nr)
    if not notes:
        return ""
    items = "".join(f"<p>{_apparatus(_esc(t))}</p>" for t in notes)
    return (
        '<div class="m-note m-ed"><span class="mlabel">Ediční poznámka na okraji</span>'
        f"{items}</div>"
    )


def _marg_notes(marg_lines: list[str]) -> list[str]:
    """Split the clean marginalia block into individual glosses."""
    text = " ".join(ln.strip() for ln in marg_lines).strip()
    text = re.sub(r"^\[[^\]]*?okraji:\]\s*", "", text)
    text = re.sub(r"\s*\[[^\]]*?:\].*$", "", text)  # drop trailing editorial note if any
    parts = re.split(r"\s—\s|;\s", text.rstrip(" ]."))
    return [p.strip(" .—") for p in parts if p.strip(" .—")]


def _later_additions(clean_lines: list[str]) -> list[str]:
    """Extract later-hand insertions (``[přípis pozdější rukau:] …`` / ``[Pozdější rukou …:]``).

    These are substantial annotations by a later hand (a different layer than the
    1587 copyist's index glosses); kept apart so the marginalia page can show them
    as their own category. Editorial notes appended in [ … ] are cut off.
    """
    adds: list[str] = []
    i, n = 0, len(clean_lines)
    marker = re.compile(r"\[(?:přípis\s+)?pozdější\s+ruk[ao]u?[^\]]*\]\s*(.*)", re.I)
    stop = re.compile(r"\[(?:přípis|pozdější|ediční)", re.I)
    while i < n:
        m = marker.match(clean_lines[i].lstrip())
        if not m:
            i += 1
            continue
        buf = [m.group(1)]
        j = i + 1
        while j < n and clean_lines[j].strip() and not stop.match(clean_lines[j].lstrip()):
            buf.append(clean_lines[j])
            j += 1
        text = " ".join(b.strip() for b in buf).strip()
        text = re.split(r"\s*—?\s*\[[Ee]diční pozn", text)[0].strip(" .—")
        if text:
            adds.append(text)
        i = j
    return adds


def _marg_category(note: str) -> tuple[str, str]:
    """Classify a gloss → (tag, popis)."""
    low = note.lower()
    if low.startswith("nb"):
        return ("NB", "pozdější čtenář (?)")
    if any(k in low for k in _MARG_HIST):
        return ("HIST", "dějiny orloje / orlojníci")
    if any(k in low for k in _MARG_LAT):
        return ("LAT", "latinský odborný termín")
    return ("IDX", "český tematický rejstřík")


def _marg_crops(work_dir: Path, out_dir: Path, page_nr: int) -> list[str]:
    """Crop the folio's marginal glosses from the scan; return relative img paths.

    Reproductions of AHMP scans (small study crops). Uses the marginalia region
    bbox from PAGE XML (else an outer-margin strip), then splits it into ink bands
    = single glosses. One column crop if band detection fails.
    """
    if Image is None:
        return []
    scan = work_dir / "scans" / f"{page_nr:04d}.jpg"
    if not scan.exists():
        return []
    im = Image.open(scan).convert("RGB")
    w, h = im.size
    xmlp = work_dir / "page_xml" / f"{page_nr:04d}.xml"
    bbs = marginalia_bboxes(xmlp.read_text(encoding="utf-8")) if xmlp.exists() else []
    if bbs:
        x0 = max(0, min(b[0][0] for b in bbs) - 12)
        x1 = min(w, max(b[0][2] for b in bbs) + 12)
        y0 = max(0, min(b[0][1] for b in bbs) - 10)
        y1 = min(h, max(b[0][3] for b in bbs) + 10)
    elif page_nr % 2 == 0:  # verso → left margin (inset past binding; before main text)
        x0, x1, y0, y1 = 55, 300, 320, min(h, 3450)
    else:  # recto → right margin (after main text; inset from edge)
        x0, x1, y0, y1 = w - 300, w - 55, 320, min(h, 3450)
    col = im.crop((x0, y0, x1, y1))
    g = col.convert("L")
    cw, ch = g.size
    px = g.load()
    min_dark = max(3, cw // 70)
    rows = [sum(1 for x in range(0, cw, 2) if px[x, y] < 150) >= min_dark for y in range(ch)]
    bands: list[tuple[int, int]] = []
    y, gap = 0, 12
    while y < ch:
        if rows[y]:
            s = y
            while y < ch and (rows[y] or (y + gap < ch and any(rows[y:y + gap]))):
                y += 1
            if 16 <= y - s <= 300:  # a real gloss; drop tiny noise and giant merged bands
                bands.append((s, y))
        else:
            y += 1
    # Drop bands in the top margin: that is the later pencil foliation (leaf number),
    # not a marginal gloss. Marginal notes align with the text block (starts ~y 420).
    bands = [(a, b) for (a, b) in bands if y0 + a >= 410]
    d = out_dir / "img" / "marg"
    d.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    if not bands or len(bands) > 14:  # detection unreliable → no crop (transcription only)
        return []
    for i, (a, b) in enumerate(bands):
        sub = col.crop((0, max(0, a - 6), cw, min(ch, b + 6)))
        if sub.width > 430:
            sub = sub.resize((430, round(sub.height * 430 / sub.width)))
        sub.save(d / f"m{page_nr:04d}_{i}.jpg", quality=85)
        paths.append(f"img/marg/m{page_nr:04d}_{i}.jpg")
    return paths


_MARG_TAGNAMES = {"IDX": "rejstřík", "LAT": "lat. termín", "HIST": "dějiny orloje",
                  "NB": "NB / čtenář"}


def _marginalia_doc(title: str, items: list[dict]) -> str:
    """Standalone analysis page for the marginalia (crops + per-gloss classification)."""
    cnt: dict[str, int] = {}
    for it in items:
        for _t, tag, _d in it["notes"]:
            cnt[tag] = cnt.get(tag, 0) + 1
    summary = " · ".join(
        f"{_MARG_TAGNAMES[k]}: {cnt[k]}" for k in ("IDX", "LAT", "HIST", "NB") if cnt.get(k)
    )
    n_add = sum(len(it.get("adds", [])) for it in items)
    if n_add:
        summary += f" · pozdější přípisky (jiná ruka): {n_add}"
    secs = []
    for it in items:
        figs = "".join(
            f'<img src="{_esc(p)}" alt="marginálie fol. {it["page"]}" loading="lazy">'
            for p in it["imgs"]
        )
        if not figs and it["notes"]:
            figs = "<i>[výřez nedostupný — viz sken v AHMP]</i>"
        notes = "".join(
            f'<li><span class="mtag t-{tag}">{_MARG_TAGNAMES[tag]}</span> {_esc(txt)}</li>'
            for (txt, tag, _desc) in it["notes"]
        )
        body = f'<ol class="marg-notes">{notes}</ol>' if notes else ""
        body += "".join(
            '<p class="marg-add"><span class="mtag t-ADD">pozdější přípisek '
            f'(jiná ruka)</span> {_esc(a)}</p>'
            for a in it.get("adds", [])
        )
        label = f' — <span class="mctx">{_esc(it["label"])}</span>' if it.get("label") else ""
        secs.append(
            f'<section class="marg-item"><h3 id="f{it["page"]:04d}">fol. {it["page"]}{label} '
            f'· <a href="p{it["page"]:04d}.html">přepis folia →</a></h3>'
            f'<div class="marg-row"><div class="marg-figs">{figs}</div>'
            f'<div class="marg-body">{body}</div></div></section>'
        )
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rozbor marginálií — {_esc(title)}</title>
<link rel="stylesheet" href="assets/edition.css"></head>
<body class="mode-dipl">
<header><a class="home" href="index.html">≡</a><h1>Rozbor marginálií</h1></header>
<main>
<section class="tiraz">
<p>Na okrajích folií <b>13–46</b> (Táborského Zpráva) je {sum(len(it['notes']) for it in items)}
okrajových přípisků na {len(items)} foliích. Klasifikace: {summary}. Těžiště rozboru jsou
<b>jejich přepisy a interpretace</b> (výřezy ze skenu jsou jen ilustrativní).</p>
<p><b>1) Rejstříkové glosy — bez nové informace.</b> Drobné okrajové glosy jsou
<b>rejstříkový aparát</b>: krátká hesla, která <b>pojmenovávají, co už říká přilehlý text</b> —
témata výkladu (české značky „O pušce“, „Srovnání obojí počtuov“), latinské odborné termíny
(<i>Index Solis, declinatio solis, Linea oppositionis/coniunctionis, Solstitium, Tabula Horarum
Planetarum</i>) a u závěru dějiny orloje a jeho správců. <b>Žádná z nich nepřidává údaj, který by
nebyl v hlavním textu</b>: i „historický“ shluk u fol. 38–46 — planetní hodiny, „nebožtík“ Tobiáš
a jeho škody, učedník Jakub Špaček, obnovení orloje — <b>doslovně odpovídá tělu textu</b> (ověřeno
proti přepisu týchž folií). Jejich přínos je <b>navigační, interpretační a terminologický</b>,
nikoli faktografický.</p>
<p><b>2) Pozdější přípisky jinou rukou — tady je nová informace.</b> Kromě rejstříku jsou v knize
<b>obsažnější vsuvky pozdější rukou</b> (jiná, mladší ruka než opisovač A), které <b>skutečně něco
přidávají</b>:
<br>• <b>fol. 22 — přestavba měsíční koule:</b> „<i>Nyní jest to jinače spraveno a lehčeji, neboť
žádných koleček není, které by měsícem hýbali… nežli vnitř v tlustosti měsíce jest příprava dosti
sprostá, však předce dosti trefně vymyšlená, tak že samým otočováním se měsíce po sféře v 24
hodinách corpus lunae o 1 grad se pohne, a v 30 dnech celý se obrátí…</i>“ — pisatel zde
dokládá, že <b>původní soukolíový pohon měsíce (popsaný Táborským) byl nahrazen jednodušším
mechanismem uvnitř tělesa měsíce</b>. To je <b>doklad reálné konstrukční změny orloje</b>, jaký
Táborského text nemá. <b>Písmo se s dobrou pravděpodobností shoduje s rukou Astrolabia parvum
(fol. 70–79) a komputistické prózy (fol. 62–68)</b> — tedy <b>orlojníka-astronoma činného
~1641–1642</b> (týž pravý sklon, hnědý inkoust a mísení latiny: <i>corpus lunae</i>, <i>gradus</i>,
<i>sphera</i>). Slovem „<i>nyní</i>“ tak <b>datuje přestavbu měsíce k ~1641–1642</b> (proběhla tedy
mezi Táborského popisem /~1570, opis 1587/ a touto pozdější astronomickou vrstvou). Dataci vrstvy
nezávisle ukotvuje výpočet příkladu z 1. XI 1642 v Astrolabiu (skript
<code>tools/verify_astrolabe_1642.py</code>). <b>Tím revidujeme dřívější přiřazení Mikuláši
Petrovi /~1628/</b>; doporučena expertní verifikace na originále.
<br>• <b>fol. 38 — autorství a List purkmistra:</b> „<i>… léta 1410 … ten orloj … dělal … vide
list purkm[istra] … origl., sub figura 4</i>“ — proti Táborského dataci „mistr Hanuš okolo 1490“
tu pisatel <b>odkazuje na List purkmistra</b> (Littera Maior), totiž na <b>opis z r. 1628 původní
listiny z r. 1410</b>, jíž pražská rada smluvila zhotovení orloje s <b>mistrem Mikulášem z Kadaně</b>
(v téže knize, fol. 51–54; originál listiny v knize není). Tím <b>klade zhotovení orloje k r. 1410
/ Mikulášovi z Kadaně</b>, ne Hanušovi. Písmo je mladší plynulá kurzíva 17. stol. (ne ruka opisovače A z 1587) a odkaz „<i>sub
figura 4</i>“ předpokládá, že List purkmistra už byl v knize a očíslován — přípisek je tedy
<b>pozdější (po r. 1628</b>, kdy List purkmistra do knihy vepsal a očísloval Mikuláš Petr;
podpis na fol. 52: „<i>… 15. 9bri [Novembris] 1628. Mikuláš Petr</i>“). Jde o <b>jinou ruku než
vsuvka o měsíční kouli na fol. 22</b> (ta je ruka C) — writer-ID ani vizuální paleografie obě
vsuvky neztotožnily. Klademe ji proto k <b>pozdějším rukám ≥1628</b>, přičemž <b>B vs C zůstává
nerozhodnuto</b>; obsahově mírně svědčí pro <b>B (Mikuláš Petr</b>, který List purkmistra do knihy
vepsal a křížově naň odkazuje). Rozhodne expertní autopsie. <b>Historický obsah</b> — zhotovení
orloje r. 1410 mistrem Mikulášem z Kadaně — <b>tím dotčen není</b>.</p>
<p><b>Rejstříkové glosy (vč. „historických“): jedna ruka, totožná s opisovačem.</b> Na rozdíl
od obou pozdějších vsuvek výše jsou <b>rejstříkové</b> glosy fol. 13–46 (i ty s historickým obsahem
jako „Tobiáš umřel“) <b>jednou rukou</b> — touž českou novogotickou kurzívou, týmž duktem a inkoustem jako hlavní text
(srovnání „Tobiáš umřel“ / „Jakub Špaček“ / „Index Slunce“ navzájem i s tělem textu). Přisuzujeme
je proto <b>ruce A — Matouši Carchesiovi Jablonskému, opisovači z r. 1587</b>; jde o
<b>autorský/písařský rejstřík</b>, ne o cizí čtenářskou ruku. Odstín inkoustu vychází měřením
proti tělu textu <b>nepatrně světlejší a méně teplý</b> (Δ jasu +13–15, Δ „tepla“ R−B −18 až −34
z 256), což je však <b>zčásti artefakt tenčího tahu</b> — týž železo-duběnkový hnědý inkoust,
psaný jemnějším perem.</p>
<p><b>Ztotožnění s jinými písaři a datace.</b> Marginálie se <b>neshodují s žádnou z pozdějších
rukou</b> knihy — německého Listu purkmistra (1628), komputistické sekce (~1641) ani přední
Hájkovy tabule a přípisku (~1689); ty jsou jiným písmem a fyzicky v jiných částech. Protože
marginálie indexují tělo textu a jsou rukou A, vznikly <b>současně s opisem, tj. r. 1587</b>
(nebo těsně po něm) — tím je lze datovat, na rozdíl od pozdějších přípisků jinde v knize.
Výjimkou mohou být ojedinělé „NB“, jež bývají rukou pozdějšího čtenáře. (Paleografie i
kolorimetrie ze skenu = pracovní hypotéza, ne znalecký posudek; jistota střední.)</p>
<p class="warn"><b>Výřezy</b> jsou drobné studijní reprodukce ze skenů <b>Archivu hlavního města
Prahy</b> (Sbírka rukopisů, inv. č. 7916), uvedené pro ilustraci; souhlas archivu s reprodukcí
v jednání. Závazný je <b>přepis</b>, ne obrázek.</p>
</section>
{"".join(secs)}
</main>
<footer>Rozbor marginálií — pracovní hypotéza ze skenů AHMP. Edice © David Knespl, CC BY 4.0.</footer>
</body></html>"""


def _page_doc(
    *, title: str, page_nr: int, total: int, regions: list[TextRegion],
    ahmp_url: str | None, teige_passage: str | None, section_label: str = "",
    tables: list[Table] | None = None, figures: list[str] | None = None,
    clean_lines: list[str] | None = None, embed_scan: bool = False,
    table_page: bool = False, binding_note: str = "",
) -> str:
    tables = tables or []
    figures = figures or []
    has_text = any(r.lines and any(line.strip() for line in r.lines) for r in regions)
    has_content = has_text or bool(tables) or bool(figures) or bool(clean_lines) or table_page
    # Teige režim/volba dává smysl jen u Carchesiova opisu Táborského zprávy (fol. 5–49),
    # kterou Teige (1901) vydal; jinde (tabulky, List, Astrolabium, vazba) reference není.
    has_teige = 5 <= page_nr <= 49
    pencil_html = (
        f' · <span class="oldfol" title="původní foliace tužkou (čísluje listy)">st. fol. '
        f'{_PENCIL_FOLIO[page_nr]}</span>' if page_nr in _PENCIL_FOLIO else ""
    )
    missing_html = (
        f'<div class="missing-leaves">⚠ {_MISSING_BEFORE[page_nr]}</div>'
        if page_nr in _MISSING_BEFORE else ""
    )
    # AHMP rules: any internet publication of a reproduction needs an agreement +
    # <=500px + watermark. Until that is in place, NOTHING is republished — figures are
    # only referenced with an out-link to the AHMP viewer.
    fig_link = (
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">sken v AHMP (fol. {page_nr})</a>'
        if ahmp_url else f"sken v AHMP (fol. {page_nr})"
    )
    fig_note = (
        f'<figure class="fig fig-ref"><figcaption>Na tomto foliu je vyobrazení '
        f"(zde nereprodukováno — viz {fig_link}).</figcaption></figure>"
        if figures else ""
    )
    prev_link = f"p{page_nr-1:04d}.html" if page_nr > 1 else ""
    next_link = f"p{page_nr+1:04d}.html" if page_nr < total else ""
    ahmp = (
        f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">↗ sken v AHMP (fol. {page_nr})</a>'
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

    marginalia = ""
    region_margin = ""
    if has_content:
        # Precedence: corrected clean text > Docling table grid > raw per-line HTR.
        if clean_lines:
            main_lines, marg_lines = _split_marginalia(clean_lines)
            do_norm = page_nr not in _NO_NORMALIZE
            body_regions = _clean_block(main_lines, page_nr, do_norm)
            marginalia = _marginalia_html(marg_lines, page_nr)
        elif tables:
            cap = _TABLE_CAPTIONS.get(page_nr)
            note = _TABLE_VERIFY.get(
                page_nr, "přepis z rukopisu; číselné hodnoty ke kontrole proti skenu."
            )
            vcls = "table-note verified" if note.startswith("✓") else "table-note"
            heading_tx = _TABLE_HEADING_TX.get(page_nr)
            cap_html = f'<p class="table-cap">{_esc(cap)}</p>' if cap else ""
            # Above the table: the transcribed manuscript heading if we have one (original
            # text), otherwise the editorial caption. The ✓/verification note and any
            # method commentary always go BELOW, into the collapsible note.
            if heading_tx:
                head = heading_tx
                cap_in_note = cap_html  # editorial caption belongs to the note here
            else:
                head = cap_html
                cap_in_note = ""
            verify_html = f'<p class="{vcls}">{_esc(note)}</p>' if cap else ""
            body_regions = head + "".join(_table_html(t) for t in tables)
            body_regions += _TABLE_PROSE.get(page_nr, "")
            long_note = _TABLE_NOTE_LONG.get(page_nr)
            note_body = cap_in_note + verify_html + (long_note or "")
            if note_body.strip():
                summ = _TABLE_NOTE_SUMMARY.get(page_nr, "Metodická poznámka — rozbor a ověření")
                body_regions += (
                    f'<details class="method-note"><summary>{_esc(summ)}</summary>'
                    f"{note_body}</details>"
                )
        elif table_page:
            link = (
                f'<a href="{_esc(ahmp_url)}" target="_blank" rel="noopener">sken v AHMP (fol. {page_nr})</a>'
                if ahmp_url else f"sken v AHMP (fol. {page_nr})"
            )
            cap = _TABLE_CAPTIONS.get(page_nr, "Komputistická / astronomická tabulka")
            body_regions = (
                f'<div class="table-todo"><b>{_esc(cap)}</b><br>Číselná data tabulky zatím '
                f"nepřepsána (strojové rozpoznání ručně psaných tabulek selhává). Viz {link}.</div>"
            )
            long_note = _TABLE_NOTE_LONG.get(page_nr)
            if long_note:
                body_regions += (
                    '<details class="method-note" open><summary>Záhlaví tabule a původ '
                    "(Tadeáš Hájek z Hájku)</summary>"
                    f"{long_note}</details>"
                )
        else:
            # Per-line HTR path (no corrected clean text). Split marginal regions out
            # of the text flow so they can sit in a dedicated outer margin column,
            # mirroring the manuscript leaf — same two-zone layout as the clean path.
            def _real_lines(r: TextRegion) -> list[str]:
                return [line.strip() for line in r.lines if line.strip()]

            def _is_noise(r: TextRegion) -> bool:
                # A narrow outer-margin strip on which the HTR hallucinated the SAME
                # token on every line (e.g. "Já"×10, "prut,"×13) is layout noise on a
                # blank/ruled edge — not a scribal gloss. Suppress it entirely.
                rl = _real_lines(r)
                return len(rl) >= 2 and len(set(rl)) == 1

            marg_regs: list[TextRegion] = []
            body_regs: list[TextRegion] = []
            for r in regions:
                if r.rtype in _MARGINALIA and _real_lines(r):
                    if _is_noise(r):
                        continue  # drop degenerate margin-strip HTR repetition
                    marg_regs.append(r)
                else:
                    body_regs.append(r)
            body_regions = "\n".join(_region_html(r) for r in body_regs)
            region_margin = "\n".join(_region_html(r) for r in marg_regs)
        body_regions += _FIGURE_SVG.get(page_nr, "")
        page_folded = {
            fold(w) for r in regions for line in r.lines for w in line.split() if len(fold(w)) >= 4
        }
        teige = _teige_html(teige_passage, page_folded)
        if clean_lines:
            # True two-zone leaf: text column + a dedicated outer margin (recto→right,
            # verso→left) holding the scribal marginalia and (colour-distinct) editorial
            # side-notes — mirroring the manuscript page, not floated inside the text.
            vcls = "verso" if page_nr % 2 == 0 else "recto"
            margin_col = marginalia + _marg_ed_html(page_nr)
            folio = (
                f'<div class="folio folio-2col {vcls}">'
                f'<div class="textcol">{fig_note}{body_regions}</div>'
                f'<aside class="margin-col">{margin_col}</aside></div>'
            )
        elif region_margin:
            # Per-line HTR with a detected marginal region: same true two-zone leaf,
            # margin side following recto/verso (recto→right, verso→left).
            vcls = "verso" if page_nr % 2 == 0 else "recto"
            folio = (
                f'<div class="folio folio-2col {vcls}">'
                f'<div class="textcol">{fig_note}{body_regions}</div>'
                f'<aside class="margin-col">{region_margin}</aside></div>'
            )
        else:
            folio = f'<div class="folio">{marginalia}{fig_note}{body_regions}</div>'
        teige_inner = teige if teige_passage else (
            '<div class="teige-empty">Tato strana patří k Táborského zprávě (Carchesiův opis), '
            "ale referenční pasáž se pro ni nepodařilo automaticky zarovnat.</div>"
        )
        body = folio + (
            '<div class="teige-pane"><div class="teige-label">Teige (1570), '
            f"přibližné zarovnání</div>{teige_inner}</div>" if has_teige else ""
        )
    else:
        body = f'<div class="empty">{_esc(binding_note) if binding_note else "[prázdná strana / vazba]"}</div>'

    body = _zodiac_textstyle(body)
    # Teige radio jen na Carchesiových foliích (has_teige výše). Jinde se vynechá; JS na
    # takové stránce uložený režim „teige“ zobrazí jako diplomatický (preference se nepřepíše).
    teige_radio = (
        '<label><input type="radio" name="mode" value="teige"> edice (Teige)</label>'
        if has_teige else ""
    )
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fol. {page_nr:04d} — {_esc(title)}</title>
<link rel="stylesheet" href="assets/edition.css"></head>
<body class="mode-dipl layout-lined app-on{' has-teige' if has_teige else ''}">
<header>
  <a class="home" href="index.html">≡</a>
  <h1>{_esc(title)}</h1>
  <div class="modes">
    <span class="ctl">
      <span class="ctl-lbl">Znění</span>
      <label><input type="radio" name="mode" value="dipl" checked> transliterace</label>
      <label><input type="radio" name="mode" value="norm"> transkripce</label>
      {teige_radio}
    </span>
    <span class="ctl">
      <span class="ctl-lbl">Sazba</span>
      <label><input type="radio" name="layout" value="lined" checked> řádky</label>
      <label><input type="radio" name="layout" value="flow"> čtení</label>
    </span>
    <label class="ctl-app"><input type="checkbox" id="appToggle" checked> ediční značky</label>
  </div>
</header>
<nav class="pager">
  <a class="prev" href="{prev_link}"{'' if prev_link else ' hidden'}>← předchozí</a>
  <span class="folno">fol. {page_nr:04d} / {total:04d}{pencil_html} &nbsp; {ahmp}</span>
  <a class="next" href="{next_link}"{'' if next_link else ' hidden'}>další →</a>
</nav>
<div class="section-label">{_esc(section_label)}</div>
<main class="leaf">{missing_html}{body}{scan_embed}</main>
<footer>Diplomatický přepis (Transkribus HTR, model 263129). Normalizace heuristická — nutná korektura.
Teige: edice 1901, public domain. Vyobrazení ani skeny se zde nereprodukují — odkazy „sken"
vedou na stabilní permalink archiválie v Archivu hlavního města Prahy (katalog.ahmp.cz);
ten otevře dokument, v prohlížeči pak přejděte na příslušné folio (skeny jsou číslovány shodně).</footer>
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


_STATUS_BADGE = {
    "done": '<span class="b-done">✅ hotovo</span>',
    "partial": '<span class="b-partial">🔶 rozpracováno</span>',
    "todo": '<span class="b-todo">❌ chybí</span>',
    "na": '<span class="b-na">— vazba/prázdná</span>',
}

def _status_first_page(fol: str) -> str:
    """Page link for a status-row folio range, e.g. 'f5–f12' -> 'p0005.html'."""
    m = re.search(r"\d+", fol)
    return f"p{int(m.group()):04d}.html" if m else ""


def _status_html(slug: str = "") -> str:
    is_1570 = "1570" in slug
    status_rows = _STATUS_ROWS_1570 if is_1570 else _STATUS_ROWS
    head_part = "část" if is_1570 else "část knihy"
    rows = "".join(
        f'<tr data-href="{_status_first_page(fol)}">'
        f'<td><a href="{_status_first_page(fol)}">{_esc(fol)}</a></td>'
        f"<td>{_esc(part)}</td>"
        f'<td class="hand">{_esc(hand)}</td>'
        f"<td>{_STATUS_BADGE.get(st, _esc(st))}</td><td>{_esc(rest)}</td></tr>"
        for fol, part, hand, st, rest in status_rows
    )
    if is_1570:
        note = (
            '<p class="status-note"><b>Co zbývá:</b> diplomatická kontrola Zprávy po řádcích '
            "(f6–f29) proti skenu a dočtení sporných marginálií. Vazební a prázdná folia: "
            "f1 (přední deska), f2 (přídeští), f30 (zadní deska). Celý text je autograf "
            "<b>Jana Táborského (1570)</b> — jediná ruka.</p>"
        )
    else:
        note = (
            '<p class="status-note"><b>Stav: textově i tabulkově kompletní</b> — každé folio je '
            "buď opravený přepis, ověřená tabulka, nebo vazba; žádné nepřepsané ani neověřené "
            "místo. Sloupec „ruka · datace“ ukazuje vrstvení konvolutu: <b>A</b> Carchesius 1587 "
            "(jádro), <b>B</b> Mikuláš Petr 1628 (List purkmistra), <b>C</b> orlojník-astronom "
            "~1641–42 (komputus + Astrolabium), <b>D</b> ~1689 (Hájkova tabule). <b>Do finální "
            "kritické edice zbývá:</b> expertní revize německého znění návodu f54, dořešení zbylých "
            "nejistých čtení [?] a kritický variantní aparát opis × Teige (kolace už hotová, "
            "<code>tools/collate_carchesius_teige.py</code>). Prázdné/předsádky: f1, f81.</p>"
        )
    return (
        '<table class="status"><caption>Stav zpracování (průběžně aktualizováno)</caption>'
        f"<thead><tr><th>folia</th><th>{head_part}</th><th>ruka · datace</th>"
        f"<th>stav</th><th>zbývá</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>{note}"
    )


def _tiraz_1570(ahmp_a: str) -> str:
    """„O edici“ pro originál Táborského (autograf 1570, AHMP sign. 1867)."""
    return (
        '<section class="tiraz"><h2>O edici</h2>'
        "<p><b>Pramen — autograf Jana Táborského z Klokotské Hory (1570).</b> Archiv hlavního "
        f"města Prahy, Sbírka rukopisů, sign. 1867. {ahmp_a}. Jde o <b>originál</b> Táborského "
        "<i>Zprávy o orloji pražském</i>, dokončený podle vlastního kolofonu <b>v středu na den "
        "sv. Lukáše, tj. 18. října 1570</b> (f29). Rukopis je vázán v skvostné renesanční kožené "
        "vazbě se zlaceným titulem „Sprawa o orlogi pražském“, znakem Starého Města Pražského a "
        "letopočtem 1570 (přední deska, f1); na zadní desce (f30) je zlacený medailon s českým "
        "lvem. Edice zpracovává <b>vlastní text Zprávy</b> (f3–f29): titulní verš, dedikaci, "
        "XVIII kapitul, kolofon a závěrečné verše. Folia f1, f2 a f30 jsou <b>vazba a přídeští</b> "
        "(bez textu Zprávy).</p>"
        '<p class="teige"><b>Vztah k orlojní knize 1587.</b> Tento rukopis je <b>předloha</b>, '
        "kterou roku 1587 opsal staroměstský písař <b>Matouš Carchesius Jablonský</b> do tzv. "
        "orlojní knihy (AHMP, inv. č. 7916) — ta je zpracována jako <b>samostatná edice</b> a od "
        "originálu se místy liší (varianty písaře, pozdější přídavky, komputistické tabulky a "
        "další části). <b>Edici originálu 1570 vydal Josef Teige</b> v Časopise Společnosti přátel "
        "starožitností českých (roč. IX, 1901). Zde tedy Teige vydává <b>tentýž</b> rukopis, "
        "který čteme — slouží proto jako přímá <b>kolační a korekturní opora</b>.</p>"
        "<p><b>Metoda — syntetická edice.</b> Strojové rozpoznání rukopisu (HTR, Transkribus "
        "PyLaia, čeština 263129) tvoří kostru přepisu řádek po řádku; ta je <b>korigována podle "
        "Teigeho edice 1901</b> a sporná místa (zejména marginálie) <b>dočítána ze skenu</b>. "
        "Text lze zobrazit ve <b>třech režimech</b>: <i>transliterace</i> (čtení ukotvené na "
        "řádky rukopisu) / <i>transkripce</i> (diakritická, dle normy Ivan Šťovíček a kol.) / "
        "<i>edice (Teige)</i>.</p>"
        "<p><b>Marginálie.</b> Na okrajích jsou <b>rejstříkové glosy</b> shrnující přilehlý text "
        "(např. „Tabula horarum planetarum“, „Obnovení orloje“, „Tobiáš umřel“, „Táborský "
        "přistúpil“, „Čeho nevyšetřili“, „Jakub Špaček“, „Suma“). V edici jsou vysazeny do "
        "<b>postranní zóny</b> podle strany rukopisu (recto → pravý okraj, verso → levý).</p>"
        '<p class="warn"><b>Stav: rozpracovaná pracovní edice.</b> Normalizace je heuristická a '
        "vyžaduje korekturu; diplomatická kontrola Zprávy po řádcích (f6–f29) proti skenu "
        "probíhá. Zatím neslouží jako citovatelná kritická edice.</p>"
        '<p><b>Práva a licence:</b> skeny ani vyobrazení se zde nereprodukují — odkazy „sken“ '
        "vedou do prohlížeče AHMP (práva k reprodukcím: Archiv hlavního města Prahy). "
        "Text edice © David Knespl, licence CC&nbsp;BY&nbsp;4.0; software EUPL-1.2.</p>"
        "<p><b>Použité zdroje a poděkování.</b> Pramen a skeny: <b>Archiv hlavního města "
        "Prahy</b> (sign. 1867). Strojový přepis: <b>Transkribus</b> (READ-COOP), model PyLaia "
        "263129. Kolace: edice originálu 1570 <b>Josefa Teigeho</b> (1901, public domain). Norma "
        "transkripce: <b>Ivan Šťovíček a kol.</b> Datace a badatelství orloje: <b>Zdeněk "
        "Horský</b>.</p></section>"
    )


def _index_doc(
    title: str,
    sections: list[tuple[str, int, int, str]],
    pages: dict[int, tuple[str, bool]],
    ahmp_permalink: str | None = None,
    work_slug: str = "",
    has_marginalia_page: bool = False,
) -> str:
    ahmp_a = (
        f'<a href="{_esc(ahmp_permalink)}" target="_blank" rel="noopener">'
        "záznam a skeny v katalogu AHMP ↗</a>"
        if ahmp_permalink else "katalog AHMP"
    )
    tiraz = (
        '<section class="tiraz"><h2>O edici</h2>'
        "<p><b>Pramen — jedna svázaná orlojní kniha (zápisy z let ~1587–1689).</b> Archiv "
        f"hlavního města Prahy, Sbírka rukopisů, inv. č. 7916. {ahmp_a}. Nejde o soubor volně "
        "vložených listů: <b>přímým ohledáním originálu v archivu (AHMP) bylo ověřeno, že jde "
        "o jediný původní svázaný celek</b> — <b>prázdný sešit svázaný vcelku a teprve pak "
        "postupně popisovaný</b>, nikoli pozdější tematická převazba. Zápisy proto vznikaly na "
        "<b>předem svázané archy</b> a pořadí folií v hlavním korpusu odpovídá chronologii jejich "
        "vzniku. <b>Jedna výjimka</b>: referenční sluneční tabule na "
        "ponechaných <b>volných předních listech (fol. 2–3) byly dopsány nejpozději</b> (dle "
        "vlastního letopočtu ≈ 1689) — fyzicky jsou první, ale časově poslední, takže pořadí "
        "folií tu chronologii neodráží a <b>protahují celkový rozsah psaní knihy zhruba na "
        "století</b>. Díky chronologii hlavního korpusu jsou <b>datovatelné i pozdější přípisky "
        "jednotlivých pisatelů</b>; právě "
        "na nich stojí přeřazení vzniku orloje k r. 1410 (Z. Horský). Kniha má několik částí: "
        "(1) <b>opis Táborského <i>Zprávy o orloji pražském</i></b> (fol. 5–49), který roku "
        "1587 pořídil staroměstský písař <b>Matouš Carchesius Jablonský</b> (kolofon fol. 47); "
        "(2) <b>opis Listu purkmistra</b> — původní listina je <b>z r. 1410</b> (de facto smlouva "
        "Starého Města s hodinářem Mikulášem z Kadaně na zhotovení orloje), v knize však <b>opis, "
        "který r. 1628 vypsal ze starých knih hořejší kanceláře Mikuláš Petr</b> (podpis fol. 52): "
        "německy (fol. 51–52) i v dobovém českém překladu (fol. 53–54); (3) "
        "<b>komputistické a astronomické tabulky</b> (fol. 2–3, 50, 55–69 — Littera dominicalis, "
        "zlaté číslo, epakta, východ slunce, polouorlojní počet); tabule délky dne / východu / "
        "západu (fol. 3) je dle <b>vlastního záhlaví</b> dílo <b>Tadeáše Hájka z Hájku</b> pro "
        "výšku pólu 50° (Praha), upravené na nový kalendář (opis ≈ 1689); (4) <b>Astrolabium "
        "parvum</b> "
        "(fol. 70–79, ~1642, autorův český překlad Franze Rittera z Norimberku — ruka C); a (5) "
        "<b>pozdější přípisky pisatelů</b> (16.–17. stol.). Edice "
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
        "opisovače 1587, „přídavek na spheru“, poznámky pozdějších pisatelů odkazující na List purkmistra 1410). "
        "Proto se text <b>neopravuje podle Teigeho</b>: Teige slouží jen jako <b>čtecí opora a "
        "kolace</b> a <b>odlišnosti opisu se záměrně zachovávají</b> (a značí), nikoli zarovnávají "
        "na originál.</p>"
        '<p class="warn"><b>Stav: rozpracovaná pracovní edice.</b> Normalizace je heuristická a '
        "vyžaduje korekturu; část přípisků na okraji (fol. 13–30) je ověřena jen zčásti. Oddíl "
        "fol. 31–42 byl nově ověřen <b>kolací proti Teigeho edici 1570</b> (porovnáno každé slovo) "
        "a vizuální kontrolou skenu — odlišnosti jsou dobové pravopisné varianty opisu, ne chyby "
        "přepisu. Zatím přesto neslouží jako plně citovatelná kritická edice.</p>"
        '<p class="verify"><b>Ověření tabulek výpočtem.</b> Číselné komputistické a astronomické '
        "tabulky byly přepsány ručně (strojové rozpoznání rukopisných číslic selhává) a poté "
        "<b>deterministicky ověřeny nezávislým výpočtem</b> (skript <code>tools/verify_computus.py</code> "
        "v repozitáři; všechny kontroly procházejí): "
        "<b>fol. 50 a 56</b> (<i>Tabula Litera dominicalis</i>, „N. I“) — juliánská i gregoriánská "
        "nedělní písmena souhlasí s výpočtem pro všech 28 let slunečního cyklu; gregoriánský sloupec "
        "platí pro 17. století (1583–1699), což zároveň datuje použitelnost tabulky. "
        "<b>fol. 57</b> (<i>Tabula Epactarum</i>, „N. 2“) — všechny tři gregoriánské sloupce epakt "
        "souhlasí s výpočtem (velikonoční úplněk dle J. Meeuse) pro 19 zlatých počtů ve více "
        "obdobích; juliánský sloupec = gregoriánský + 10 (10denní rozdíl kalendářů), hranice "
        "období odpovídají gregoriánským korekcím. "
        "<b>fol. 55</b> (východ Slunce) — sezónní průběh přesně odpovídá astronomickému "
        "výpočtu pro Prahu (φ ≈ 50,09°, <b>pravé Slunce</b>): residuum je ploché přes celý rok "
        "(tedy bez chyby přepisu i zeměpisné šířky). Tabule počítá východ jako <b>střed Slunce "
        "na geometrickém obzoru bez refrakce</b> (perpetuální tabule refrakci běžně vynechávaly) "
        "— při této definici je odchylka ≤ 2 min; vůči modernímu východu (horní okraj + "
        "refrakce, −50′) je rukopis o ~7 min později. Těsnost shody (RMS ~0,8 min přes 365 dní) "
        "ukazuje, že jde o data <b>vypočtená, ne pozorovaná</b> — nejspíš opsaná z hotové "
        "tištěné tabule; celá sekce je datovatelná kolem r. 1641 (podrobný rozbor v metodické "
        "poznámce u fol. 55). "
        "<b>fol. 69</b> (násobilka) — součiny souhlasí. "
        "<b>fol. 60 a 61</b> (<i>Tabula intervalli Paschae</i>, juliánská a gregoriánská) — "
        "dvojčíslí v buňkách dekódováno (první číslo = pořadí týdne Velikonoc, druhé doplněk): "
        "juliánská <b>f60 souhlasí ve všech 133 buňkách</b>, gregoriánská <b>f61 v 191 z 210</b> "
        "— zbylé neshody leží v zóně <b>epakty 25/XXV</b> (gregoriánská zvláštnost s dvojí "
        "podobou epakty), kterou je třeba dořešit na originále; princip i většina tabule jsou "
        "potvrzeny. (Dřívější verze edice uváděla f60 jako nedekódovanou — překonáno.)</p>"
        "<p><b>Písařské ruce.</b> Kniha je <b>konvolut čtyř hlavních rukou z let ~1587–1689</b>. "
        "<b>A — Matouš Carchesius Jablonský</b> (1587, kolofon fol. 47): opis Táborského "
        "<i>Zprávy</i> fol. 5–49 a její rejstříkové glosy fol. 13–46. <b>B — Mikuláš Petr</b> "
        "(1628, podpis fol. 52): List purkmistra německy (fol. 51–52) i v dobovém českém "
        "překladu (fol. 53–54). <b>C — orlojník-astronom</b> (~1641–1642): komputistické tabulky "
        "a próza (fol. 50, 55–69) a <b>Astrolabium parvum fol. 70–79</b> — <b>nikoli ruka A</b>: "
        "text mluví o Táborském ve 3. osobě, vznikl „poněvadž papír prázdný zůstával“, je to "
        "autorův <b>český překlad Franze Rittera z Norimberku</b> a nese <b>vlastní dataci „1642, "
        "1. Novembris“</b> (fol. 78). <b>D</b> (~1689): přední Hájkova tabule fol. 2–3. Německý "
        "návod k tabuli dole na fol. 54 (≥1641) je <b>nejistý</b> — buď C dvojjazyčně, nebo "
        "zvláštní německá ruka (jiný jazyk = jiné písmo, rukopisně nerozhodnutelné). Latinské "
        "epigramy fol. 4 a 80 (jednou rukou) pracovně připsány <b>ruce C</b> (writer-ID je řadí "
        "ke shluku C, sedí matematický obsah f80 i poloha hned za Astrolabiem, a C latinka "
        "„Corpus lunæ“ f22 / „Novembris“ f78 je s písmem epigramů slučitelná) — jistota střední. "
        "<b>Metoda atribuce:</b> syntéza tří kritérií "
        "— písmo (vizuální paleografie + počítačová <i>writer-ID</i> analýza ~4100 řádkových "
        "výřezů: texturní rysy ResNet-50 → UMAP/HDBSCAN), obsah / jazyk / odkazy a datace "
        "(kolofony, interní roky). Strojová analýza spolehlivě oddělí hrubé rozdíly (německý "
        "Kurrent vyšel jako čistý shluk), na jednotlivou krátkou glosu však nestačí — ta se "
        "rozhoduje paleograficky a obsahově. Jde o <b>pracovní atribuci, ne znalecký posudek</b>.</p>"
        "<p><b>Glosy a pozdější přípisky.</b> <b>Rejstříkové glosy fol. 13–46</b> (hesla "
        "„<i>Index Solis</i>“, „<i>Linea oppositionis/coniunctionis</i>“, „O pušce“, „Václav "
        "Zvůnek, třetí zprávce“, „Tobiáš umřel“ ad.) přisuzujeme <b>ruce A</b> — táž česká "
        "novogotická kurzíva jako hlavní text, týž dukt a mísení české a latinské terminologie; "
        "jde o <b>rejstříkový aparát opisovače</b>, ne cizí přípisky (hesla shrnují vyprávění, ne "
        "vnější události). <b>Dvě pozdější vsuvky 17. století jsou však cizíma rukama:</b> na "
        "<b>fol. 22</b> přípisek „<i>Nyní jest to jinače spraveno… žádných koleček není… samým "
        "otočováním se měsíce… corpus lunae o 1 grad… v 30 dnech celý se obrátí</i>“ dokumentuje "
        "<b>přestavbu měsíční koule na samootáčivou</b> a rukopisně i obsahem patří <b>ruce C</b> "
        "(~1641–42; slovem „nyní“ tu přestavbu datuje); na <b>fol. 38</b> přípisek „<i>…léta 1410… "
        "vide list purkmistra… sub figura 4</i>“ <b>přeřazuje vznik orloje k r. 1410</b> (proti "
        "„mistr Hanuš okolo 1490“ v textu) — pozdější latinsky gramotná ruka (≥1628, předpokládá "
        "vložený a očíslovaný List), <b>odlišná od C; mezi B a C nerozhodnuto</b>. Strojové "
        "shlukování rukopisu (writer-ID) oddělí hrubé rozdíly (německý Kurrent), ale na atribuci "
        "jednotlivé glosy nestačí — ta stojí na paleografii, obsahu a dataci.</p>"
        "<p><b>Odstín inkoustu.</b> Střední barva tahů marginálií proti hlavnímu textu v témž "
        "snímku (fol. 20 a 43) vychází <b>nepatrně světlejší a méně teplá</b> (méně "
        "červenohnědá; Δ jasu +13–15, Δ „tepla“ R−B −18 až −34 z 256). Tento rozdíl je však "
        "<b>zčásti artefaktem tenčího okrajového tahu</b> (úzké písmo „nabírá“ víc papíru), "
        "nikoli nutně jiným inkoustem. Závěr: týž <b>železo-duběnkový hnědý inkoust</b>, "
        "marginálie psané <b>jemnějším perem</b> (snad o málo zředěnější či v rychlejším "
        "samostatném sezení) — slučitelné se vznikem <b>současně s opisem</b> (1587), ne jako "
        "pozdější vrstva. (Paleografie i kolorimetrie ze skenu = pracovní hypotéza, ne znalecký "
        "posudek; jistota střední.)</p>"
        '<p><b>Práva a licence:</b> skeny ani vyobrazení se zde nereprodukují — odkazy „sken" '
        "vedou do prohlížeče AHMP (práva k reprodukcím: Archiv hlavního města Prahy). "
        "Text edice © David Knespl, licence CC&nbsp;BY&nbsp;4.0; software EUPL-1.2.</p>"
        "<p><b>Použité zdroje a poděkování.</b> Pramen a skeny: <b>Archiv hlavního města "
        "Prahy</b>. Strojový přepis: <b>Transkribus</b> (READ-COOP), modely PyLaia 263129 a "
        "27457. Kolace: edice originálu 1570 <b>Josefa Teigeho</b> (1901, public domain). "
        "Přepis Astrolabia parvum (fol. 70–79) přejat z orloj.eu — přepis <b>Pavel Baudisch</b>, "
        "poznámky a model <b>Petr Král</b> a kol. (Český spolek horologický); za orlojnické "
        "konzultace patří dík <b>Petru Skálovi</b> (ČSH). Paleografický přepis německého Listu "
        "purkmistra (fol. 51–52) byl pořízen na zakázku (autorka k doplnění); <b>dobový český "
        "překlad (fol. 53–54)</b> přejat z přepisu <b>Stanislava Macháčka</b> (<i>Nález zprávy "
        "o vytvoření orloje Starého Města r. 1410</i>, Zprávy Komise pro dějiny přírodních, "
        "lékařských a technických věd ČSAV, 10, 1962, s. 21–24); <b>zarovnán na vlastní HTR</b>. "
        "Norma transkripce: "
        "<b>Ivan Šťovíček a kol.</b> "
        "Datace a badatelství: <b>Zdeněk Horský</b> (1988); opis objevil <b>Stanislav "
        "Macháček</b> (1962). Rozpoznání tabulek: <b>Docling</b> (IBM).</p></section>"
    )
    uvod = (
        '<section class="uvod"><h2>Úvod</h2>'
        '<p class="lead">Orlojní kniha pražského orloje — rukopis, který přes celé století '
        "(1587–1689) sloužil patrně jako <b>příručka orlojníků</b>: shromažďoval, co bylo "
        "potřeba k nastavování a obsluze orloje — opis Táborského zprávy o orloji, smlouvu "
        "z roku 1410, komputistické tabulky i návod k astrolábu.</p>"
        "<p>Rukopis je uložen v Archivu hlavního města Prahy (Sbírka rukopisů, inv. č. 7916). "
        "Není to sborník volně vložených listů, ale <b>prázdný sešit svázaný vcelku a teprve pak "
        "postupně popisovaný</b> — což jsme ověřili přímým ohledáním originálu v archivu. Je to "
        "tedy <b>konvolut</b>: vrství v sobě texty od konce 16. do konce 17. století, jak je "
        "psali po sobě jdoucí pisatelé — městský i kancelářský písař, orlojník-astronom, "
        "opisovač.</p>"
        "<h3>O čem kniha je</h3>"
        "<ul>"
        "<li><b>Jádro (fol. 5–49):</b> opis <i>Zprávy o orloji pražském</i> Jana Táborského, "
        "který roku 1587 pořídil staroměstský písař <b>Matouš Carchesius Jablonský</b> — "
        "základní dobový popis stroje, jeho soukolí, dějin a obsluhy.</li>"
        "<li><b>List purkmistra (fol. 51–54):</b> opis (1628, <b>Mikuláš Petr</b>) listiny "
        "<b>z r. 1410</b> — de facto smlouvy Starého Města s hodinářem <b>Mikulášem z Kadaně</b> "
        "na zhotovení orloje; německy i v dobovém českém překladu.</li>"
        "<li><b>Komputistické a astronomické tabulky (fol. 2–3, 50, 55–69):</b> nedělní písmena, "
        "zlaté číslo, epakty, východ Slunce, počítání nového měsíce a Velikonoc; tabule délky "
        "dne (fol. 3) je opis <b>Hájkovy „Tabule dlúhosti dne a noci k spravování orloje“ "
        "(1574)</b>, zhotovené přímo pro pražský orloj.</li>"
        "<li><b>Astrolabium parvum (fol. 70–79, ~1642):</b> orlojníkův vlastní český překlad "
        "příručky <b>Franze Rittera</b> z Norimberku — jak astrolábem počítat čas, východ a "
        "západ Slunce i Měsíce, včetně řešených příkladů.</li>"
        "<li><b>Pozdější přípisky pisatelů</b> (16.–17. stol.) na okrajích a volných "
        "místech.</li>"
        "</ul>"
        "<h3>Na co jsme přišli</h3>"
        "<ul>"
        "<li><b>Pořadí zápisů je vodítkem k jejich dataci.</b> Protože kniha byla svázána jako "
        "prázdný sešit a popisována postupně, <b>pořadí folií odráží chronologii vzniku</b> — díky tomu lze "
        "datovat i nedatované přípisky. (Výjimka: přední volné listy fol. 2–3 byly dopsány "
        "<b>nejpozději</b>, ≈ 1689, takže fyzicky první jsou časově poslední.)</li>"
        "<li><b>Podle staré foliace chybějí listy.</b> Srovnání původní (tužkou psané) foliace "
        "s dnešním pořadím skenů odhalilo dvě přerušení: mezi naším fol. 55 a 56 chybějí "
        "<b>2 listy</b> (st. fol. 33–34, uvnitř komputu) a mezi fol. 68 a 70 <b>4 listy</b> "
        "(st. fol. 42–45, na přechodu komputus → Astrolabium) — patrně ztracené. V edici jsou "
        "tato místa vyznačena přímo u příslušných folií (fol. 56 a 70).</li>"
        "<li><b>Čtyři hlavní písařské ruce.</b> Rozlišili jsme je (A Carchesius 1587 · "
        "B Mikuláš Petr 1628 · C orlojník-astronom ~1641–42 · D ~1689) syntézou paleografie, "
        "<b>počítačové analýzy písma</b> a obsahu/datace. Kniha tedy nevznikla najednou r. 1587, "
        "ale <b>narůstala po vrstvách</b> přes celé století. Např. <b>Astrolabium parvum je "
        "vlastní český překlad orlojníka C</b> (~1642); téže ruce (orlojníka C) jsou přiřazeny "
        "i další části — komputistické tabulky a próza (fol. 50, 55–69) a vsuvka o přestavbě "
        "měsíční koule (fol. 22).</li>"
        "<li><b>Doklad pro vznik orloje r. 1410.</b> Přeřazení vzniku orloje od legendárního "
        "„mistra Hanuše (~1490)“ k r. <b>1410</b> stojí na <b>pozdějším přípisku na fol. 38</b>, "
        "který odkazuje na vložený List purkmistra — to je opora datace Z. Horského.</li>"
        "<li><b>Přesně datované pozorování (1. 11. 1642).</b> Astrolabium nese jediné přesně "
        "datované noční pozorování. <b>Ověřili jsme je výpočtem</b>: Slunce na 8° Štíra, Měsíc "
        "na 1° Ryb, západ Slunce 16:48, kulminace Měsíce ~19:48 — vše souhlasí s moderním "
        "přepočtem na 1–2 minuty a potvrzuje rok 1642 (gregoriánský kalendář).</li>"
        "<li><b>Systematická chyba ze stáří tabulek.</b> Slunce i Měsíc leží shodně o ~1° níže "
        "než pravá poloha. Že je odchylka u obou stejná je <b>průkazem</b>, že nejde o chybu "
        "data ani měření, ale o <b>precesní zastarání předrudolfínských tabulek</b> (o řádově "
        "století starších), z nichž orlojník počítal; v rozdílu poloh Slunce a Měsíce se chyba "
        "vykrátí, takže výsledný čas přesto sedí.</li>"
        "<li><b>Všechny číselné tabulky dekódovány a ověřeny.</b> Komputistické tabulky "
        "(nedělní písmena, epakty, východ Slunce, intervaly Velikonoc, věčný kalendář, "
        "násobilka) jsme rozluštili podle dobových vzorců a <b>nezávisle ověřili buňku po "
        "buňce</b> — včetně obou intervalových tabulí Velikonoc (juliánská f60 souhlasí ve "
        "všech 133 buňkách). Jediná drobná výhrada: u gregoriánského dvojčete <b>f61</b> sedí "
        "191 z 210 buněk, zbylé neshody leží v proslulé zóně <b>epakty 25</b> a čekají na "
        "kontrolu na originále.</li>"
        "<li><b>Dohledané předlohy.</b> Dvě části jsme ztotožnili s konkrétními tisky a porovnali: "
        "<b>Astrolabium parvum</b> je překlad spisu <b>Franze Rittera</b> (Norimberk 1613) — "
        "shodují se pasáže i figury (vč. desky pro pól 50°), orlojník k němu přidal české hodiny "
        "a vlastní příklad 1642; <b>tabule f3</b> je Hájkova <b>„Tabule… k spravování orloje“ "
        "(1574)</b> zhotovená přímo pro orloj, jejíž tištěný originál se zřejmě nedochoval — f3 "
        "je tak pravděpodobně její vzácný svědek.</li>"
        "</ul>"
        "<h3>Metody a nástroje</h3>"
        "<p><b>Syntetická edice.</b> Text nevzniká pouhým strojovým přepisem, ale "
        "<b>kombinací zdrojů</b>: strojové rozpoznání rukopisu (HTR — <b>Transkribus</b> "
        "PyLaia, čeština i německý Kurrent, dva nezávislé běhy), <b>ruční korektura čtením "
        "skenu</b>, rozpoznání tabulek (<b>Docling</b> TableFormer) a externí opory — edice "
        "originálu 1570 (J. Teige, 1901) a přepisy z orloj.eu.</p>"
        "<p><b>Převzaté a zakázkové přepisy.</b> Paleografický přepis <b>německé verze Listu "
        "purkmistra</b> (fol. 51–52, novogotická kurzíva) pořídil <b>na zakázku profesionální "
        "paleograf</b>; <b>dobový český překlad</b> (fol. 53–54) je přepis, který z rukopisu "
        "pořídil a r. 1962 publikoval <b>Stanislav Macháček</b> — jeho přepis jsme zarovnali "
        "na vlastní HTR. Přepis "
        "<b>Astrolabia parvum</b> (fol. 70–79) je převzat z <b>orloj.eu</b> — přepis "
        "<b>Pavel Baudisch</b>, odborné poznámky a analýza <b>Petr Král</b> a kol. (Český "
        "spolek horologický). <b>Každý externí přepis jsme navíc vždy porovnali se strojovým "
        "rozpoznáním (HTR) téhož folia</b> — slouží tak jako vzájemná kontrola, ne jako "
        "nekriticky převzatý text.</p>"
        "<p><b>Ověřování výpočtem.</b> Číselné tabulky byly přepsány ručně (strojové čtení "
        "číslic selhává) a poté <b>deterministicky ověřeny nezávislým výpočtem</b> — dobové "
        "komputistické vzorce a astronomie (Meeus); ověřovací skripty jsou součástí "
        "repozitáře.</p>"
        "<p><b>Počítačová identifikace písaře (writer-ID).</b> Ruce jsme nejdřív roztřídili "
        "<b>vlastním skriptem</b> (<code>cluster_hands.py</code>, otevřený, licence EUPL-1.2), "
        "inspirovaným běžnými postupy <i>writer-identification</i> / <i>script-classification</i>. "
        "Postup: ze <b>4132 řádkových výřezů</b> všech 81 folií se neuronovou sítí <b>ResNet-50</b> "
        "(předtrénovanou na ImageNetu, knihovna <i>torchvision</i>) vzaly <b>texturní rysy</b> ze "
        "střední vrstvy (drží <i>duktus</i> písma, ne obsah), zprůměrovaly přes drobné výřezy podél "
        "tahů a L2-normalizovaly; volitelně se přidala ruční stylometrie (sklon, tloušťka tahu, "
        "hustota inkoustu). Vektory se zobrazily do nízkého rozměru (<b>UMAP</b>) a shlukovaly "
        "(<b>HDBSCAN</b>). Skript <b>spolehlivě oddělí hrubé rozdíly</b> — německý Kurrent "
        "(fol. 51–52) vyšel jako čistý samostatný shluk — a mapuje rejstříky kodexu "
        "(próza × tabulky × němčina). <b>Doložená mez:</b> na atribuci <b>jednotlivé krátké "
        "glosy</b> skript nestačí — cílené nejbližší-ruka srovnání dalo všem kandidátům "
        "podobnost 0,96–0,99 bez odstupu a kontrola selhala (přípisek fol. 22, o němž z písma "
        "víme, že je ruka C, vyšel nejblíž ruce A); na krátkém fragmentu dominuje morfologie "
        "výřezu, ne identita ruky. Writer-ID je proto <b>jen jedno ze tří kritérií</b> atribuce — "
        "jednotlivé přiřazení stojí na paleografii a obsahu/dataci, ne na skriptu. Použitý "
        "open-source základ: PyTorch/<i>torchvision</i> (ResNet-50), <i>umap-learn</i>, "
        "<i>hdbscan</i>.</p>"
        "<p><b>Čtenářské rozhraní.</b> Český text lze zobrazit ve <b>třech režimech</b> "
        "(diplomatický / normalizovaný / Teige), s <b>číslováním řádků podle předlohy</b> "
        "a rozbalovacími edičními poznámkami; okrajové přípisky stojí ve vnější margině "
        "jako v rukopise.</p>"
        '<p class="more">▸ Podrobné vymezení pramene, metody, písařských rukou, '
        "ověření tabulek, práv a poděkování viz <b>O edici</b> níže.</p>"
        "</section>"
    )
    is_1570 = "1570" in work_slug
    if is_1570:
        tiraz = _tiraz_1570(ahmp_a)
        uvod = ""
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
{uvod}
{_status_html(work_slug)}
{'' if is_1570 and not has_marginalia_page else '<p class="marg-link">▸ <a href="marginalia.html">Rozbor marginálií</a> — přepisy okrajových přípisků folií 13–46, co přinášejí, identifikace písaře a datace.</p>'}
{tiraz}
<p class="note">{'Autograf Jana Táborského (1570), jeden svázaný celek.' if is_1570 else 'Jedna svázaná kniha (více částí, jeden celek).'} <span class="teige-badge">T</span> = {'folia, k nimž Teigeho edice originálu (1901) poskytuje srovnávací znění' if is_1570 else 'folia s opisem Táborského zprávy, kde existuje referenční edice (Teige 1901); ostatní oddíly referenci nemají'}.
Označeno {n_teige} z {len(pages)} folií. {'Hranice oddílů jsou odvozené automaticky (heuristika).' if is_1570 else 'Oddíly odpovídají částem knihy; celý Carchesiův opis Táborského zprávy (fol. 5–49) je jeden oddíl.'}</p>
{"".join(blocks)}</main>
<footer>{len(pages)} folií. Diplomatická edice z Transkribus HTR.</footer>
<script>document.querySelectorAll('.status tbody tr[data-href]').forEach(function(tr){{tr.addEventListener('click',function(e){{if(e.target.closest('a'))return;location.href=tr.dataset.href;}});}});</script>
</body></html>"""


_CSS = """
:root{--ink:#2b2b2b;--paper:#f7f3ea;--accent:#7a5c2e;}
*{box-sizing:border-box}
body{margin:0;font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:#e9e3d6}
header{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid #cdbf9f;
  padding:.5rem 1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
header h1{font-size:1rem;margin:0;flex:1 1 auto}
header .home{font-size:1.3rem;text-decoration:none;color:var(--accent)}
.modes{display:flex;gap:.9rem;align-items:center;flex-wrap:wrap}
.modes .ctl{display:inline-flex;align-items:center;gap:.5rem;padding:.1rem .55rem;
  background:#f1ead8;border:1px solid #ddd0ad;border-radius:6px}
.modes .ctl-lbl{font-family:system-ui,sans-serif;font-size:.62rem;text-transform:uppercase;
  letter-spacing:.05em;color:#9a8d70}
.modes label{cursor:pointer;font-family:system-ui,sans-serif;font-size:.8rem}
.modes .ctl-app{font-family:system-ui,sans-serif;font-size:.8rem;cursor:pointer}
.modes input{vertical-align:middle}
.pager{max-width:min(97vw,86rem);margin:.6rem auto 0;padding:0 1rem;display:flex;justify-content:space-between;
  align-items:center;font-family:system-ui,sans-serif;font-size:.85rem}
.pager a{color:var(--accent);text-decoration:none}
.pager .folno{color:#6b6256}
.pager .oldfol{color:#8a7a52;font-variant:small-caps}
.missing-leaves{margin:0 0 1rem;padding:.55rem .8rem;background:#fbe7d6;border:1px solid #d8a25a;
  border-left:4px solid #b8600b;border-radius:4px;font-family:system-ui,sans-serif;
  font-size:.84rem;line-height:1.5;color:#5a3a12}
.pager a[hidden]{visibility:hidden}
main{max-width:62rem;margin:1rem auto 3rem;padding:0 1rem}
/* folio pages use (almost) the full screen width so lines need not wrap */
main.leaf{max-width:min(97vw,86rem)}
.folio{background:var(--paper);border:1px solid #cdbf9f;border-radius:4px;padding:1.2rem 1.6rem;
  box-shadow:0 1px 3px rgba(0,0,0,.12)}
/* two-zone leaf: text column + a dedicated outer margin (recto→right, verso→left),
   mirroring the manuscript page; marginalia & editorial side-notes live there. */
/* Text column is wide enough that a manuscript line fits without wrapping
   (≈99 % of lines ≤ 121 chars → ~64rem incl. the number gutter); the outer
   margin stays a fixed 15rem. Both hug the left so the margin sits near the text. */
.folio-2col{display:grid;gap:1.7rem;align-items:start;justify-content:start;
  grid-template-columns:minmax(0,64rem) 15rem}
.folio-2col.verso{grid-template-columns:15rem minmax(0,64rem)}
.folio-2col.verso .textcol{grid-column:2;grid-row:1}
.folio-2col.verso .margin-col{grid-column:1;grid-row:1}
.textcol{min-width:0}
.margin-col{min-width:0;font-family:system-ui,sans-serif}
.margin-col:empty{display:none}
.region{margin:0 0 .6rem}
/* notes in the outer margin — original scribal glosses (brown) vs editorial (green) */
.m-note{font-size:.76rem;line-height:1.5;border-radius:4px;padding:.45rem .62rem;margin:0 0 .7rem}
.m-note .mlabel{display:block;font-size:.6rem;letter-spacing:.05em;text-transform:uppercase;
  margin-bottom:.22rem}
.m-note p{margin:.25rem 0 0}
.m-note p:first-of-type{margin-top:0}
.m-orig{background:#f5efe0;border:1px solid #d8ccae;color:#5a5046}
.m-orig .mlabel{color:#9a8d70}
.m-orig.later{border-left:3px solid #5a6b8c}
.m-ed{background:#eaf3ec;border:1px solid #bcd9c2;border-left:3px solid #2f6b3a;color:#39573f}
.m-ed .mlabel{color:#2f6b3a}
/* fallback for raw-region marginalia on non-clean folios */
.region.marginalia{font-family:system-ui,sans-serif;font-size:.8rem;color:#5a5046;background:#f5efe0;
  border:1px solid #d8ccae;border-radius:4px;padding:.45rem .65rem;margin:.4rem 0}
@media(max-width:760px){
  .folio-2col,.folio-2col.verso{grid-template-columns:1fr}
  .folio-2col.verso .textcol,.folio-2col.verso .margin-col{grid-column:1;grid-row:auto}
}
/* --- lineated transcription with margin line numbers (citable) --- */
.lines{position:relative}
.ln{display:block;position:relative;padding-left:2.4rem;line-height:1.75}
.lno{position:absolute;left:0;width:1.9rem;text-align:right;top:.15em;
  font-family:system-ui,sans-serif;font-size:.66rem;color:#b6a982;user-select:none;
  text-decoration:none;cursor:pointer;opacity:0;transition:opacity .12s}
.lno.show{opacity:.85}
.ln:hover .lno{opacity:.85}
a.lno:hover{color:var(--accent);text-decoration:underline}
.ln:target{background:#fbf1cf;border-radius:2px;box-shadow:0 0 0 3px #fbf1cf}
.ln.flash{animation:lnflash 1.1s ease-out}
@keyframes lnflash{0%{background:#f4dd8a}100%{background:transparent}}
.pbreak{display:block;height:.7rem}
/* čtecí (continuous) sazba: join lines into justified prose at a comfortable
   measure (the wide no-wrap column is for the lineated „řádky" view only) */
body.layout-flow .lines{text-align:justify;line-height:1.8;hyphens:auto;max-width:46rem}
body.layout-flow .ln{display:inline;padding-left:0;padding-right:0}
body.layout-flow .ln::after{content:" "}
body.layout-flow .lno{display:none}
body.layout-flow .ln:target{box-shadow:none}
body.layout-flow .pbreak{display:block;height:0;margin-bottom:.85rem}
/* editorial-apparatus marks ([?], expansions); hidden by the „ediční značky" toggle */
.ed{color:#2f6b3a}
body.app-off .ed{display:none}
.ed-note{margin:.9rem 0 .2rem;font-family:system-ui,sans-serif;font-size:.82rem;
  line-height:1.55;background:#eaf3ec;border-left:3px solid #2f6b3a;border-radius:3px;
  padding:.1rem .7rem;color:#39573f}
.ed-note summary{cursor:pointer;font-weight:600;color:#2f6b3a;padding:.35rem 0}
.ed-note p{margin:.4rem 0}
body.app-off .ed-note,body.app-off .clean-flag{display:none}
.heading{font-size:1.05rem;font-weight:bold}
.table-todo{font-family:system-ui,sans-serif;font-size:.85rem;color:#6b6256;background:#f6f1e4;
  border:1px dashed #cdbf9f;border-radius:4px;padding:.7rem .9rem}
.table-todo a{color:#7a5c2e}
/* editorial table caption (not original text) → green, like the side ed-notes */
.table-cap{font-family:system-ui,sans-serif;font-size:.85rem;margin:.2rem 0 .6rem;
  color:#2f6b3a;font-weight:600}
.table-note{font-family:system-ui,sans-serif;font-size:.82rem;color:#39573f;margin:.45rem 0}
.table-note.verified{color:#2f6b3a}
.ms-heading{margin:.3rem 0 .7rem;line-height:1.55}
.ms-prose{margin:1rem 0;padding:.6rem .8rem;background:#f7f3ea;border-left:3px solid #c9b88a;
  line-height:1.6}
.ms-prose-label{display:block;font-family:system-ui,sans-serif;font-size:.72rem;
  text-transform:uppercase;letter-spacing:.04em;color:#8a7d63;margin-bottom:.3rem}
.ms-prose p{margin:.45rem 0}
.ms-prose-ed{font-size:.86rem;color:#39573f}
.zod{font-variant-emoji:text;font-family:"Segoe UI Symbol","Noto Sans Symbols2","DejaVu Sans",
  "Apple Symbols",serif;color:#5a4a2a}
.ms-heading-label{display:block;font-family:system-ui,sans-serif;font-size:.72rem;
  text-transform:uppercase;letter-spacing:.04em;color:#8a7d63;margin-bottom:.25rem}
.method-note{margin:.7rem 0;font-family:system-ui,sans-serif;font-size:.82rem;line-height:1.5;
  background:#eaf3ec;border-left:3px solid #2f6b3a;border-radius:3px;padding:.2rem .7rem}
.method-note summary{cursor:pointer;font-weight:600;color:#2f6b3a;padding:.35rem 0}
.method-note p{margin:.45rem 0}
.method-note code{font-size:.82em;background:#dce8df;padding:0 .2em;border-radius:2px}
.page-table{border-collapse:collapse;margin:.6rem 0;font-family:system-ui,sans-serif;font-size:.85rem}
.page-table td{border:1px solid #cdbf9f;padding:.15rem .4rem;text-align:center;min-width:1.6rem}
.fig-svg{margin:1rem 0;text-align:center}
.fig-svg svg{max-width:240px;height:auto;background:#fffdf8;border:1px solid #e6ddc7;border-radius:4px;padding:.4rem}
.fig-svg figcaption{font-family:system-ui,sans-serif;font-size:.78rem;color:#8a7d63;margin-top:.35rem}
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
.section-label{max-width:min(97vw,86rem);margin:.3rem auto 0;padding:0 1rem;font-family:system-ui,sans-serif;
  font-size:.78rem;color:#7a5c2e;text-transform:uppercase;letter-spacing:.04em}
.tiraz{font-family:system-ui,sans-serif;font-size:.85rem;line-height:1.5;background:#f6f1e4;
  border:1px solid #cdbf9f;border-radius:5px;padding:.8rem 1.1rem;margin:0 0 1.4rem}
.tiraz h2{font-size:1rem;margin:.1rem 0 .5rem;border:0}
.tiraz p{margin:.4rem 0}
.tiraz .warn{background:#fbeed6;border-left:3px solid #b8860b;padding:.4rem .6rem;border-radius:3px}
.tiraz .teige{background:#eef1f6;border-left:3px solid #5a6b8c;padding:.4rem .6rem;border-radius:3px}
.tiraz .verify{background:#eaf3ec;border-left:3px solid #2f6b3a;padding:.4rem .6rem;border-radius:3px}
.tiraz .verify code{font-size:.82em;background:#dce8df;padding:0 .2em;border-radius:2px}
.tiraz a{color:#7a5c2e}
.uvod{font-family:Georgia,'Times New Roman',serif;font-size:.98rem;line-height:1.62;
  background:var(--paper);border:1px solid #cdbf9f;border-radius:5px;padding:1.1rem 1.4rem;margin:0 0 1.4rem}
.uvod h2{font-size:1.3rem;margin:.1rem 0 .3rem;border:0}
.uvod h2+.lead{margin-top:0;color:#6b6256;font-style:italic}
.uvod h3{font-size:1.02rem;margin:1.1rem 0 .3rem;color:#5a4a2e}
.uvod p{margin:.5rem 0}
.uvod ul{margin:.4rem 0;padding-left:1.2rem}
.uvod li{margin:.35rem 0}
.uvod a{color:#7a5c2e}
.uvod code{font-size:.86em;background:#efe7d4;padding:0 .25em;border-radius:2px}
.uvod .more{font-size:.86rem;color:#6b6256;margin-top:1rem}
.status{font-family:system-ui,sans-serif;font-size:.82rem;border-collapse:collapse;width:100%;margin:0 0 1.4rem}
.status caption{text-align:left;font-weight:bold;font-size:1rem;margin-bottom:.4rem;color:#3a342a}
.status th,.status td{border:1px solid #cdbf9f;padding:.3rem .55rem;text-align:left;vertical-align:top}
.status th{background:#efe7d3}
.status tbody tr:nth-child(even){background:#faf6ec}
.status tbody tr[data-href]{cursor:pointer}
.status tbody tr[data-href]:hover{background:#f0e6c8}
.status td a{color:#7a5c2e;text-decoration:none;font-weight:600}
.status td a:hover{text-decoration:underline}
.status td.hand{white-space:nowrap;color:#5a5046;font-size:.8rem;font-variant-numeric:tabular-nums}
.marg-link{font-family:system-ui,sans-serif;font-size:.9rem;margin:.6rem 0 1.2rem;
  padding:.5rem .7rem;background:#f0e6c8;border-left:3px solid #b8860b;border-radius:3px}
.marg-link a{color:#7a5c2e;font-weight:700}
.marg-item{margin:1.1rem 0;padding-top:.6rem;border-top:1px solid #e2d7bb}
.marg-item h3{font-family:system-ui,sans-serif;font-size:.95rem;margin:.2rem 0 .5rem;color:#3a342a}
.marg-item h3 a{font-size:.8rem;font-weight:normal;color:#7a5c2e}
.marg-ctx,.mctx{color:#6b6256;font-weight:normal}
.marg-row{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-start}
.marg-figs{flex:0 0 210px;display:flex;flex-direction:column;gap:5px}
.marg-figs img{max-width:210px;border:1px solid #d8cba8;background:#fff;border-radius:2px;opacity:.95}
.marg-body{flex:1 1 360px}
.marg-notes{margin:0 0 .5rem;padding-left:1.2rem;font-size:.95rem;line-height:1.65}
.marg-notes li{margin:.2rem 0}
.marg-add{font-size:.95rem;line-height:1.6;margin:.5rem 0;padding:.5rem .7rem;
  background:#f3ece0;border-left:3px solid #9c6b3a;border-radius:3px}
.t-ADD{background:#e6d3bf;color:#7a3b1e}
.mtag{display:inline-block;font-family:system-ui,sans-serif;font-size:.68rem;
  text-transform:uppercase;letter-spacing:.03em;padding:.05rem .35rem;border-radius:3px;
  margin-right:.35rem;vertical-align:.08em}
.t-IDX{background:#e7eecd;color:#4a5a1e}
.t-LAT{background:#dde6f0;color:#33506e}
.t-HIST{background:#f0dcd0;color:#7a3b1e}
.t-NB{background:#eee;color:#555}
.status .b-done{color:#2e7d32;font-weight:bold;white-space:nowrap}
.status .b-partial{color:#b8860b;font-weight:bold;white-space:nowrap}
.status .b-todo{color:#a3332b;font-weight:bold;white-space:nowrap}
.status .b-na{color:#999;white-space:nowrap}
.status-note{font-family:system-ui,sans-serif;font-size:.8rem;line-height:1.5;color:#6b6256;
  background:#f6f1e4;border-left:3px solid #b8860b;padding:.5rem .7rem;border-radius:3px;margin:-.8rem 0 1.4rem}
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
#ed-toast{position:fixed;bottom:1.2rem;left:50%;transform:translateX(-50%) translateY(1rem);
  background:#2b2b2b;color:#f7f3ea;font-family:system-ui,sans-serif;font-size:.8rem;
  padding:.5rem .95rem;border-radius:6px;opacity:0;pointer-events:none;z-index:20;
  transition:opacity .18s,transform .18s;box-shadow:0 2px 10px rgba(0,0,0,.25)}
#ed-toast.show{opacity:.97;transform:translateX(-50%) translateY(0)}
"""

_JS = """
(function(){
  const B=document.body;
  function store(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  function load(k){try{return localStorage.getItem(k)}catch(e){return null}}
  function setMode(m){
    store('edmode',m);                                  // zachovej preferenci uživatele
    var eff=(m==='teige'&&!B.classList.contains('has-teige'))?'dipl':m;  // Teige jen kde dává smysl
    B.classList.remove('mode-dipl','mode-norm','mode-teige');B.classList.add('mode-'+eff);
    for(const r of document.querySelectorAll('input[name=mode]'))r.checked=(r.value===eff);}
  function setLayout(l){
    B.classList.remove('layout-lined','layout-flow');B.classList.add('layout-'+l);
    for(const r of document.querySelectorAll('input[name=layout]'))r.checked=(r.value===l);
    store('edlayout',l);}
  function setApp(on){
    B.classList.toggle('app-off',!on);
    const c=document.getElementById('appToggle');if(c)c.checked=on;
    store('edapp',on?'1':'0');}
  document.addEventListener('DOMContentLoaded',function(){
    const sm=load('edmode');if(sm)setMode(sm);
    const sl=load('edlayout');if(sl)setLayout(sl);
    const sa=load('edapp');if(sa!==null)setApp(sa==='1');
    for(const r of document.querySelectorAll('input[name=mode]'))r.addEventListener('change',()=>setMode(r.value));
    for(const r of document.querySelectorAll('input[name=layout]'))r.addEventListener('change',()=>setLayout(r.value));
    const c=document.getElementById('appToggle');if(c)c.addEventListener('change',()=>setApp(c.checked));
    let tt;
    function toast(msg){
      let el=document.getElementById('ed-toast');
      if(!el){el=document.createElement('div');el.id='ed-toast';document.body.appendChild(el);}
      el.textContent=msg;el.classList.add('show');
      clearTimeout(tt);tt=setTimeout(()=>el.classList.remove('show'),1900);}
    document.addEventListener('click',function(e){
      const a=e.target.closest('a.lno');if(!a)return;
      e.preventDefault();
      const id=a.getAttribute('href').slice(1);
      const wrap=a.closest('.lines');const fol=wrap?wrap.getAttribute('data-folio'):'';
      const ref='fol. '+fol+', ř. '+a.getAttribute('data-n');
      const url=location.href.split('#')[0]+'#'+id;
      try{history.replaceState(null,'','#'+id)}catch(_){location.hash=id;}
      const t=document.getElementById(id);
      if(t){t.classList.remove('flash');void t.offsetWidth;t.classList.add('flash');}
      const cite=ref+' — '+url;
      if(navigator.clipboard&&navigator.clipboard.writeText){
        navigator.clipboard.writeText(cite).then(()=>toast('Zkopírováno: '+ref)).catch(()=>toast(ref));
      }else toast(ref);
    });
    document.addEventListener('keydown',function(e){
      if(e.target.tagName==='INPUT')return;
      if(e.key==='ArrowLeft'){const a=document.querySelector('.pager .prev');if(a&&!a.hidden)location.href=a.getAttribute('href');}
      if(e.key==='ArrowRight'){const a=document.querySelector('.pager .next');if(a&&!a.hidden)location.href=a.getAttribute('href');}
    });
  });
})();
"""


# AHMP (Bach pragapublica) link policy. AHMP has NO stable per-scan URL:
#  - ``permalink?xid=<XID>`` is the canonical, persistent link, but resolves to the
#    document (scanIndex is ignored server-side — always the first scan);
#  - the per-scan jump ``Zoomify.action…&scanIndex=N`` is a session-bound *action* URL
#    that returns „Platnost stránky vypršela" when opened cold → not a stable citation.
# We therefore link the stable permalink and carry the folio (= scan N) in the link text;
# the reader opens scan N in the viewer. Scans are not republished here.
_AHMP_PERMALINK = "https://katalog.ahmp.cz/pragapublica/permalink"


def _ahmp_xid(permalink: str | None) -> str | None:
    if not permalink or "xid=" not in permalink:
        return None
    return permalink.split("xid=", 1)[1].split("&", 1)[0]


def _folio_ahmp_url(permalink: str | None, page_nr: int) -> str | None:
    """Stable AHMP link for a folio = the canonical document permalink.

    AHMP exposes no stable per-scan URL, so we return the persistent
    ``permalink?xid=<XID>``; the target folio (scan number) is conveyed in the
    link text instead. Scans are not republished — this only links out to AHMP.
    """
    xid = _ahmp_xid(permalink)
    if not xid:
        return None
    return f"{_AHMP_PERMALINK}?xid={xid}"


def build_edition(
    work_dir: Path, *, title: str, ahmp_permalink: str | None = None,
    teige_path: Path | None = None, embed_scan: bool = False,
) -> Path:
    work_dir = Path(work_dir)
    work_slug = work_dir.name
    binding_notes = _BINDING_NOTE_1570 if "1570" in work_slug else {}
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
        tuple[int, list[TextRegion], list[Table], str, str | None, list[str], list[str], bool]
    ] = []
    tables_dir = work_dir / "tables"            # raw Docling — only flags a table page
    tables_clean_dir = work_dir / "tables_clean"  # verified, rendered as a grid
    figures_dir = work_dir / "figures"
    for xf in xml_files:
        page_nr = int(xf.stem)
        xml = xf.read_text(encoding="utf-8")
        regions = parse_page_xml(xml)
        # Only verified tables (tables_clean/) are rendered; raw Docling OCR of handwritten
        # table cells is unreliable, so it is NOT shown — it just marks a table page.
        tables: list[Table] = []
        clean_tbl = tables_clean_dir / f"{page_nr:04d}.json"
        if clean_tbl.exists():
            from transcribus.processing.docling_tables import tables_from_json

            tables = tables_from_json(clean_tbl.read_text(encoding="utf-8")) or []
        is_table_page = bool(tables) or (tables_dir / f"{page_nr:04d}.json").exists()
        fig_sidecar = figures_dir / f"{page_nr:04d}.json"
        fig_names = json.loads(fig_sidecar.read_text()) if fig_sidecar.exists() else []
        clean_file = work_dir / "clean" / f"{page_nr:04d}.txt"
        clean_lines = (
            [ln for ln in clean_file.read_text(encoding="utf-8").splitlines()]
            if clean_file.exists() else []
        )
        plain = " ".join(line for r in regions for line in r.lines if line.strip())
        passage = teige_index.align(plain) if (teige_index and plain) else None
        entries.append(
            (page_nr, regions, tables, plain, passage, fig_names, clean_lines, is_table_page)
        )

    matched = {e[0] for e in entries if e[4]}
    sections = derive_sections(matched, total, work_slug=work_slug)
    folio_section = {n: label for _k, lo, hi, label in sections for n in range(lo, hi + 1)}

    # NOTE: no AHMP reproduction is republished (figures or whole pages) — each folio
    # only links out to the AHMP viewer. Embedding would require an AHMP agreement
    # (<=500px longer side + watermark + "internet" purpose stated in the contract).

    # Pass 2: write per-folio pages + index.
    toc: dict[int, tuple[str, bool]] = {}
    marg_items: list[dict] = []
    for page_nr, regions, tables, plain, passage, fig_names, clean_lines, is_tbl in entries:
        doc = _page_doc(
            title=title, page_nr=page_nr, total=total, regions=regions,
            ahmp_url=_folio_ahmp_url(ahmp_permalink, page_nr), teige_passage=passage,
            section_label=folio_section.get(page_nr, ""), tables=tables, figures=fig_names,
            clean_lines=clean_lines, embed_scan=embed_scan, table_page=is_tbl,
            binding_note=binding_notes.get(page_nr, ""),
        )
        (out_dir / f"p{page_nr:04d}.html").write_text(doc, encoding="utf-8")
        # _FOLIO_SNIP a _TABLE_CAPTIONS jsou specifické pro orlojní knihu 1587 —
        # pro originál 1570 je nepoužívej (popisky by neseděly na jeho folia).
        snip = None if "1570" in work_slug else _FOLIO_SNIP.get(page_nr)
        if not snip:
            if binding_notes.get(page_nr):
                snip = binding_notes[page_nr].strip("[]").split(" — ")[0]
            elif (tables or is_tbl) and "1570" not in work_slug:
                snip = _TABLE_CAPTIONS.get(page_nr, "[tabulka]")
            elif plain:
                snip = plain[:80] + "…"
            else:
                snip = "[vyobrazení]" if fig_names else "[prázdná]"
        toc[page_nr] = (snip, passage is not None)
        _main, marg_lines = _split_marginalia(clean_lines)
        notes = _marg_notes(marg_lines)
        adds = _later_additions(clean_lines)
        if notes or adds:
            marg_items.append({
                "page": page_nr, "label": _FOLIO_SNIP.get(page_nr, ""),
                "notes": [(n, *_marg_category(n)) for n in notes],
                "adds": adds,
                "imgs": _marg_crops(work_dir, out_dir, page_nr) if notes else [],
            })

    if marg_items:
        (out_dir / "marginalia.html").write_text(
            _marginalia_doc(title, marg_items), encoding="utf-8"
        )

    index = out_dir / "index.html"
    index.write_text(
        _index_doc(
            title, sections, toc, ahmp_permalink,
            work_slug=work_slug, has_marginalia_page=bool(marg_items),
        ),
        encoding="utf-8",
    )
    return index
