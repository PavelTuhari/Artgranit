#!/usr/bin/env python3
"""Autopark -- installs the FLT_* schema into the platform's cloud ADB.

Same transport as SDA (modules/sda/scripts/sda_deploy.py): thin-mode
Oracle over models/database.py, wallet-based auth, same cloud ADB as the
rest of the backoffice portal -- not the OfficePlus 11g thick-worker
contour used by biro26/servouts26. SQL parsing is imported rather than
duplicated from the shared installer (deploy_oracle_objects.py): a pure
function-level import with no side effects at import time (`main()` is
guarded by `if __name__ == "__main__"`).

    venv/bin/python modules/autopark/scripts/autopark_deploy.py --dry-run
    venv/bin/python modules/autopark/scripts/autopark_deploy.py --only 120
    venv/bin/python modules/autopark/scripts/autopark_deploy.py --yes
"""
from __future__ import annotations

import argparse
import os
import sys

# Script lives in modules/autopark/scripts/, project root is three levels up.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FILES = (
    "120_flt_tables.sql",
    "121_flt_views.sql",
    "122_flt_seed.sql",
)


def head(sql: str) -> str:
    """First non-comment line -- for a human-readable report."""
    for line in sql.splitlines():
        line = line.strip()
        if line and not line.startswith("--"):
            return line[:88]
    return sql[:88]


def statements_of(path, sql_blocks, is_plsql, split_ddl, is_comment):
    """File -> list of (text, is_plsql), split the same way as the cloud installer."""
    text = open(path, encoding="utf-8").read()
    out = []
    for block in sql_blocks(text):
        if not block or is_comment(block):
            continue
        if is_plsql(block):
            out.append((block, True))
        else:
            for stmt in split_ddl(block):
                stmt = stmt.strip()
                if stmt and not is_comment(stmt):
                    out.append((stmt, False))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install the Autopark (FLT_*) schema into the cloud ADB")
    parser.add_argument("--yes", action="store_true",
                        help="confirm writing to the database")
    parser.add_argument("--dry-run", action="store_true",
                        help="show the planned commands without executing them")
    parser.add_argument("--only", metavar="NNN",
                        help="run only the file whose name starts with this "
                             "number (e.g. 120, 121, 122)")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        print("Run with --yes or --dry-run.")
        sys.exit(2)

    # Import the SQL-parsing helpers from the shared installer (same file
    # format, same transport -- reuse, not duplication of the splitting rule).
    import deploy_oracle_objects as shared
    sql_blocks = shared._sql_blocks
    is_plsql = shared._is_plsql_block
    split_ddl = shared._split_ddl_dml
    is_comment = shared._is_comment_only

    files = FILES
    if args.only:
        files = tuple(name for name in FILES if name.startswith(args.only))
        if not files:
            print(f"No file matches --only {args.only}")
            sys.exit(1)

    plan = []
    for name in files:
        path = os.path.join(ROOT, "modules", "autopark", "sql", name)
        if not os.path.isfile(path):
            print(f"Not found: {name}")
            sys.exit(1)
        plan.append((name, statements_of(path, sql_blocks, is_plsql,
                                         split_ddl, is_comment)))

    if args.dry_run:
        for name, statements in plan:
            kinds = sum(1 for _, pl in statements if pl)
            print(f"[dry-run] {name}: {len(statements)} statements "
                  f"(of which PL/SQL: {kinds})")
            for sql, _ in statements:
                print("    " + head(sql))
        return

    from models.database import DatabaseConnection

    try:
        conn = DatabaseConnection.get_connection()
    except Exception as exc:                                     # noqa: BLE001
        print(f"Oracle connection error: {exc}")
        sys.exit(1)

    cursor = conn.cursor()
    created = failed = 0
    try:
        for name, statements in plan:
            print(f"Running {name} ...")
            for sql, _plsql in statements:
                try:
                    cursor.execute(sql)
                    conn.commit()
                    created += 1
                except Exception as exc:                          # noqa: BLE001
                    message = str(exc)
                    if any(code in message for code in
                           ("ORA-00955", "ORA-01430", "ORA-02260", "ORA-00001")):
                        # Object already exists -- not an error on a repeat install.
                        continue
                    failed += 1
                    print(f"  ERROR: {head(sql)}")
                    print(f"         {message.splitlines()[0][:160]}")
    finally:
        cursor.close()
        conn.close()

    print(f"\nExecuted: {created}, errors: {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
