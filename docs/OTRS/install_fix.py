#!/usr/bin/env python3
"""Установка исправленного отправителя почты и чистка очереди UN9MAIL_MSG.

Чинится процедура send_email_api_php в двух схемах БД cloudbd:
  OTRS    -> PKG_TICKET_MAIL   (дневные отчёты «Raport de lucru zilnic»)
  TICKETS -> PKG_TICKETS_MAIL  (тот же код, параметр schema=tickets)

Запуск из корня проекта:
    venv/bin/python docs/OTRS/install_fix.py                  # обе схемы
    venv/bin/python docs/OTRS/install_fix.py --only otrs      # одна схема
    venv/bin/python docs/OTRS/install_fix.py --cleanup        # + архив старья
    venv/bin/python docs/OTRS/install_fix.py --rollback       # вернуть исходники

Пароли берутся из Keychain (записаны 25.08.2026):
    security find-generic-password -s oracle-cloudbd-otrs -w
    security find-generic-password -s oracle-cloudbd-tickets -w

Разбор проблемы: docs/OTRS/MAIL_QUEUE_DIAGNOSIS.md
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from models.unisim_cassa import _call_worker, _rows  # noqa: E402

DSN = "orange.una.md:4024/cloudbd.world"
DOCS = ROOT / "docs/OTRS"

TARGETS = {
    "otrs": {
        "user": "otrs",
        "keychain": "oracle-cloudbd-otrs",
        "package": "PKG_TICKET_MAIL",
        "fixed": DOCS / "PKG_TICKET_MAIL_BODY_20260825_fixed.sql",
        "original": DOCS / "backup/PKG_TICKET_MAIL_BODY_20260825_original.sql",
    },
    "tickets": {
        "user": "tickets",
        "keychain": "oracle-cloudbd-tickets",
        "package": "PKG_TICKETS_MAIL",
        "fixed": DOCS / "PKG_TICKETS_MAIL_BODY_20260825_fixed.sql",
        "original": DOCS / "backup/PKG_TICKETS_MAIL_BODY_20260825_original.sql",
    },
}


def auth(t):
    pw = subprocess.run(
        ["security", "find-generic-password", "-s", t["keychain"], "-w"],
        capture_output=True, text=True, check=True).stdout.strip()
    return {"user": t["user"], "password": pw, "dsn": DSN}


def run(a, sql, label):
    r = _call_worker(a, sql, 5)
    ok = r.get("success")
    print(f"    {label}: {'OK' if ok else str(r.get('message'))[:250]}")
    return ok


def install(t, rollback=False):
    path = t["original"] if rollback else t["fixed"]
    a = auth(t)
    sql = path.read_text(encoding="utf-8").rstrip().rstrip("/").rstrip()
    print(f"  {t['package']} <- {path.name} ({len(sql.splitlines())} строк)")
    run(a, sql, "компиляция")
    for x in _rows(_call_worker(a, "SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM USER_OBJECTS "
                                   f"WHERE OBJECT_NAME='{t['package']}'", 10)):
        print("    ", x)
    errs = _rows(_call_worker(a, f"SELECT LINE, TEXT FROM USER_ERRORS WHERE NAME='{t['package']}' "
                                 "ORDER BY SEQUENCE", 30))
    print("    ошибки компиляции:", errs if errs else "нет")
    return not errs


def cleanup(t):
    """Старые письма переводятся в STATUS=3 (окончательный отказ).

    Строки намеренно НЕ удаляются: остаётся след, что именно не ушло.
    ERR_CODE=-1 помечает эту разовую чистку.
    """
    a = auth(t)
    before = _rows(_call_worker(a, "SELECT COUNT(*) C FROM UN9MAIL_MSG "
                                   "WHERE STATUS=1 AND SENT_DATE < SYSDATE-30", 5))
    print(f"  {t['user']}: в архив уходит писем — {before[0]['c'] if before else '?'}")
    # UPDATE и COMMIT обязаны быть в ОДНОМ вызове: воркер на каждый вызов
    # открывает новое соединение, отдельный COMMIT ничего не сохранит.
    run(a, "BEGIN "
           "UPDATE UN9MAIL_MSG SET STATUS=3, ERR_CODE=-1, "
           "ERR_MSG='arhivat 25.08.2026: fix buffer VARCHAR2(4000)' "
           "WHERE STATUS=1 AND SENT_DATE < SYSDATE-30; "
           "COMMIT; END;", "пометка архивом + commit")
    for x in _rows(_call_worker(a, "SELECT STATUS, COUNT(*) C FROM UN9MAIL_MSG "
                                   "GROUP BY STATUS ORDER BY STATUS", 10)):
        print("    ", x)


def retry(t, nrmsg):
    """Прогон одного письма через исправленную процедуру — проверка после установки."""
    a = auth(t)
    proc = f"{t['package']}.SEND_EMAIL_API_PHP"
    print("  до:  ", _rows(_call_worker(a, "SELECT NRMSG, STATUS, SUBSTR(ERR_MSG,1,90) EM "
                                           f"FROM UN9MAIL_MSG WHERE NRMSG={nrmsg}", 5)))
    run(a, f"BEGIN {proc}({nrmsg}); END;", "отправка")
    print("  после:", _rows(_call_worker(a, "SELECT NRMSG, STATUS, ERR_CODE, SUBSTR(ERR_MSG,1,150) EM "
                                            f"FROM UN9MAIL_MSG WHERE NRMSG={nrmsg}", 5)))


if __name__ == "__main__":
    args = sys.argv[1:]
    names = list(TARGETS)
    if "--only" in args:
        names = [args[args.index("--only") + 1]]
    rollback = "--rollback" in args

    for name in names:
        t = TARGETS[name]
        print(f"\n=== схема {name.upper()} ===")
        if "--retry" in args:
            retry(t, int(args[args.index("--retry") + 1]))
            continue
        if "--cleanup-only" in args:
            cleanup(t)
            continue
        ok = install(t, rollback=rollback)
        if ok and not rollback and "--cleanup" in args:
            cleanup(t)
