# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Collate the 1587 Carchesius copy (fol. 5–49) against Teige's 1570 edition.

Produces a *variant apparatus*: word-level differences between the copy and the
original, classified as substitutions, copy-only additions ("navíc v opisu") and
copy omissions ("chybí v opisu").

The comparison runs on FOLDED forms (teige.fold(): lowercase + orthography
normalization + diacritics stripped), so purely orthographic / spelling
differences are intentionally ignored — only *substantive* textual variants
surface. Method: one global word-level difflib alignment of the whole copy text
vs the whole Teige text, then the non-equal opcodes become variants, each mapped
back to the copy's folio + line.

Caveats baked into the output:
  * fol. 31–42 of the copy are not yet diplomatically line-checked, so some
    variants there are transcription/HTR noise, not genuine witness variants.
  * Teige edited the 1570 ORIGINAL; the copy is a different (1587) witness with
    its own later layer — large copy-only blocks (e.g. the 1587 colophon) are
    real differences, not errors.

Outputs: work/orloj1587/collation_teige.json (machine) and
work/orloj1587/collation_teige.md (human apparatus). Prints a summary.
"""

from __future__ import annotations

import difflib
import json
import re
import sys

sys.path.insert(0, "src")

from transcribus.processing.teige import fold  # noqa: E402

WORD = re.compile(r"\w+", re.UNICODE)
BRACKET = re.compile(r"\[[^\]]*\]")     # inline editorial / marginalia brackets
COPY_FOLIOS = range(5, 50)             # f5–49 = Carchesius copy of Táborského Zprávy
UNVERIFIED = set(range(31, 43))        # f31–42 not yet diplomatically checked


def copy_words() -> list[tuple[str, str, int, int]]:
    """Return (orig, folded, folio, line) for the running MAIN text of f5–49.

    Skips foliation numbers, bracketed marginalia / editorial notes, and inline
    [...] editorial spans; keeps only the scribe's running prose/verse.
    """
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


def teige_words() -> list[tuple[str, str]]:
    text = open("data/teige_taborsky.txt", encoding="utf-8").read()
    return [(m.group(0), fold(m.group(0))) for m in WORD.finditer(text)
            if fold(m.group(0))]


def main() -> None:
    cw = copy_words()
    tw = teige_words()
    cf = [w[1] for w in cw]
    tf = [w[1] for w in tw]
    print(f"opis (f5–49): {len(cw)} slov | Teige 1570: {len(tw)} slov")

    sm = difflib.SequenceMatcher(None, cf, tf, autojunk=False)
    KIND = {"replace": "záměna", "delete": "navíc v opisu", "insert": "chybí v opisu"}
    variants = []
    equal_words = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            equal_words += i2 - i1
            continue
        cseg, tseg = cw[i1:i2], tw[j1:j2]
        if cseg:
            folio, line = cseg[0][2], cseg[0][3]
        else:                                   # insert: anchor at preceding copy word
            folio = cw[i1 - 1][2] if i1 else 0
            line = cw[i1 - 1][3] if i1 else 0
        variants.append({
            "kind": KIND[op],
            "folio": folio,
            "line": line,
            "copy": " ".join(w[0] for w in cseg),
            "teige": " ".join(w[0] for w in tseg),
            "n_copy": len(cseg),
            "n_teige": len(tseg),
            "ctx_before": " ".join(w[0] for w in cw[max(0, i1 - 4):i1]),
            "ctx_after": " ".join(w[0] for w in cw[i2:i2 + 4]),
            "unverified": folio in UNVERIFIED,
        })

    total = len(cf)
    agree = 100 * equal_words / max(total, 1)
    by_kind = {k: sum(1 for v in variants if v["kind"] == k) for k in KIND.values()}
    print(f"shoda slov (folded): {equal_words}/{total} = {agree:.1f} %")
    print("varianty:", ", ".join(f"{k}={n}" for k, n in by_kind.items()),
          f"| celkem {len(variants)}")

    # structural (big) blocks = the headline differences
    big = sorted((v for v in variants if max(v["n_copy"], v["n_teige"]) >= 6),
                 key=lambda v: -max(v["n_copy"], v["n_teige"]))
    print(f"\nVětší strukturní rozdíly (≥6 slov): {len(big)}")
    for v in big[:12]:
        tag = " [f31–42 NEOVĚŘENO]" if v["unverified"] else ""
        print(f"  f{v['folio']} ř{v['line']} {v['kind']} "
              f"(opis {v['n_copy']}/Teige {v['n_teige']}){tag}: "
              f"…{v['ctx_before'][-30:]} » OPIS: {v['copy'][:60]} | TEIGE: {v['teige'][:60]}")

    # outputs
    json.dump({"summary": {"copy_words": len(cw), "teige_words": len(tw),
                           "agreement_pct": round(agree, 1), "by_kind": by_kind,
                           "total_variants": len(variants)},
               "variants": variants},
              open("work/orloj1587/collation_teige.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    with open("work/orloj1587/collation_teige.md", "w", encoding="utf-8") as fh:
        fh.write("# Kolace: Carchesiův opis 1587 (f5–49) × Teige 1570\n\n")
        fh.write(f"Shoda slov (po folded normalizaci): **{agree:.1f} %** "
                 f"({equal_words}/{total}). Varianty: "
                 + ", ".join(f"{k} {n}" for k, n in by_kind.items())
                 + f", celkem **{len(variants)}**.\n\n")
        fh.write("> Srovnání je na *folded* tvarech → pravopisné/diakritické rozdíly se "
                 "ignorují; hlásí se jen věcné varianty. Teige edituje **originál 1570**, "
                 "opis je jiný svědek s vlastní pozdější vrstvou. **f31–42 nejsou diplomaticky "
                 "ověřeny** → tam část variant = přepisový šum.\n\n")
        cur = None
        for v in variants:
            if v["folio"] != cur:
                cur = v["folio"]
                warn = " — ⚠ neověřeno (přepisový šum možný)" if cur in UNVERIFIED else ""
                fh.write(f"\n## fol. {cur}{warn}\n\n")
            fh.write(f"- **ř.{v['line']} · {v['kind']}** "
                     f"(opis {v['n_copy']} / Teige {v['n_teige']} sl.): "
                     f"opis „{v['copy'] or '—'}" + "“ × Teige „"
                     + f"{v['teige'] or '—'}“  "
                     + (f"_(…{v['ctx_before'][-24:]} | {v['ctx_after'][:24]}…)_"
                        if v['ctx_before'] or v['ctx_after'] else "") + "\n")
    print("\nuloženo: work/orloj1587/collation_teige.json + .md")


if __name__ == "__main__":
    main()
