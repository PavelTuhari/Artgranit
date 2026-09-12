#!/usr/bin/env python3
"""Установщик DDL модуля netmon — СВОЙ, общий deploy_oracle_objects.py не трогаем.

    python modules/netmon/scripts/netmon_deploy.py            # установить
    python modules/netmon/scripts/netmon_deploy.py --dry-run  # только разбор

--dry-run не доказывает, что схема встанет (CLAUDE.md §2 п.5): прогнать вживую.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# Разбор SQL берём у общего установщика, чтобы не дублировать логику
from deploy_oracle_objects import _is_comment_only, _is_plsql_block, _split_ddl_dml, _sql_blocks  # noqa: E402

FILES = ["200_nmon_tables.sql", "201_nmon_pve.sql"]
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    stmts = []
    for name in FILES:
        text = (SQL_DIR / name).read_text(encoding="utf-8")
        for block in _sql_blocks(text):
            if _is_comment_only(block):
                continue
            stmts += [block] if _is_plsql_block(block) else [s for s in _split_ddl_dml(block) if not _is_comment_only(s)]
    print(f"команд к выполнению: {len(stmts)}")
    if args.dry_run:
        return

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from models.database import DatabaseConnection
    conn = DatabaseConnection.get_connection()
    cur = conn.cursor()
    ok = err = 0
    for s in stmts:
        try:
            cur.execute(s.rstrip().rstrip("/").rstrip())
            conn.commit()
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ошибка: {str(e)[:160]}")
            err += 1
    print(f"готово: успешно {ok}, ошибок {err}")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
