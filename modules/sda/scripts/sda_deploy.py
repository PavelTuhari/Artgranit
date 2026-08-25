#!/usr/bin/env python3
"""SDA — установка контура SDA_* в облачную ADB портала.

В отличие от SEOForge (боевая ERP OfficePlus 11g через thick-воркер),
таблицы SDA живут в той же облачной базе, что и остальной бэкофис портала:
thin-режим, wallet, `models/database.py` — тот же транспорт, что использует
`deploy_oracle_objects.py`. Поэтому разбор SQL-файлов не копируется, а
импортируется напрямую оттуда: это чистый импорт функций уровня модуля,
без побочных эффектов на момент импорта (`main()` спрятан за
`if __name__ == "__main__"`).

    venv/bin/python modules/sda/scripts/sda_deploy.py --dry-run
    venv/bin/python modules/sda/scripts/sda_deploy.py --yes
"""
from __future__ import annotations

import argparse
import os
import sys

# Скрипт лежит в modules/sda/scripts/, корень проекта — на три уровня выше.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FILES = (
    "117_sda_tables.sql",
)


def head(sql: str) -> str:
    """Первая содержательная строка — для человекочитаемого отчёта."""
    for line in sql.splitlines():
        line = line.strip()
        if line and not line.startswith("--"):
            return line[:88]
    return sql[:88]


def statements_of(path, sql_blocks, is_plsql, split_ddl, is_comment):
    """Файл -> список (текст, это_plsql), той же разбивкой, что и облачный установщик."""
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
        description="Установка контура SDA в облачную ADB портала")
    parser.add_argument("--yes", action="store_true",
                        help="подтвердить запись в базу")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать команды, ничего не выполняя")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        print("Запускайте с --yes либо --dry-run.")
        sys.exit(2)

    # Импорт функций разбора SQL из общего установщика (тот же формат
    # файлов, тот же транспорт — переиспользование, а не дублирование
    # правила).
    import deploy_oracle_objects as shared
    sql_blocks = shared._sql_blocks
    is_plsql = shared._is_plsql_block
    split_ddl = shared._split_ddl_dml
    is_comment = shared._is_comment_only

    plan = []
    for name in FILES:
        path = os.path.join(ROOT, "modules", "sda", "sql", name)
        if not os.path.isfile(path):
            print(f"Не найден: {name}")
            sys.exit(1)
        plan.append((name, statements_of(path, sql_blocks, is_plsql,
                                         split_ddl, is_comment)))

    if args.dry_run:
        for name, statements in plan:
            kinds = sum(1 for _, pl in statements if pl)
            print(f"[dry-run] {name}: {len(statements)} команд "
                  f"(из них PL/SQL: {kinds})")
            for sql, _ in statements:
                print("    " + head(sql))
        return

    from models.database import DatabaseConnection

    try:
        conn = DatabaseConnection.get_connection()
    except Exception as exc:                                     # noqa: BLE001
        print(f"Ошибка подключения к Oracle: {exc}")
        sys.exit(1)

    cursor = conn.cursor()
    created = failed = 0
    try:
        for name, statements in plan:
            print(f"Выполняю {name} ...")
            for sql, _plsql in statements:
                try:
                    cursor.execute(sql)
                    conn.commit()
                    created += 1
                except Exception as exc:                          # noqa: BLE001
                    message = str(exc)
                    if any(code in message for code in
                           ("ORA-00955", "ORA-01430", "ORA-02260", "ORA-00001")):
                        # Объект уже существует — не ошибка при повторной установке.
                        continue
                    failed += 1
                    print(f"  ОШИБКА: {head(sql)}")
                    print(f"          {message.splitlines()[0][:160]}")
    finally:
        cursor.close()
        conn.close()

    print(f"\nВыполнено: {created}, ошибок: {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
