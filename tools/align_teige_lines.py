# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
"""Global per-line Teige alignment for the 1570 ORIGINAL (mode B).

Aligns the per-line HTR of the 1570 autograph to Teige's 1901 edition by a single
global word-level difflib match, projects the Teige span onto each HTR line, and flags
low-confidence / unmatched lines for diplomatic check. Output: work/orloj1570/teige_lines.json.
"""
import difflib
import glob
import json
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, "src")

from transcribus.processing.teige import fold  # noqa: E402

def htr_lines(px):
    x=open(px,encoding='utf-8').read(); ns={'p':re.search(r'xmlns="([^"]+)"',x).group(1)}
    r=ET.fromstring(x); return [ (tl.find('.//p:Unicode',ns).text or '') if tl.find('.//p:Unicode',ns) is not None else '' for tl in r.findall('.//p:TextLine',ns)]

W=re.compile(r'\S+')
if __name__=='__main__':
    teige=open('data/teige_taborsky.txt',encoding='utf-8').read()
    pw=W.findall(teige); pwf=[fold(w) for w in pw]
    pages=sorted(glob.glob('work/orloj1570/page_xml/*.xml'))
    # global HTR sequence with (page,line) tags
    T=[]; tag=[]; lines_by_pg={}
    for px in pages:
        pn=px.split('/')[-1][:-4]; lns=htr_lines(px); lines_by_pg[pn]=lns
        for li,ln in enumerate(lns):
            for w in W.findall(ln):
                f=fold(w)
                if f: T.append(f); tag.append((pn,li))
    sm=difflib.SequenceMatcher(None,T,pwf,autojunk=False)
    t2p={}
    for t_,i1,i2,j1,j2 in sm.get_opcodes():
        if t_ in('equal','replace'):
            for k in range(i2-i1):
                jj=j1+min(k,max(0,j2-j1-1))
                if jj<len(pw): t2p[i1+k]=jj
    # per (page,line): teige span
    from collections import defaultdict
    byline=defaultdict(list); nwline=defaultdict(int)
    for ti,(pn,li) in enumerate(tag):
        nwline[(pn,li)]+=1
        if ti in t2p: byline[(pn,li)].append(t2p[ti])
    allres={}; low=[]
    for pn,lns in lines_by_pg.items():
        res=[]
        for li,ln in enumerate(lns):
            idxs=byline.get((pn,li),[]); nw=nwline.get((pn,li),0)
            if idxs:
                lo,hi=min(idxs),max(idxs); tt=' '.join(pw[lo:hi+1]); conf=round(len(idxs)/max(nw,1),2)
            else: tt=''; conf=0.0
            res.append({'htr':ln,'teige':tt,'conf':conf,'nw':nw})
            if nw>=3 and (conf<0.4 or not tt.strip()): low.append((pn,li,ln,tt,conf))
        allres[pn]=res
    json.dump(allres,open('work/orloj1570/teige_lines.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print(f"disputed lines (nw>=3, conf<0.4 or empty): {len(low)}")
    print("=== sporné řádky (k dořešení skenem) ===")
    for pn,li,ln,tt,c in low[:25]:
        print(f"  {pn} ř{li:2} c={c}: '{ln[:46]}'")
