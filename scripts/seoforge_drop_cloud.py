#!/usr/bin/env python3
"""SEOForge — снятие контура YSEO_* с облачной БД бэкофиса.

Контур перенесён в боевую ERP OfficePlus (`scripts/seoforge_deploy_erp.py`),
и модуль читает только оттуда. Копия в облачной базе после переноса ничего
не обслуживает: она молча расходилась бы с боевой и путала бы того, кто
станет разбираться, где на самом деле лежат данные.

Скрипт удаляет объекты **безвозвратно**, поэтому требует `--yes`. Перед
удалением он показывает, сколько строк в таблицах: если там появились
данные, которых не должно быть, это видно до удаления, а не после.

    venv/bin/python scripts/seoforge_drop_cloud.py --dry-run
    venv/bin/python scripts/seoforge_drop_cloud.py --yes
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from models.database import DatabaseModel  # noqa: E402

# Порядок обратный установке: сначала зависимые, потом то, на что ссылаются.
VIEWS = ("VSEO_SITE", "VSEO_CAMPAIGN", "VSEO_BUDGET_PLANFACT", "VSEO_CHANNEL_ROI")
PACKAGES = ("PK_SEO_BUDGET", "PK_SEO_UTIL")
TABLES = ("YSEO_SPEND_FACT", "YSEO_METRICS_FACT", "YSEO_IMPORT",
          "YSEO_BUDGET_PLAN", "YSEO_CAMPAIGN", "YSEO_PLATFORM", "YSEO_SITE",
          "YSEO_XREF", "YSEO_EVENT_LOG", "YSEO_FX_RATE", "YSEO_SETUP",
          "YSEO_DICT")
SEQUENCES = ("YSEO_DICT_SEQ", "YSEO_SITE_SEQ", "YSEO_PLATFORM_SEQ",
             "YSEO_CAMPAIGN_SEQ", "YSEO_BUDGET_PLAN_SEQ",
             "YSEO_SPEND_FACT_SEQ", "YSEO_METRICS_FACT_SEQ",
             "YSEO_IMPORT_SEQ", "YSEO_XREF_SEQ", "YSEO_EVENT_LOG_SEQ")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Снятие контура SEOForge с облачной БД бэкофиса")
    parser.add_argument("--yes", action="store_true",
                        help="подтвердить безвозвратное удаление объектов")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать, что будет удалено")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        print("Удаление безвозвратно. Запускайте с --yes либо --dry-run.")
        sys.exit(2)

    with DatabaseModel() as db:
        print("Строк в таблицах контура (облачная БД):")
        total = 0
        for name in TABLES:
            result = db.execute_query(f"SELECT COUNT(*) FROM {name}")
            if not result.get("success"):
                print(f"  {name}: нет объекта")
                continue
            count = result["data"][0][0]
            total += count
            print(f"  {name}: {count}")
        print(f"  всего: {total}")

        if args.dry_run:
            print("\n[dry-run] Будет удалено: "
                  f"{len(VIEWS)} вьюшек, {len(PACKAGES)} пакетов, "
                  f"{len(TABLES)} таблиц, {len(SEQUENCES)} последовательностей.")
            return

        print()
        dropped = missing = failed = 0
        plan = ([(f"DROP VIEW {n}", n) for n in VIEWS]
                + [(f"DROP PACKAGE {n}", n) for n in PACKAGES]
                # CASCADE CONSTRAINTS: таблицы связаны внешними ключами.
                + [(f"DROP TABLE {n} CASCADE CONSTRAINTS PURGE", n) for n in TABLES]
                + [(f"DROP SEQUENCE {n}", n) for n in SEQUENCES])

        for sql, name in plan:
            result = db.execute_query(sql)
            if result.get("success"):
                dropped += 1
                continue
            message = result.get("message", "")
            # ORA-00942/-04043/-02289 - объекта уже нет, это не ошибка.
            if any(code in message for code in
                   ("ORA-00942", "ORA-04043", "ORA-02289")):
                missing += 1
                continue
            failed += 1
            print(f"  ОШИБКА {name}: {message.splitlines()[0][:140]}")

        db.connection.commit()
        print(f"Удалено: {dropped}, уже отсутствовало: {missing}, "
              f"ошибок: {failed}")

        left = db.execute_query(
            "SELECT OBJECT_TYPE, OBJECT_NAME FROM USER_OBJECTS "
            "WHERE OBJECT_NAME LIKE 'YSEO%' OR OBJECT_NAME LIKE 'VSEO%' "
            "OR OBJECT_NAME LIKE 'PK_SEO%' OR OBJECT_NAME LIKE 'TRG_YSEO%'")
        rest = list(left.get("data") or [])
        if rest:
            print("\nОсталось в облачной БД:")
            for row in rest:
                print(f"  {row[0]} {row[1]}")
        else:
            print("Контур в облачной БД не найден — перенос завершён.")

        sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
