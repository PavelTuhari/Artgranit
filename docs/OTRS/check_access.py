#!/usr/bin/env python3
"""Проверка доступа к задетым схемам и наличия в них дефектной процедуры.

Пароли берутся из Keychain (запись oracle-cloudbd-<схема>); если записи нет,
пробуется соглашение «пароль = имя схемы», которое подтвердилось на TICKETS.

    venv/bin/python docs/OTRS/check_access.py

Только чтение: логин + просмотр USER_SOURCE. Ничего не меняет.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from models.unisim_cassa import _call_worker, _rows  # noqa: E402

DSN = "orange.una.md:4024/cloudbd.world"
# схемы с застрявшими письмами, по данным scan_schemas.py
SCHEMAS = ["UNI", "GARABTA", "DORIMAX", "FLORENTINO", "LACOSTE", "LEALEA",
           "NLCOLLECTION", "SORINST", "GARAA"]


def keychain(name):
    r = subprocess.run(["security", "find-generic-password", "-s", f"oracle-cloudbd-{name}", "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def try_login(user):
    for pw in filter(None, [keychain(user.lower()), user.lower(), user]):
        r = _call_worker({"user": user.lower(), "password": pw, "dsn": DSN},
                         "SELECT USER AS U FROM DUAL", 60)
        if r.get("success"):
            return pw
    return None


if __name__ == "__main__":
    for s in SCHEMAS:
        pw = try_login(s)
        if not pw:
            print(f"{s:<14} вход: НЕТ (нужен пароль)")
            continue
        a = {"user": s.lower(), "password": pw, "dsn": DSN}
        pkgs = _rows(_call_worker(a,
            "SELECT NAME, TYPE FROM USER_SOURCE WHERE LOWER(TEXT) LIKE '%send_email_api_php%' "
            "AND TYPE='PACKAGE BODY' GROUP BY NAME, TYPE", 60))
        bad = _rows(_call_worker(a,
            "SELECT DISTINCT NAME FROM USER_SOURCE WHERE TYPE='PACKAGE BODY' "
            "AND LOWER(REPLACE(TEXT,' ','')) LIKE '%v_req_resultvarchar2(4000)%'", 60))
        names = ", ".join(x["name"] for x in pkgs) or "процедуры нет"
        flag = "ДЕФЕКТ: " + ", ".join(x["name"] for x in bad) if bad else "буфер в порядке"
        print(f"{s:<14} вход: OK | {names} | {flag}")
