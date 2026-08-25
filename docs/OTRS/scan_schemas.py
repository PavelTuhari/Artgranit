#!/usr/bin/env python3
"""Поиск того же дефекта во всех схемах БД cloudbd.

Ищет процедуру send_email_api_php и проверяет, объявлен ли в ней приёмник
ответа как varchar2(4000) — то самое место, где теряются письма крупнее
4000 байт (разбор: docs/OTRS/MAIL_QUEUE_DIAGNOSIS.md).

    venv/bin/python docs/OTRS/scan_schemas.py

Читает под haruzdar2018 (ALL_SOURCE виден по ролям), ничего не меняет.
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

    print("=== где вообще есть send_email_api_php ===")
    owners = _rows(_call_worker(a,
        "SELECT OWNER, NAME, TYPE, COUNT(*) C FROM ALL_SOURCE "
        "WHERE LOWER(TEXT) LIKE '%send_email_api_php%' AND TYPE='PACKAGE BODY' "
        "GROUP BY OWNER, NAME, TYPE ORDER BY 1, 2", 180))
    for x in owners:
        print(f"   {x['owner']:<22} {x['name']}")
    print(f"   всего пакетов: {len(owners)}")

    print("\n=== из них с дефектным varchar2(4000) под ответ ===")
    bad = _rows(_call_worker(a,
        "SELECT DISTINCT OWNER, NAME FROM ALL_SOURCE "
        "WHERE TYPE='PACKAGE BODY' AND LOWER(REPLACE(TEXT,' ','')) LIKE '%v_req_resultvarchar2(4000)%' "
        "ORDER BY 1, 2", 180))
    for x in bad:
        print(f"   {x['owner']:<22} {x['name']}")
    print(f"   всего задето: {len(bad)}")

    print("\n=== сколько писем уже потеряно в каждой (STATUS=1) ===")
    for x in bad:
        o = x["owner"]
        r = _rows(_call_worker(a,
            f"SELECT COUNT(*) C, TO_CHAR(MIN(SENT_DATE),'YYYY-MM-DD') OT "
            f"FROM {o}.UN9MAIL_MSG WHERE STATUS=1", 60))
        if r:
            print(f"   {o:<22} {r[0]['c']:>6} писем, с {r[0]['ot']}")
        else:
            print(f"   {o:<22} нет доступа к очереди")
