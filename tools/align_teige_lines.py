# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Global per-line Teige alignment for the 1570 ORIGINAL (mode B).

Aligns the per-line HTR of the 1570 autograph to Teige's 1901 edition by a single
global word-level difflib match, projects the Teige span onto each HTR line, and flags
low-confidence / unmatched lines for diplomatic check. Output: work/orloj1570/teige_lines.json.
"""
from __future__ import annotations

import difflib
import glob
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

sys.path.insert(0, "src")

from transcribus.processing.teige import fold  # noqa: E402

WORD = re.compile(r"\S+")


def htr_lines(path: str) -> list[str]:
    """Return the Unicode text of every TextLine in a PAGE-XML file, in order."""
    xml = open(path, encoding="utf-8").read()
    ns = {"p": re.search(r'xmlns="([^"]+)"', xml).group(1)}
    root = ET.fromstring(xml)
    out = []
    for tl in root.findall(".//p:TextLine", ns):
        u = tl.find(".//p:Unicode", ns)
        out.append((u.text or "") if u is not None else "")
    return out


def main() -> None:
    teige = open("data/teige_taborsky.txt", encoding="utf-8").read()
    pw = WORD.findall(teige)
    pwf = [fold(w) for w in pw]
    pages = sorted(glob.glob("work/orloj1570/page_xml/*.xml"))

    # Global folded-word sequence of the HTR, each word tagged with (page, line).
    seq: list[str] = []
    tag: list[tuple[str, int]] = []
    lines_by_pg: dict[str, list[str]] = {}
    for px in pages:
        pn = px.split("/")[-1][:-4]
        lns = htr_lines(px)
        lines_by_pg[pn] = lns
        for li, ln in enumerate(lns):
            for w in WORD.findall(ln):
                f = fold(w)
                if f:
                    seq.append(f)
                    tag.append((pn, li))

    # Match HTR word sequence to Teige word sequence; map HTR index -> Teige index.
    sm = difflib.SequenceMatcher(None, seq, pwf, autojunk=False)
    t2p: dict[int, int] = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("equal", "replace"):
            for k in range(i2 - i1):
                jj = j1 + min(k, max(0, j2 - j1 - 1))
                if jj < len(pw):
                    t2p[i1 + k] = jj

    # Per (page, line): the Teige span + a coverage confidence.
    byline: dict[tuple[str, int], list[int]] = defaultdict(list)
    nwline: dict[tuple[str, int], int] = defaultdict(int)
    for ti, (pn, li) in enumerate(tag):
        nwline[(pn, li)] += 1
        if ti in t2p:
            byline[(pn, li)].append(t2p[ti])

    allres: dict[str, list[dict]] = {}
    low: list[tuple[str, int, str, str, float]] = []
    for pn, lns in lines_by_pg.items():
        res = []
        for li, ln in enumerate(lns):
            idxs = byline.get((pn, li), [])
            nw = nwline.get((pn, li), 0)
            if idxs:
                lo, hi = min(idxs), max(idxs)
                tt = " ".join(pw[lo:hi + 1])
                conf = round(len(idxs) / max(nw, 1), 2)
            else:
                tt, conf = "", 0.0
            res.append({"htr": ln, "teige": tt, "conf": conf, "nw": nw})
            if nw >= 3 and (conf < 0.4 or not tt.strip()):
                low.append((pn, li, ln, tt, conf))
        allres[pn] = res

    out = "work/orloj1570/teige_lines.json"
    json.dump(allres, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"disputed lines (nw>=3, conf<0.4 or empty): {len(low)} -> {out}")
    print("=== sporné řádky (k dořešení skenem) ===")
    for pn, li, ln, _tt, c in low[:25]:
        print(f"  {pn} ř{li:2} c={c}: '{ln[:46]}'")


if __name__ == "__main__":
    main()
