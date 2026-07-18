#!/usr/bin/env python3
"""Deploy ServOuts26 Oracle objects into the UNITEST schema (Oracle 11g).

The target DB is 11g -> THICK mode only, so this script must NOT be imported
by the main (thin) app; it is a standalone CLI run on demand:

    venv/bin/python deploy_servouts26_oracle.py

Executes, in order:
    sql/60_servouts26_srvo.sql          (SRVO_* staging + mapping profiles)
    sql/61_servouts26_yservouts_bp.sql  (YServOuts_BP package spec + body)

Statements are separated by a line containing only "/". "already exists"
errors (ORA-00955) are reported and skipped so reruns are idempotent.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import oracledb  # noqa: E402
from config import Config  # noqa: E402

SQL_FILES = [
    "sql/60_servouts26_srvo.sql",
    "sql/61_servouts26_yservouts_bp.sql",
]


def split_statements(text: str):
    """Split a script into statements on lines that contain only '/'."""
    stmt, out = [], []
    for line in text.splitlines():
        if line.strip() == "/":
            s = "\n".join(stmt).strip()
            if s:
                out.append(s)
            stmt = []
        else:
            stmt.append(line)
    s = "\n".join(stmt).strip()
    if s:
        out.append(s)
    return out


def main() -> int:
    oracledb.init_oracle_client(lib_dir=Config.BIRO26_INSTANT_CLIENT)
    conn = oracledb.connect(
        user=Config.SERVOUTS26_DB_USER,
        password=Config.SERVOUTS26_DB_PASSWORD,
        dsn=Config.SERVOUTS26_DB_DSN,
    )
    cur = conn.cursor()
    print(f"Connected as {Config.SERVOUTS26_DB_USER}@{Config.SERVOUTS26_DB_DSN}")
    failed = 0
    for path in SQL_FILES:
        full = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        with open(full, encoding="utf-8") as f:
            statements = split_statements(f.read())
        print(f"\n== {path}: {len(statements)} statement(s)")
        for s in statements:
            head = " ".join(s.split()[:6])
            try:
                cur.execute(s)
                print(f"  OK   {head}")
            except oracledb.DatabaseError as e:
                msg = str(e)
                if "ORA-00955" in msg:
                    print(f"  SKIP {head} (already exists)")
                else:
                    failed += 1
                    print(f"  FAIL {head}\n       {msg.splitlines()[0]}")
    # compile check for the package
    cur.execute("""SELECT object_name, object_type, status FROM user_objects
                    WHERE object_name = 'YSERVOUTS_BP' ORDER BY object_type""")
    rows = cur.fetchall()
    print("\n== YSERVOUTS_BP status:", rows or "NOT FOUND")
    bad = [r for r in rows if r[2] != "VALID"]
    if bad:
        cur.execute("""SELECT type, line, text FROM user_errors
                        WHERE name = 'YSERVOUTS_BP' ORDER BY type, sequence""")
        for t, ln, tx in cur.fetchall():
            print(f"  {t} line {ln}: {tx.strip()}")
        failed += 1
    conn.commit()
    conn.close()
    print("\nDeploy", "FAILED" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
