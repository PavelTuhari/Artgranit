#!/usr/bin/env python3
"""Instalatorul DDL al modulului CRM (conturul CRM_*).

RO: instalator PROPRIU, conform regulii nr. 1 — instalatorul comun
`deploy_oracle_objects.py` nu se atinge. Idempotent: obiectele existente se
sar cu mesaj, nu cu eroare. Blocurile PL/SQL sint delimitate cu '/' pe rind
separat, INAINTE si DUPA (lectia SDA din 25.08.2026).

Rulare (din radacina proiectului, pe orice contur cu .env valid):
    python3 modules/crm/scripts/crm_deploy.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from models.biro26_db import Biro26DB  # noqa: E402

SQL_DIR = os.path.join(ROOT, "modules", "crm", "sql")
# RO: ORA-02303 = tipul obiect are dependenti (tabela de tip / pachetul) si nu
#     se poate inlocui; la reinstalare tipurile sint neschimbate -> SKIP.
#     Daca un tip chiar se schimba: DROP PACKAGE EFA_REPORT, DROP TYPE ..._TAB,
#     DROP TYPE ..._T, apoi instalatorul din nou.
EXISTS_OK = ("ORA-00955", "ORA-01543", "ORA-02260", "ORA-00001", "ORA-01408",
             "ORA-02303")


def run_file(db, path):
    text = open(path, encoding="utf-8").read()
    # RO: impartim DOAR pe '/' aflat singur pe rind / EN: split on lone '/'
    stmts, buf = [], []
    for line in text.splitlines():
        if line.strip() == "/":
            stmt = "\n".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
        else:
            buf.append(line)
    tail = "\n".join(buf).strip()
    if tail:
        stmts.append(tail)
    ok = skip = fail = 0
    for stmt in stmts:
        head = " ".join(stmt.split()[:6])
        r = db.execute_dml(stmt)
        if r.get("success"):
            ok += 1
            print(f"  OK    {head}")
        elif any(code in str(r.get("message", "")) for code in EXISTS_OK):
            skip += 1
            print(f"  SKIP  {head}  (există deja)")
        else:
            fail += 1
            print(f"  FAIL  {head}\n        {str(r.get('message'))[:200]}")
    return ok, skip, fail


def main():
    db = Biro26DB()
    total_fail = 0
    for fn in sorted(os.listdir(SQL_DIR)):
        if not fn.endswith(".sql"):
            continue
        print(f"== {fn} ==")
        _, _, fail = run_file(db, os.path.join(SQL_DIR, fn))
        total_fail += fail
    r = db.execute_query(
        "SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM USER_OBJECTS "
        "WHERE OBJECT_NAME LIKE 'CRM^_%' ESCAPE '^' ORDER BY OBJECT_TYPE, OBJECT_NAME")
    print("== obiecte CRM_* in USER_OBJECTS ==")
    for row in (r.get("data") or []):
        print("  ", row)
    sys.exit(1 if total_fail else 0)


if __name__ == "__main__":
    main()
