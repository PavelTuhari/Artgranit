#!/usr/bin/env python3
"""BIRO26_GOODS: un singur rind per COD_UNIVERS + index unic (01.09.2026).

RO: feed-ul de marfa avea ~3.800 de rinduri duplicate (3.632 de coduri) din
vechile importuri Excel. Catalogul le ocolea sortind TOATA tabela la fiecare
cerere (ROW_NUMBER peste 235k rinduri) — asta a incarcat baza.

Ce face scriptul, in ordinea asta, cu numaratori la fiecare pas:
  1. copiaza rindurile care vor fi sterse in BIRO26_GOODS_DUP_BAK (backup);
  2. sterge copiile, pastrind pentru fiecare cod rindul cu ID-ul cel mai mic
     — EXACT rindul pe care il arata site-ul si acum (acelasi criteriu ca in
     interogarea catalogului), deci nimic vizibil nu se schimba;
  3. inlocuieste indexul simplu IX_BIRO26_GOODS_CODUNIV cu unul UNIC;
  4. verifica: zero duplicate, indexul unic exista, numarul de rinduri bate.

Fara --go NU schimba nimic — doar arata ce ar face.
EN: dedupe BIRO26_GOODS by COD_UNIVERS, back up removed rows, add a unique
index. Dry-run by default; --go applies.

Rulare (de pe orice masina cu wallet-ul Oracle, o singura data — baza e
comuna ambelor contururi):
    venv/bin/python scripts/biro26_goods_dedupe.py            # dry-run
    venv/bin/python scripts/biro26_goods_dedupe.py --go
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAK = "BIRO26_GOODS_DUP_BAK"
OLD_IX = "IX_BIRO26_GOODS_CODUNIV"
NEW_IX = "UX_BIRO26_GOODS_CODUNIV"

# RO: criteriul de pastrare = cel din catalog: ORDER BY ID, NULL la urma
DUP_ROWIDS = ("SELECT rid FROM (SELECT ROWID rid, ROW_NUMBER() OVER "
              "(PARTITION BY COD_UNIVERS ORDER BY ID) rn FROM BIRO26_GOODS "
              "WHERE COD_UNIVERS IS NOT NULL) WHERE rn > 1")


def _load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    go = "--go" in sys.argv
    _load_env()
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    from models.biro26_db import Biro26DB
    from models.biro26_oracle_store import _rows
    db = Biro26DB()
    one = lambda sql: (_rows(db.execute_query(sql)) or [{}])[0]   # noqa: E731

    print(f"== {datetime.now():%d.%m.%Y %H:%M} BIRO26_GOODS dedupe "
          f"({'APLICARE' if go else 'DRY-RUN'})")
    before = one("SELECT COUNT(*) N, COUNT(DISTINCT COD_UNIVERS) CODURI "
                 "FROM BIRO26_GOODS")
    dups = one("SELECT COUNT(*) CODURI, NVL(SUM(N - 1), 0) RINDURI FROM ("
               "SELECT COD_UNIVERS, COUNT(*) N FROM BIRO26_GOODS "
               "WHERE COD_UNIVERS IS NOT NULL GROUP BY COD_UNIVERS "
               "HAVING COUNT(*) > 1)")
    ix = one(f"SELECT MAX(UNIQUENESS) U FROM USER_INDEXES WHERE INDEX_NAME "
             f"IN ('{OLD_IX}', '{NEW_IX}')")
    to_del = int(dups.get("rinduri") or 0)
    print(f"  rinduri total: {before.get('n')}, coduri distincte: "
          f"{before.get('coduri')}")
    print(f"  coduri cu duplicate: {dups.get('coduri')}, rinduri de sters: "
          f"{to_del}")
    print(f"  index pe COD_UNIVERS: {ix.get('u') or 'LIPSESTE'}")
    if to_del == 0 and (ix.get("u") == "UNIQUE"):
        print("  nimic de facut — deja curat si unic")
        return 0
    if not go:
        print("  (fara --go nu se schimba nimic)")
        return 0

    # 1. backup
    exists = one(f"SELECT COUNT(*) N FROM USER_TABLES WHERE TABLE_NAME='{BAK}'")
    if int(exists.get("n") or 0):
        r = db.execute_dml(f"INSERT INTO {BAK} SELECT g.*, SYSDATE FROM "
                           f"BIRO26_GOODS g WHERE ROWID IN ({DUP_ROWIDS})")
    else:
        r = db.execute_dml(f"CREATE TABLE {BAK} AS SELECT g.*, SYSDATE BAK_AT "
                           f"FROM BIRO26_GOODS g WHERE ROWID IN ({DUP_ROWIDS})")
    if not r.get("success"):
        print("  EROARE la backup:", str(r.get("message"))[:300])
        return 2
    saved = one(f"SELECT COUNT(*) N FROM {BAK}")
    print(f"  1. backup in {BAK}: {saved.get('n')} rinduri (cumulat)")

    # 2. stergerea
    r = db.execute_dml(f"DELETE FROM BIRO26_GOODS WHERE ROWID IN ({DUP_ROWIDS})")
    if not r.get("success"):
        print("  EROARE la stergere:", str(r.get("message"))[:300])
        return 2
    print(f"  2. sterse: {r.get('rowcount')} (asteptat {to_del})")

    # 3. indexul unic
    if ix.get("u") != "UNIQUE":
        has_old = one(f"SELECT COUNT(*) N FROM USER_INDEXES "
                      f"WHERE INDEX_NAME='{OLD_IX}'")
        if int(has_old.get("n") or 0):
            r = db.execute_dml(f"DROP INDEX {OLD_IX}")
            if not r.get("success"):
                print("  EROARE la DROP INDEX:", str(r.get("message"))[:300])
                return 2
        r = db.execute_dml(f"CREATE UNIQUE INDEX {NEW_IX} ON BIRO26_GOODS "
                           "(COD_UNIVERS)")
        if not r.get("success"):
            # RO: fara index catalogul ar suferi — punem inapoi macar simplul
            db.execute_dml(f"CREATE INDEX {OLD_IX} ON BIRO26_GOODS (COD_UNIVERS)")
            print("  EROARE la indexul unic (pus inapoi cel simplu):",
                  str(r.get("message"))[:300])
            return 2
        print(f"  3. index unic {NEW_IX} creat")

    # 4. verificare
    after = one("SELECT COUNT(*) N FROM BIRO26_GOODS")
    left = one("SELECT COUNT(*) N FROM (SELECT COD_UNIVERS FROM BIRO26_GOODS "
               "WHERE COD_UNIVERS IS NOT NULL GROUP BY COD_UNIVERS "
               "HAVING COUNT(*) > 1)")
    ix2 = one(f"SELECT UNIQUENESS U FROM USER_INDEXES WHERE INDEX_NAME='{NEW_IX}'")
    ok = (int(left.get("n") or 0) == 0 and ix2.get("u") == "UNIQUE"
          and int(after.get("n")) == int(before.get("n")) - to_del)
    print(f"  4. rinduri acum: {after.get('n')} (inainte {before.get('n')}), "
          f"duplicate ramase: {left.get('n')}, index: {ix2.get('u')}")
    print("  REZULTAT:", "OK" if ok else "VERIFICATI — ceva nu bate")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
