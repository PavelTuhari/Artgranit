#!/usr/bin/env python3
"""SEOForge — установка контура YSEO_* в боевую ERP OfficePlus/UNA.

Зачем отдельный установщик. `deploy_oracle_objects.py` умеет ходить только
в облачную базу бэкофиса: thin-режим, wallet, `models/database.py`. ERP
OfficePlus — Oracle 11g на `orange.una.md`, туда ходят исключительно через
thick-режим в отдельном процессе (`models/biro26_db.py`), иначе падает
основное приложение. Поэтому разбор SQL-файлов переиспользуется из
`deploy_oracle_objects.py`, а выполнение идёт через воркер.

Отличие от облачного установщика: здесь после каждого файла проверяется
`USER_ERRORS`. `CREATE PACKAGE` с ошибкой компиляции не бросает исключение —
объект просто остаётся невалидным, и без этой проверки установка выглядела
бы успешной.

    venv/bin/python scripts/seoforge_deploy_erp.py --dry-run
    venv/bin/python scripts/seoforge_deploy_erp.py --yes
"""
from __future__ import annotations

import argparse
import os
import re
import sys

# Скрипт лежит в modules/seoforge/scripts/, корень проекта — на три уровня выше.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Порядок зависимостей: таблицы -> пакеты -> вьюшки -> справочники.
# Вьюшки вызывают PK_SEO_UTIL.TO_MDL, поэтому пакеты идут раньше вьюшек.
FILES = (
    "113_yseo_tables.sql",
    "115_yseo_package.sql",
    "114_yseo_views.sql",
    "116_yseo_dict_seed.sql",
)

# Объект уже существует — это не ошибка при повторной установке.
_ALREADY_EXISTS = ("ORA-00955", "ORA-01430", "ORA-02260", "ORA-00001")


def _splitters():
    """Разбор SQL берём из облачного установщика, чтобы правило было одно."""
    src = open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8").read()
    body = src.split("def _sql_blocks")[1].split("def main()")[0]
    namespace = {"re": re}
    exec("def _sql_blocks" + body, namespace)  # noqa: S102
    return (namespace["_sql_blocks"], namespace["_is_plsql_block"],
            namespace["_split_ddl_dml"], namespace["_is_comment_only"])


def statements_of(path, split_blocks, is_plsql, split_ddl, is_comment):
    """Файл -> список (текст, это_plsql)."""
    text = open(path, encoding="utf-8").read()
    out = []
    for block in split_blocks(text):
        block = re.sub(r"\s*/\s*$", "", block.strip())
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


def head(sql: str) -> str:
    """Первая содержательная строка — для человекочитаемого отчёта."""
    for line in sql.splitlines():
        line = line.strip()
        if line and not line.startswith("--"):
            return line[:88]
    return sql[:88]


def check_errors(db, names) -> list:
    rows = db.execute_query(
        "SELECT NAME, TYPE, LINE, TEXT FROM USER_ERRORS "
        "WHERE NAME LIKE 'YSEO%' OR NAME LIKE 'VSEO%' OR NAME LIKE 'PK_SEO%' "
        "OR NAME LIKE 'TRG_YSEO%' ORDER BY NAME, SEQUENCE")
    return list(rows.get("data") or [])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Установка контура SEOForge в боевую ERP OfficePlus")
    parser.add_argument("--yes", action="store_true",
                        help="подтвердить запись в боевую базу")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать команды, ничего не выполняя")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        print("Это БОЕВАЯ база OfficePlus. Запускайте с --yes либо --dry-run.")
        sys.exit(2)

    split_blocks, is_plsql, split_ddl, is_comment = _splitters()

    plan = []
    for name in FILES:
        path = os.path.join(ROOT, "modules", "seoforge", "sql", name)
        if not os.path.isfile(path):
            print(f"Не найден: {name}")
            sys.exit(1)
        plan.append((name, statements_of(path, split_blocks, is_plsql,
                                         split_ddl, is_comment)))

    if args.dry_run:
        for name, statements in plan:
            kinds = sum(1 for _, pl in statements if pl)
            print(f"[dry-run] {name}: {len(statements)} команд "
                  f"(из них PL/SQL: {kinds})")
            for sql, _ in statements:
                print("    " + head(sql))
        return

    from models.biro26_db import Biro26DB

    db = Biro26DB()
    probe = db.test_connection()
    if not probe.get("success"):
        print(f"Нет связи с ERP: {probe.get('error')}")
        sys.exit(1)
    print(f"ERP: {probe.get('version')}")

    who = db.execute_query("SELECT USER FROM DUAL")
    print(f"Схема: {who['data'][0][0]}\n")

    created = skipped = failed = 0
    for name, statements in plan:
        print(f"Выполняю {name} ...")
        for sql, plsql in statements:
            if plsql:
                result = db.call_proc(sql)
            else:
                result = db.execute_dml(sql)

            if result.get("success"):
                created += 1
                continue

            message = result.get("message", "")
            if any(code in message for code in _ALREADY_EXISTS):
                skipped += 1
                continue
            failed += 1
            print(f"  ОШИБКА: {head(sql)}")
            print(f"          {message.splitlines()[0][:160]}")

    print(f"\nВыполнено: {created}, пропущено (уже есть): {skipped}, "
          f"ошибок: {failed}")

    # Пакет или вьюшка с ошибкой компиляции не бросает исключение —
    # ошибка видна только здесь.
    errors = check_errors(db, None)
    if errors:
        print("\nОбъекты с ошибками компиляции:")
        for row in errors:
            print(f"  {row[1]} {row[0]} строка {row[2]}: {str(row[3])[:120]}")

    invalid = db.execute_query(
        "SELECT OBJECT_TYPE, OBJECT_NAME FROM USER_OBJECTS "
        "WHERE STATUS <> 'VALID' AND (OBJECT_NAME LIKE 'YSEO%' "
        "OR OBJECT_NAME LIKE 'VSEO%' OR OBJECT_NAME LIKE 'PK_SEO%' "
        "OR OBJECT_NAME LIKE 'TRG_YSEO%')")
    bad = list(invalid.get("data") or [])
    if bad:
        print("\nНевалидные объекты:")
        for row in bad:
            print(f"  {row[0]} {row[1]}")

    summary = db.execute_query(
        "SELECT OBJECT_TYPE, COUNT(*) FROM USER_OBJECTS "
        "WHERE OBJECT_NAME LIKE 'YSEO%' OR OBJECT_NAME LIKE 'VSEO%' "
        "OR OBJECT_NAME LIKE 'PK_SEO%' OR OBJECT_NAME LIKE 'TRG_YSEO%' "
        "GROUP BY OBJECT_TYPE ORDER BY OBJECT_TYPE")
    print("\nОбъекты контура в ERP:")
    for row in summary.get("data") or []:
        print(f"  {row[0]}: {row[1]}")

    sys.exit(1 if (failed or errors or bad) else 0)


if __name__ == "__main__":
    main()
