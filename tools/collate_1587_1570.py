# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Collate the 1587 Carchesius copy (fol. 5–49) DIRECTLY against the 1570 Táborský
autograph (AHMP sign. 1867), witness vs witness — no Teige editorial intermediary.

Motivation: comparing the copy to Teige's 1901 edition mixes genuine 1570↔1587
scribal variants with Teige's own normalization. This script compares the two
manuscripts' OWN diplomatic transcriptions:
  * 1587 copy  : work/orloj1587/clean/*.txt   (hand-corrected)
  * 1570 orig. : work/orloj1570/page_xml/*.xml (HTR Unicode lines)

Both folded (teige.fold) for the alignment; non-equal opcodes → variants.

IMPORTANT caveat: the 1570 side is UNVERIFIED HTR, so divergences mix real
witness variants with HTR noise on the 1570 side. Structural/lexical differences
are reliable; fine orthography needs the scan to adjudicate. Output:
work/orloj1587/collation_1570.{json,md} + summary.
"""

from __future__ import annotations

import difflib
import glob
import json
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, "src")

from transcribus.processing.teige import fold  # noqa: E402

WORD = re.compile(r"\w+", re.UNICODE)
BRACKET = re.compile(r"\[[^\]]*\]")
COPY_FOLIOS = range(5, 50)


def copy_words() -> list[tuple[str, str, int, int]]:
    out: list[tuple[str, str, int, int]] = []
    for n in COPY_FOLIOS:
        try:
            lines = open(f"work/orloj1587/clean/{n:04d}.txt", encoding="utf-8").read().splitlines()
        except FileNotFoundError:
            continue
        for li, raw in enumerate(lines, start=1):
            s = raw.strip()
            if not s or s.startswith("[") or s.isdigit():
                continue
            s = BRACKET.sub(" ", s).replace("…", " ")
            for m in WORD.finditer(s):
                f = fold(m.group(0))
                if f:
                    out.append((m.group(0), f, n, li))
    return out


def autograph_words() -> list[tuple[str, str]]:
    """All TextLine Unicode words of the 1570 autograph HTR, in page/line order."""
    out: list[tuple[str, str]] = []
    for px in sorted(glob.glob("work/orloj1570/page_xml/*.xml")):
        xml = open(px, encoding="utf-8").read()
        m = re.search(r'xmlns="([^"]+)"', xml)
        ns = {"p": m.group(1)} if m else {}
        for tl in ET.fromstring(xml).findall(".//p:TextLine", ns):
            u = tl.find(".//p:Unicode", ns)
            t = (u.text or "") if u is not None else ""
            for mm in WORD.finditer(t):
                f = fold(mm.group(0))
                if f:
                    out.append((mm.group(0), f))
    return out


def main() -> None:
    cw = copy_words()
    aw = autograph_words()
    if not aw:
        raise SystemExit("autograf 1570 nemá text (work/orloj1570/page_xml prázdné?)")
    cf = [w[1] for w in cw]
    af = [w[1] for w in aw]
    print(f"opis 1587 (f5–49): {len(cw)} slov | autograf 1570 (HTR): {len(aw)} slov")

    sm = difflib.SequenceMatcher(None, cf, af, autojunk=False)
    KIND = {"replace": "záměna", "delete": "navíc v opisu", "insert": "chybí v opisu (má 1570)"}
    variants = []
    equal = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            equal += i2 - i1
            continue
        cseg, aseg = cw[i1:i2], aw[j1:j2]
        folio = cseg[0][2] if cseg else (cw[i1 - 1][2] if i1 else 0)
        line = cseg[0][3] if cseg else (cw[i1 - 1][3] if i1 else 0)
        variants.append({
            "kind": KIND[op], "folio": folio, "line": line,
            "copy": " ".join(w[0] for w in cseg),
            "orig1570": " ".join(w[0] for w in aseg),
            "n_copy": len(cseg), "n_orig": len(aseg),
            "ctx_before": " ".join(w[0] for w in cw[max(0, i1 - 4):i1]),
        })

    agree = 100 * equal / max(len(cf), 1)
    by_kind = {k: sum(1 for v in variants if v["kind"] == k) for k in KIND.values()}
    print(f"shoda slov (folded): {equal}/{len(cf)} = {agree:.1f} %")
    print("varianty:", ", ".join(f"{k}={n}" for k, n in by_kind.items()),
          f"| celkem {len(variants)}")
    big = sorted((v for v in variants if max(v["n_copy"], v["n_orig"]) >= 6),
                 key=lambda v: -max(v["n_copy"], v["n_orig"]))
    print(f"\nVětší strukturní rozdíly (≥6 slov): {len(big)}")
    for v in big[:12]:
        print(f"  f{v['folio']} ř{v['line']} {v['kind']} (opis {v['n_copy']}/1570 {v['n_orig']}): "
              f"OPIS: {v['copy'][:55]} | 1570: {v['orig1570'][:55]}")

    json.dump({"summary": {"copy_words": len(cw), "orig1570_words": len(aw),
                           "agreement_pct": round(agree, 1), "by_kind": by_kind,
                           "total_variants": len(variants)}, "variants": variants},
              open("work/orloj1587/collation_1570.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open("work/orloj1587/collation_1570.md", "w", encoding="utf-8") as fh:
        fh.write("# Přímá kolace: Carchesiův opis 1587 (f5–49) × autograf Táborského 1570\n\n")
        fh.write(f"Shoda slov (folded): **{agree:.1f} %** ({equal}/{len(cf)}). Varianty: "
                 + ", ".join(f"{k} {n}" for k, n in by_kind.items())
                 + f", celkem **{len(variants)}**.\n\n")
        fh.write("> Bez Teigeho mezičlánku — porovnání dvou rukopisných svědků. **1570 strana "
                 "je neověřené HTR** (a obsahuje i marginálie/glosy jako řádky), takže rozdíly "
                 "mísí skutečné varianty 1570↔1587 s HTR šumem a marginálním aparátem 1570; "
                 "strukturní a lexikální rozdíly jsou spolehlivé, jemný pravopis nutno ověřit "
                 "na skenu.\n\n")
        cur = None
        for v in variants:
            if v["folio"] != cur:
                cur = v["folio"]
                fh.write(f"\n## fol. {cur}\n\n")
            fh.write(f"- **ř.{v['line']} · {v['kind']}**: opis „{v['copy'] or '—'}“ × 1570 "
                     f"„{v['orig1570'] or '—'}“\n")
    print("\nuloženo: work/orloj1587/collation_1570.{json,md}")


if __name__ == "__main__":
    main()
