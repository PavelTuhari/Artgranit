#!/usr/bin/env python3
"""Deploy Biro26 web-shop objects: YBIRO_CLIENT table + package y_ai_BIRO26.

Idempotent for the table (skips if YBIRO_CLIENT exists); the package is
always CREATE OR REPLACE'd from sql/biro26/04_y_ai_biro26.sql content.

Usage: ./venv/bin/python deploy_biro26_shop.py
"""
from __future__ import annotations
import re
import sys
from models.biro26_db import Biro26DB

SQL_FILE = "sql/biro26/04_y_ai_biro26.sql"


def split_statements(text: str):
    """Split the DDL file: '/' on its own line ends a PL/SQL unit; plain
    DDL statements end with ';' at line end."""
    units = []
    buf: list[str] = []
    plsql = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") and not buf:
            continue
        if re.match(r"(?i)^\s*(CREATE\s+OR\s+REPLACE\s+(PACKAGE|TRIGGER|FUNCTION|PROCEDURE))", line):
            plsql = True
        if stripped == "/" :
            if buf:
                units.append(("plsql", "\n".join(buf).strip()))
            buf = []
            plsql = False
            continue
        buf.append(line)
        if not plsql and stripped.endswith(";"):
            unit = "\n".join(buf).strip().rstrip(";")
            if unit:
                units.append(("ddl", unit))
            buf = []
    if buf and "".join(buf).strip():
        units.append(("ddl", "\n".join(buf).strip().rstrip(";")))
    return units


def main() -> int:
    db = Biro26DB()
    text = open(SQL_FILE, encoding="utf-8").read()

    table_exists = False
    ex = db.execute_query(
        "SELECT COUNT(*) FROM all_objects WHERE object_name='YBIRO_CLIENT'")
    if ex["success"] and ex["data"] and ex["data"][0][0] > 0:
        table_exists = True
        print("YBIRO_CLIENT already exists — skipping table/sequence/trigger.")

    for kind, unit in split_statements(text):
        head = " ".join(unit.split()[:6]).upper()
        if table_exists and ("YBIRO_CLIENT" in head and "PACKAGE" not in head):
            continue
        if kind == "plsql":
            r = db.call_proc(unit) if unit.upper().startswith("BEGIN") else db.execute_dml(unit)
        else:
            r = db.execute_dml(unit)
        ok = r.get("success")
        print(f"  [{'OK ' if ok else 'ERR'}] {head[:60]}" + ("" if ok else f" -> {r.get('message')}"))
        if not ok:
            return 1

    # package must be VALID
    st = db.execute_query(
        "SELECT object_type, status FROM all_objects "
        "WHERE object_name='Y_AI_BIRO26' AND owner='OFFICEPLUS'")
    print("y_ai_BIRO26 status:", st["data"])
    if any(row[1] != "VALID" for row in (st["data"] or [])):
        err = db.execute_query(
            "SELECT line, text FROM all_errors WHERE name='Y_AI_BIRO26' ORDER BY sequence")
        for row in (err["data"] or [])[:15]:
            print("   err:", row)
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
