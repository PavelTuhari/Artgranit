#!/usr/bin/env python3
"""Поиск того же дефекта во всех схемах БД cloudbd.

Исходники чужих пакетов под haruzdar2018 не видны (нет EXECUTE), поэтому
дефект ищется по следу: сколько писем зависло в очереди UN9MAIL_MSG со
STATUS=1 и как давно. Там, где рассылка идёт через send_email_api_php с
приёмником varchar2(4000), письма крупнее 4000 байт теряются молча —
разбор в docs/OTRS/MAIL_QUEUE_DIAGNOSIS.md.

    venv/bin/python docs/OTRS/scan_schemas.py

Только чтение, ничего не меняет.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from models.unisim_cassa import _call_worker, _rows  # noqa: E402

DSN = "orange.una.md:4024/cloudbd.world"


def auth():
    pw = subprocess.run(["security", "find-generic-password", "-a", "haruzdar2018",
                         "-s", "oracle-cloudbd-haruzdar2018", "-w"],
                        capture_output=True, text=True, check=True).stdout.strip()
    return {"user": "haruzdar2018", "password": pw, "dsn": DSN}


if __name__ == "__main__":
    a = auth()
    total = _rows(_call_worker(a,
        "SELECT COUNT(*) C FROM ALL_TABLES WHERE TABLE_NAME='UN9MAIL_MSG'", 120))
    # в части схем таблица старой раскладки — без STATUS/SENT_DATE; берём только
    # те, где очередь устроена так же, как в OTRS
    owners = [x["owner"] for x in _rows(_call_worker(a,
        "SELECT OWNER FROM ALL_TAB_COLUMNS WHERE TABLE_NAME='UN9MAIL_MSG' "
        "AND COLUMN_NAME IN ('STATUS','SENT_DATE','TEXT') "
        "GROUP BY OWNER HAVING COUNT(DISTINCT COLUMN_NAME)=3 ORDER BY OWNER", 120))]
    print(f"схем с очередью UN9MAIL_MSG: {total[0]['c'] if total else '?'}, "
          f"из них с современной раскладкой: {len(owners)}\n")

    # один запрос вместо 150 подключений: воркер поднимает соединение на вызов
    parts = [f"SELECT '{o}' OWNER, COUNT(*) STUCK, "
             f"SUM(CASE WHEN DBMS_LOB.GETLENGTH(TEXT) >= 4000 THEN 1 ELSE 0 END) BIG, "
             f"TO_CHAR(MIN(SENT_DATE),'YYYY-MM-DD') OT, TO_CHAR(MAX(SENT_DATE),'YYYY-MM-DD') DD "
             f"FROM {o}.UN9MAIL_MSG WHERE STATUS=1" for o in owners]
    rows, chunk = [], 25
    for i in range(0, len(parts), chunk):
        sql = " UNION ALL ".join(parts[i:i + chunk])
        r = _call_worker(a, sql, 300)
        if r.get("success"):
            rows += _rows(r)
        else:
            print(f"  часть {i // chunk + 1}: {str(r.get('message'))[:120]}")

    rows = [x for x in rows if (x["stuck"] or 0) > 0]
    rows.sort(key=lambda x: -(x["stuck"] or 0))
    print(f"{'СХЕМА':<24}{'ЗАСТРЯЛО':>9}{'из них >4КБ':>13}   ПЕРИОД")
    for x in rows:
        print(f"{x['owner']:<24}{x['stuck']:>9}{x['big']:>13}   {x['ot']} … {x['dd']}")
    print(f"\nзатронуто схем: {len(rows)}, писем всего: {sum(x['stuck'] for x in rows)}, "
          f"из них крупнее 4 КБ (гарантированно из-за буфера): {sum(x['big'] or 0 for x in rows)}")
