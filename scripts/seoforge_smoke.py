#!/usr/bin/env python3
"""SEOForge — живой smoke контура YSEO_* после установки DDL.

Юнит-тесты гоняются на моках и не могут проверить то, ради чего контур
и делался: срабатывает ли лимит бюджета, не плодит ли повторный импорт
дубли, действительно ли архивирование заменяет удаление. Эти правила
живут в пакетах и триггерах Oracle, поэтому нужен прогон по настоящей
базе.

Скрипт пишет в базу, поэтому требует явного `--yes`:

    venv/bin/python scripts/seoforge_smoke.py --yes

Работа идёт на служебном сайте `smoke.invalid` — домен из зарезервированной
зоны, он не может совпасть с настоящим. В конце сайт архивируется, а факты
и план по нему остаются: удалений в контуре нет по замыслу, и smoke не
делает исключения для себя. Повторные запуски идемпотентны: сайт и его
строки переиспользуются по стабильному EXT_ID.
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

SITE_DOMAIN = "smoke.invalid"
PERIOD = "2099-01"
SPEND_DATE = "2099-01-15"
ARTICLE_CODE = "ADS"
CHANNEL_CODE = "GOOGLE_ADS"

PASSED: list = []
FAILED: list = []


def report(name: str, ok: bool, detail: str = "") -> bool:
    (PASSED if ok else FAILED).append(name)
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}] {name}{(' — ' + detail) if detail else ''}")
    return ok


def query(db, sql, params=None):
    result = db.execute_query(sql, params or {})
    if not result.get("success"):
        raise RuntimeError(result.get("message", "unknown error"))
    columns = [c.lower() for c in (result.get("columns") or [])]
    return [dict(zip(columns, row)) for row in (result.get("data") or [])]


def scalar(db, sql, params=None):
    rows = query(db, sql, params)
    return list(rows[0].values())[0] if rows else None


def run(db, sql, params=None):
    """Выполняет команду и возвращает (успех, сообщение) вместо исключения."""
    result = db.execute_query(sql, params or {})
    return bool(result.get("success")), result.get("message", "")


# ── подготовка ───────────────────────────────────────────────────────

def prepare(db) -> dict:
    """Служебный сайт, чистый период и известный режим перерасхода."""
    cod = scalar(db, "SELECT COD FROM YSEO_SITE WHERE DOMAIN = :d",
                 {"d": SITE_DOMAIN})
    if cod is None:
        run(db, "INSERT INTO YSEO_SITE (DOMAIN, LOCALES, GEO, NICHE) "
                "VALUES (:d, 'ru', 'MD', 'smoke')", {"d": SITE_DOMAIN})
        db.connection.commit()
        cod = scalar(db, "SELECT COD FROM YSEO_SITE WHERE DOMAIN = :d",
                     {"d": SITE_DOMAIN})

    # Прошлый прогон мог оставить факты: они мешают считать лимит заново.
    run(db, "DELETE FROM YSEO_SPEND_FACT WHERE SITE_COD = :cod", {"cod": cod})
    run(db, "DELETE FROM YSEO_BUDGET_PLAN WHERE SITE_COD = :cod", {"cod": cod})
    run(db, "UPDATE YSEO_SITE SET ISARHIV = 0 WHERE COD = :cod", {"cod": cod})
    db.connection.commit()

    article = scalar(db, "SELECT COD1 FROM YSEO_DICT "
                         "WHERE SECTION = 'ARTICLE' AND CODE = :c",
                     {"c": ARTICLE_CODE})
    channel = scalar(db, "SELECT COD1 FROM YSEO_DICT "
                         "WHERE SECTION = 'CHANNEL' AND CODE = :c",
                     {"c": CHANNEL_CODE})

    return {"site": cod, "article": article, "channel": channel}


def set_mode(db, mode: str) -> None:
    run(db, "UPDATE YSEO_SETUP SET PARAM_VALUE = :m "
            "WHERE PARAM_CODE = 'BUDGET_OVERRUN_MODE'", {"m": mode})
    db.connection.commit()


def insert_spend(db, ctx, ext_id, suma, valuta="MDL"):
    return run(db,
               "INSERT INTO YSEO_SPEND_FACT (EXT_ID, SITE_COD, CHANNEL_COD1, "
               "ARTICLE_COD1, SPEND_DATE, PERIOD, SUMA, VALUTA, SOURCE) "
               "VALUES (:ext_id, :site, :channel, :article, "
               "TO_DATE(:day, 'YYYY-MM-DD'), :period, :suma, :valuta, 'MANUAL')",
               {"ext_id": ext_id, "site": ctx["site"], "channel": ctx["channel"],
                "article": ctx["article"], "day": SPEND_DATE, "period": PERIOD,
                "suma": suma, "valuta": valuta})


# ── проверки ─────────────────────────────────────────────────────────

def check_plan_and_spend(db, ctx) -> None:
    """План записывается пакетом, расход в пределах плана проходит."""
    ok, message = run(db,
        "BEGIN PK_SEO_BUDGET.PLAN_UPSERT(:period, :article, :channel, :site, "
        "1000, 'MDL', 'smoke', 'smoke'); END;",
        {"period": PERIOD, "article": ctx["article"],
         "channel": ctx["channel"], "site": ctx["site"]})
    db.connection.commit()
    report("план записывается через PK_SEO_BUDGET.PLAN_UPSERT", ok, message)

    plan = scalar(db, "SELECT PLAN_SUMA FROM YSEO_BUDGET_PLAN "
                      "WHERE PERIOD = :p AND SITE_COD = :s",
                  {"p": PERIOD, "s": ctx["site"]})
    report("план виден в таблице", plan == 1000, f"plan={plan}")

    # Повторный вызов обязан обновить строку, а не создать вторую.
    run(db, "BEGIN PK_SEO_BUDGET.PLAN_UPSERT(:period, :article, :channel, "
            ":site, 1000, 'MDL', 'smoke again', 'smoke'); END;",
        {"period": PERIOD, "article": ctx["article"],
         "channel": ctx["channel"], "site": ctx["site"]})
    db.connection.commit()
    count = scalar(db, "SELECT COUNT(*) FROM YSEO_BUDGET_PLAN "
                       "WHERE PERIOD = :p AND SITE_COD = :s",
                   {"p": PERIOD, "s": ctx["site"]})
    report("повторный PLAN_UPSERT не создаёт вторую строку", count == 1,
           f"строк={count}")

    ok, message = insert_spend(db, ctx, "smoke-within-plan", 400)
    db.connection.commit()
    report("расход в пределах плана проходит", ok, message)

    flag = scalar(db, "SELECT IS_OVERBUDGET FROM YSEO_SPEND_FACT "
                      "WHERE EXT_ID = 'smoke-within-plan'")
    report("расход в пределах плана не помечен перерасходом", flag == 0,
           f"флаг={flag}")

    period = scalar(db, "SELECT PERIOD FROM YSEO_SPEND_FACT "
                        "WHERE EXT_ID = 'smoke-within-plan'")
    report("период проставлен триггером из даты", period == PERIOD,
           f"период={period}")


def check_overrun_blocked(db, ctx) -> None:
    """В режиме BLOCK расход сверх плана отклоняется."""
    set_mode(db, "BLOCK")
    ok, message = insert_spend(db, ctx, "smoke-over-block", 5000)
    db.connection.commit()

    report("режим BLOCK отклоняет расход сверх плана", not ok, message[:120])
    report("сообщение отказа двуязычное",
           (not ok) and "RO:" in message and "EN:" in message, message[:120])

    exists = scalar(db, "SELECT COUNT(*) FROM YSEO_SPEND_FACT "
                        "WHERE EXT_ID = 'smoke-over-block'")
    report("отклонённая строка не осталась в таблице", exists == 0,
           f"строк={exists}")


def check_overrun_warned(db, ctx) -> None:
    """В режиме WARN тот же расход записывается с флагом перерасхода."""
    set_mode(db, "WARN")
    ok, message = insert_spend(db, ctx, "smoke-over-warn", 5000)
    db.connection.commit()
    report("режим WARN пропускает расход сверх плана", ok, message[:120])

    flag = scalar(db, "SELECT IS_OVERBUDGET FROM YSEO_SPEND_FACT "
                      "WHERE EXT_ID = 'smoke-over-warn'")
    report("расход сверх плана помечен IS_OVERBUDGET", flag == 1, f"флаг={flag}")


def check_import_dedup(db, ctx) -> None:
    """Повторная загрузка той же строки не создаёт дубль."""
    ok, message = insert_spend(db, ctx, "smoke-over-warn", 10)
    db.connection.commit()
    report("повторный EXT_ID отвергается уникальным ключом", not ok,
           message[:120])

    count = scalar(db, "SELECT COUNT(*) FROM YSEO_SPEND_FACT "
                       "WHERE EXT_ID = 'smoke-over-warn'")
    report("строка с таким EXT_ID осталась одна", count == 1, f"строк={count}")


def check_archive_not_delete(db, ctx) -> None:
    """Архивирование вместо удаления, событие в журнале."""
    before = scalar(db, "SELECT COUNT(*) FROM YSEO_EVENT_LOG")

    run(db, "BEGIN PK_SEO_UTIL.LOG_EVENT('SMOKE_ARCHIVE', 'SITE', :cod, "
            "'smoke run', 'smoke'); END;", {"cod": ctx["site"]})
    run(db, "UPDATE YSEO_SITE SET ISARHIV = 1 WHERE COD = :cod",
        {"cod": ctx["site"]})
    db.connection.commit()

    still_here = scalar(db, "SELECT COUNT(*) FROM YSEO_SITE WHERE COD = :cod",
                        {"cod": ctx["site"]})
    flag = scalar(db, "SELECT ISARHIV FROM YSEO_SITE WHERE COD = :cod",
                  {"cod": ctx["site"]})
    after = scalar(db, "SELECT COUNT(*) FROM YSEO_EVENT_LOG")

    report("сайт остался в таблице после архивирования", still_here == 1)
    report("флаг архива выставлен", flag == 1, f"флаг={flag}")
    report("журнал пополнился событием", after > before,
           f"было={before} стало={after}")

    ok, message = run(db, "DELETE FROM YSEO_EVENT_LOG WHERE COD = :c",
                      {"c": scalar(db, "SELECT MAX(COD) FROM YSEO_EVENT_LOG")})
    db.connection.rollback()
    report("журнал защищён от удаления", not ok, message[:120])


def check_views(db, ctx) -> None:
    """Вьюшки дают ожидаемые суммы."""
    rows = query(db,
        "SELECT PLAN_SUMA, FACT_SUMA, REST_SUMA FROM VSEO_BUDGET_PLANFACT "
        "WHERE PERIOD = :p AND SITE_COD = :s", {"p": PERIOD, "s": ctx["site"]})
    if not rows:
        report("VSEO_BUDGET_PLANFACT содержит строку периода", False, "строк нет")
    else:
        row = rows[0]
        report("VSEO_BUDGET_PLANFACT: план 1000", row["plan_suma"] == 1000,
               f"план={row['plan_suma']}")
        report("VSEO_BUDGET_PLANFACT: факт 5400", row["fact_suma"] == 5400,
               f"факт={row['fact_suma']}")
        report("VSEO_BUDGET_PLANFACT: остаток отрицательный",
               row["rest_suma"] < 0, f"остаток={row['rest_suma']}")

    roi_rows = query(db,
        "SELECT SPEND_SUMA, ROI FROM VSEO_CHANNEL_ROI "
        "WHERE PERIOD = :p AND SITE_COD = :s", {"p": PERIOD, "s": ctx["site"]})
    report("VSEO_CHANNEL_ROI отдаёт расход по каналу",
           bool(roi_rows) and roi_rows[0]["spend_suma"] == 5400,
           f"строк={len(roi_rows)}")

    site_rows = query(db, "SELECT DOMAIN FROM VSEO_SITE WHERE COD = :s",
                      {"s": ctx["site"]})
    report("VSEO_SITE отдаёт служебный сайт", bool(site_rows))


CHECKS = (check_plan_and_spend, check_overrun_blocked, check_overrun_warned,
          check_import_dedup, check_archive_not_delete, check_views)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Живой smoke контура SEOForge (пишет в базу)")
    parser.add_argument("--yes", action="store_true",
                        help="подтвердить запись в базу")
    args = parser.parse_args()

    if not args.yes:
        print("Скрипт пишет в базу. Запускайте с --yes, если это то, что нужно.")
        sys.exit(2)

    print(f"SEOForge smoke: сайт {SITE_DOMAIN}, период {PERIOD}\n")

    with DatabaseModel() as db:
        try:
            ctx = prepare(db)
        except RuntimeError as exc:
            print(f"Не удалось подготовить данные: {exc}")
            print("Проверьте, что контур установлен: "
                  "python deploy_oracle_objects.py --only yseo")
            sys.exit(1)

        if ctx["article"] is None or ctx["channel"] is None:
            print("В справочнике нет статьи ADS или канала GOOGLE_ADS — "
                  "не выполнен 116_yseo_dict_seed.sql")
            sys.exit(1)

        for check in CHECKS:
            print(f"\n{check.__doc__.splitlines()[0]}")
            try:
                check(db, ctx)
            except RuntimeError as exc:
                report(check.__name__, False, str(exc)[:160])

        # Возвращаем настройку в состояние по умолчанию.
        set_mode(db, "WARN")

    print(f"\nИтог: пройдено {len(PASSED)}, провалено {len(FAILED)}")
    if FAILED:
        for name in FAILED:
            print(f"  провалено: {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
