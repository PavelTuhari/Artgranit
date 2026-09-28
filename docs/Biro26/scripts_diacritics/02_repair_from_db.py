#!/usr/bin/env python3
# RO: Valul 2 - repara '?' ramase folosind textele CURATE din BD insasi (cross-table)
#     + fisierele sursa. Potrivire prin masca ('?' = orice caracter), doar cind e UNICA.
# EN: Wave 2 - repair remaining '?' using CLEAN text already in the DB (cross-table)
#     plus source files. Mask matching, only when unambiguous.
import sys, re, json, oracledb
from collections import defaultdict

GO = '--go' in sys.argv
oracledb.init_oracle_client(lib_dir='/Users/pt/Downloads/instantclient_23_26')
con = oracledb.connect(user='officeplus', password='officeplus26', dsn='orange.una.md:4024/cloudbd.world')
cur = con.cursor()
cur.arraysize = 5000

# ---- 1) candidati curati din BD / clean candidates from the DB itself ----
CLEAN = set()
for sql in [
    "SELECT DISTINCT denumirea FROM tms_univers WHERE denumirea IS NOT NULL AND denumirea NOT LIKE '%?%'",
    "SELECT DISTINCT denumire  FROM biro26_goods WHERE denumire  IS NOT NULL AND denumire  NOT LIKE '%?%'",
    "SELECT DISTINCT categorie FROM biro26_goods WHERE categorie IS NOT NULL AND categorie NOT LIKE '%?%'",
    "SELECT DISTINCT grupa     FROM biro26_goods WHERE grupa     IS NOT NULL AND grupa     NOT LIKE '%?%'",
    "SELECT DISTINCT denumire  FROM biro26pt_stg WHERE denumire  IS NOT NULL AND denumire  NOT LIKE '%?%'",
    "SELECT DISTINCT categ     FROM biro26pt_stg WHERE categ     IS NOT NULL AND categ     NOT LIKE '%?%'",
]:
    cur.execute(sql)
    for (v,) in cur:
        if v and len(v.strip()) >= 5:
            CLEAN.add(v.strip())
print(f"clean candidates from DB: {len(CLEAN)}", file=sys.stderr)

by_pref = defaultdict(list)
for s in CLEAN:
    by_pref[s[:4]].append(s)

def match(v):
    s = v.strip()
    if '?' not in s: return None
    n = len(s); pref = s[:4]
    if '?' in pref:
        head = s.split('?')[0]
        if len(head) < 3: return None
        cands = [x for k, lst in by_pref.items() if k.startswith(head) or head.startswith(k) for x in lst]
    else:
        cands = by_pref.get(pref, [])
    if not cands: return None
    rx = re.compile('^' + ''.join('.' if c == '?' else re.escape(c) for c in s))
    hits = {x[:n] for x in cands if len(x) >= n and rx.match(x)}
    if len(hits) == 1:
        h = hits.pop()
        if '?' not in h and h != s:
            return v.replace(s, h) if s != v else h
    return None

TARGETS = [('TMS_UNIVERS','DENUMIREA'), ('BIRO26_GOODS','DENUMIRE'), ('BIRO26_GOODS','CATEGORIE'),
           ('BIRO26_GOODS','GRUPA'), ('TMS_SYSGRPH','COMENT'), ('TMS_MPT_BARCODE','COMENT'),
           ('BIRO26PT_STG','DENUMIRE'), ('BIRO26PT_STG','CATEG'), ('BIRO26PT_STG','GRUPA')]
LOG = []
print(f"\n{'TABLE.COLUMN':30} {'distinct?':>10} {'reparate':>9} {'rinduri':>9}")
print('-'*62)
for tbl, col in TARGETS:
    cur.execute(f"SELECT {col}, COUNT(*) FROM {tbl} WHERE {col} LIKE '%?%' GROUP BY {col}")
    rows = cur.fetchall()
    mp, nr = [], 0
    for val, cnt in rows:
        r = match(val)
        if r and r != val:
            mp.append((r, val)); nr += cnt
    print(f"{tbl+'.'+col:30} {len(rows):>10} {len(mp):>9} {nr:>9}")
    LOG.extend([{'t':tbl,'c':col,'old':o,'new':n} for n,o in mp])
    if GO and mp:
        cur.executemany(f"UPDATE {tbl} SET {col} = :1 WHERE {col} = :2", mp)
        con.commit()
print('-'*62)
if GO:
    print("\n=== ramase cu '?' / remaining ===")
    for tbl, col in TARGETS:
        cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {col} LIKE '%?%'")
        print(f"  {tbl}.{col}: {cur.fetchone()[0]}")
    json.dump(LOG, open('/private/tmp/claude-501/-Users-pt-Projects-AI-BIRO26/fc666e55-371e-4d3a-986d-ddffe457696f/scratchpad/replacements_w2.json','w'), ensure_ascii=False)
    print(f"log: {len(LOG)} replacements")
else:
    print("\nDRY-RUN — ruleaza cu --go.")
con.close()
