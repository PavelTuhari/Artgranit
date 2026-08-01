#!/usr/bin/env python3
"""Deploy TMDB_CREDITE_M/D + VMDB_CREDITE_M/D + y_ai_BIRO26_credite (Oracle 11g).

Idempotent: existing objects are skipped (ORA-00955), views and the package are
always recreated (CREATE OR REPLACE).

Usage: ./venv/bin/python deploy_credite_docs.py
"""
from __future__ import annotations

import re
import sys

from models.biro26_db import Biro26DB

FILES = ["sql/biro26/13_tmdb_credite.sql", "sql/biro26/14_y_ai_biro26_credite.sql"]
OBJECTS = ["TMDB_CREDITE_M", "TMDB_CREDITE_D", "VMDB_CREDITE_M", "VMDB_CREDITE_D",
           "Y_AI_BIRO26_CREDITE"]


def split_sql(text: str) -> list[str]:
    """Разбивает файл на операторы: PL/SQL-блоки завершает одинокий '/'."""
    out, buf, plsql = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("--") and not buf:
            continue
        if s == "/":
            if buf:
                out.append("\n".join(buf).strip())
                buf, plsql = [], False
            continue
        if re.match(r"^CREATE\s+OR\s+REPLACE\s+(PACKAGE|TRIGGER|PROCEDURE|FUNCTION)",
                    s, re.I):
            plsql = True
        buf.append(line)
        if not plsql and s.endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            buf = []
    if buf and "\n".join(buf).strip():
        out.append("\n".join(buf).strip().rstrip(";").strip())
    return [s for s in out if s]


def main() -> int:
    db = Biro26DB()
    for path in FILES:
        print(f"\n=== {path} ===")
        with open(path, encoding="utf-8") as f:
            for stmt in split_sql(f.read()):
                head = " ".join(stmt.split()[:4]).upper()
                r = db.execute_dml(stmt)
                msg = r.get("message") or ""
                if r.get("success"):
                    print(f"  + {head}")
                elif "ORA-00955" in msg or "ORA-01408" in msg:
                    print(f"  = {head} (уже есть)")
                else:
                    print(f"  ! {head}: {msg[:180]}")
                    return 1

    print("\n=== проверка ===")
    bad = []
    for name in OBJECTS:
        r = db.execute_query(
            "SELECT OBJECT_TYPE, STATUS FROM USER_OBJECTS WHERE OBJECT_NAME = :n",
            {"n": name})
        rows = r.get("data") or []
        if not rows:
            print(f"  ✗ {name}: НЕТ"); bad.append(name); continue
        for t, st in rows:
            flag = "✓" if st == "VALID" else "✗"
            print(f"  {flag} {name} ({t}) — {st}")
            if st != "VALID":
                bad.append(name)
    if bad:
        print("\nПРОБЛЕМЫ:", ", ".join(sorted(set(bad))))
        return 1
    print("\nOK: все объекты на месте и VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
