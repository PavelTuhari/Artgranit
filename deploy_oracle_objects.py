#!/usr/bin/env python3
"""
Скрипт развёртывания объектов Oracle: таблицы, представления, триггеры, пакеты,
демо-данные для табло отправлений (bus), админки кредитов и интерфейса оператора (cred).

Использование:
  python deploy_oracle_objects.py              # развернуть объекты (без drop)
  python deploy_oracle_objects.py --drop       # удалить объекты, затем развернуть заново
  python deploy_oracle_objects.py --dry-run    # только показать, что будет выполнено

Переменные окружения (.env): DB_USER, DB_PASSWORD, WALLET_*, CONNECT_STRING — как в приложении.
"""
from __future__ import annotations

import os
import re
import sys
import argparse
from pathlib import Path

# корень проекта
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def _sql_blocks(content: str) -> list[str]:
    """Разбивает скрипт на блоки по разделителю / на отдельной строке (SQL*Plus style)."""
    normalized = content.replace("\r\n", "\n").strip()
    parts = re.split(r"\n\s*/\s*\n", normalized)
    return [p.strip() for p in parts if p.strip()]


def _is_plsql_block(block: str) -> bool:
    """Проверяет, что блок — PL/SQL (package, trigger, anonymous block)."""
    u = block.upper()
    if "CREATE OR REPLACE PACKAGE" in u:
        return True
    if "CREATE OR REPLACE TRIGGER" in u:
        return True
    if "CREATE OR REPLACE PROCEDURE" in u or "CREATE OR REPLACE FUNCTION" in u:
        return True
    if re.search(r"\bBEGIN\b", u) and re.search(r"\bEND\s*;", u):
        return True
    return False


def _split_ddl_dml(block: str) -> list[str]:
    """Разбивает DDL/DML блок на отдельные команды по ';'. Без обработки вложенных строк."""
    out = []
    cur = []
    i = 0
    in_sq = False
    qchar = None
    while i < len(block):
        c = block[i]
        if not in_sq and c in ("'", '"'):
            in_sq = True
            qchar = c
            cur.append(c)
            i += 1
            continue
        if in_sq:
            cur.append(c)
            if c == qchar and i + 1 < len(block) and block[i + 1] == qchar:
                cur.append(block[i + 1])
                i += 2
                continue
            if c == qchar:
                in_sq = False
            i += 1
            continue
        if c == ";":
            stmt = "".join(cur).strip()
            if stmt:
                out.append(stmt)
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    stmt = "".join(cur).strip()
    if stmt:
        out.append(stmt)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Развёртывание Oracle-объектов (bus, cred)")
    ap.add_argument("--drop", action="store_true", help="Сначала выполнить 00_drop.sql")
    ap.add_argument("--dry-run", action="store_true", help="Не выполнять, только вывести команды")
    ap.add_argument("--sql-dir", type=Path, default=ROOT / "sql", help="Каталог с SQL-файлами")
    args = ap.parse_args()

    sql_dir = args.sql_dir
    if not sql_dir.is_dir():
        print(f"Ошибка: каталог {sql_dir} не найден.")
        sys.exit(1)

    # порядок файлов
    order = [
        "00_drop.sql",
        "01_bus_tables.sql",
        "02_bus_views.sql",
        "03_bus_triggers.sql",
        "04_bus_package.sql",
        "05_cred_tables.sql",
        "06_cred_views.sql",
        "07_cred_triggers.sql",
        "08_cred_admin_package.sql",
        "09_cred_operator_package.sql",
        "11_cred_program_products.sql",
        "10_demo_data.sql",
        "12_cred_reports.sql",
        "13_shell_projects.sql",
        "14_nufarul_tables.sql",
        "15_nufarul_views.sql",
    ]
    if not args.drop:
        order = [f for f in order if f != "00_drop.sql"]

    files = []
    for name in order:
        p = sql_dir / name
        if not p.is_file():
            print(f"Пропуск (не найден): {name}")
            continue
        files.append((name, p))

    if args.dry_run:
        for name, p in files:
            print(f"[dry-run] {name}")
            blocks = _sql_blocks(p.read_text(encoding="utf-8", errors="replace"))
            for i, b in enumerate(blocks):
                pl = "PL/SQL" if _is_plsql_block(b) else "DDL/DML"
                n = 1 if _is_plsql_block(b) else len(_split_ddl_dml(b))
                print(f"  block {i+1} ({pl}): {n} statement(s)")
        return

    try:
        from models.database import DatabaseConnection
    except Exception as e:
        print(f"Ошибка импорта: {e}")
        sys.exit(1)

    conn = None
    try:
        conn = DatabaseConnection.get_connection()
    except Exception as e:
        print(f"Ошибка подключения к Oracle: {e}")
        sys.exit(1)

    ok = 0
    err = 0
    cursor = conn.cursor()

    def run_one(stmt: str) -> bool:
        nonlocal ok, err
        try:
            cursor.execute(stmt)
            conn.commit()
            ok += 1
            return True
        except Exception as e:
            print(f"  Ошибка: {e}")
            err += 1
            return False

    for name, path in files:
        print(f"Выполняю {name} ...")
        text = path.read_text(encoding="utf-8", errors="replace")
        blocks = _sql_blocks(text)

        for bi, block in enumerate(blocks):
            block = re.sub(r"\s*/\s*$", "", block.strip())
            if not block:
                continue
            if _is_plsql_block(block):
                run_one(block)
            else:
                for stmt in _split_ddl_dml(block):
                    stmt = stmt.strip()
                    if not stmt:
                        continue
                    run_one(stmt)

    if cursor:
        try:
            cursor.close()
        except Exception:
            pass
    if conn:
        try:
            conn.close()
        except Exception:
            pass

    print(f"Готово. Успешно: {ok}, ошибок: {err}.")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
