#!/usr/bin/env python3
"""Установка исправленного PKG_TICKET_MAIL и чистка старой очереди UN9MAIL_MSG.

Запуск из корня проекта:
    venv/bin/python docs/OTRS/install_fix.py            # установить пакет
    venv/bin/python docs/OTRS/install_fix.py --cleanup  # + пометить старьё STATUS=3
    venv/bin/python docs/OTRS/install_fix.py --rollback # вернуть исходный пакет

Пароль берётся из Keychain: security find-generic-password -s oracle-cloudbd-otrs -w
Разбор проблемы: docs/OTRS/MAIL_QUEUE_DIAGNOSIS.md
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from models.unisim_cassa import _call_worker, _rows  # noqa: E402

DSN = "orange.una.md:4024/cloudbd.world"
FIXED = ROOT / "docs/OTRS/PKG_TICKET_MAIL_BODY_20260825_fixed.sql"
ORIGINAL = ROOT / "docs/OTRS/backup/PKG_TICKET_MAIL_BODY_20260825_original.sql"


def auth():
    pw = subprocess.run(
        ["security", "find-generic-password", "-s", "oracle-cloudbd-otrs", "-w"],
        capture_output=True, text=True, check=True).stdout.strip()
    return {"user": "otrs", "password": pw, "dsn": DSN}


def run(a, sql, label):
    r = _call_worker(a, sql, 5)
    ok = r.get("success")
    print(f"  {label}: {'OK' if ok else str(r.get('message'))[:250]}")
    return ok


def install(a, path):
    sql = path.read_text(encoding="utf-8").rstrip().rstrip("/").rstrip()
    print(f"Ставлю {path.name} ({len(sql.splitlines())} строк) ...")
    run(a, sql, "компиляция")
    for x in _rows(_call_worker(a, "SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM USER_OBJECTS "
                                   "WHERE OBJECT_NAME='PKG_TICKET_MAIL'", 10)):
        print("  ", x)
    errs = _rows(_call_worker(a, "SELECT LINE, TEXT FROM USER_ERRORS WHERE NAME='PKG_TICKET_MAIL' "
                                 "ORDER BY SEQUENCE", 30))
    print("  ошибки компиляции:", errs if errs else "нет")
    return not errs


def cleanup(a):
    """Старые письма переводятся в STATUS=3 (окончательный отказ).

    Строки намеренно НЕ удаляются: остаётся след, что именно не ушло за два
    года. ERR_CODE=-1 помечает эту разовую чистку.
    """
    before = _rows(_call_worker(a, "SELECT COUNT(*) C FROM UN9MAIL_MSG WHERE STATUS=1 "
                                   "AND SENT_DATE < SYSDATE-30", 5))
    print(f"Помечаю архивом писем: {before[0]['c'] if before else '?'}")
    run(a, "UPDATE UN9MAIL_MSG SET STATUS=3, ERR_CODE=-1, "
           "ERR_MSG='arhivat 25.08.2026: fix buffer VARCHAR2(4000)' "
           "WHERE STATUS=1 AND SENT_DATE < SYSDATE-30", "пометка архивом")
    run(a, "COMMIT", "commit")
    for x in _rows(_call_worker(a, "SELECT STATUS, COUNT(*) C FROM UN9MAIL_MSG "
                                   "GROUP BY STATUS ORDER BY STATUS", 10)):
        print("  ", x)


if __name__ == "__main__":
    a = auth()
    if "--rollback" in sys.argv:
        install(a, ORIGINAL)
    else:
        if install(a, FIXED) and "--cleanup" in sys.argv:
            cleanup(a)
