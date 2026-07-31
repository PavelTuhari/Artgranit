#!/usr/bin/env python3
"""Deploy TMS_CREDITE_* to both Oracle databases (idempotent).

ADB    — main project (thin mode + wallet), models/database.py
Biro26 — OfficePlus Oracle 11g (thick subprocess worker), models/biro26_db.py

Steps per target:
  1. create tables/sequences/triggers that do not exist yet
  2. migrate data from YBIRO_CREDIT_* (if present and not migrated yet)
  3. seed TMS_CREDITE_PROVIDER from data/*.json + .env (if empty)
  4. rename YBIRO_CREDIT_* -> *_OLD — ONLY with --rename-legacy (off by default:
     remote still reads YBIRO_CREDIT_* until the new code ships, see Task 10)

Usage: ./venv/bin/python deploy_credite_oracle.py --target both
       ./venv/bin/python deploy_credite_oracle.py --target both --rename-legacy
"""
from __future__ import annotations

import argparse
import sys
from typing import List

from models.credite_settings import AdbBackend, Biro26Backend, CrediteBackend, PROVIDER_DEFS

TABLES = ["TMS_CREDITE_PROVIDER", "TMS_CREDITE_PROVIDER_PARAM", "TMS_CREDITE_ORG",
          "TMS_CREDITE_PLAN", "TMS_CREDITE_REQ", "TMS_CREDITE_REQ_EVENT"]

DDL_PATH = {"adb": "sql/50_credite_tables.sql", "biro26": "sql/biro26/12_tms_credite.sql"}


def _split_ddl(text: str) -> List[str]:
    """Split the DDL file into statements.

    PL/SQL trigger bodies are terminated by a lone '/' line; plain DDL by ';'.
    """
    out, buf, in_plsql = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("--") and not buf:
            continue
        if s == "/":
            if buf:
                out.append("\n".join(buf).strip())
                buf, in_plsql = [], False
            continue
        if s.upper().startswith("CREATE OR REPLACE TRIGGER"):
            in_plsql = True
        buf.append(line)
        if not in_plsql and s.endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            buf = []
    if buf and "\n".join(buf).strip():
        out.append("\n".join(buf).strip().rstrip(";").strip())
    return [s for s in out if s]


def _exists(be: CrediteBackend, name: str) -> bool:
    rows = be.query("SELECT COUNT(*) CNT FROM USER_OBJECTS WHERE OBJECT_NAME = :n",
                    {"n": name.upper()})
    return bool(rows) and int(rows[0]["cnt"]) > 0


def create_objects(be: CrediteBackend, ddl_file: str) -> int:
    with open(ddl_file, encoding="utf-8") as f:
        stmts = _split_ddl(f.read())
    created = 0
    for stmt in stmts:
        head = " ".join(stmt.split()[:4]).upper()
        try:
            be.dml(stmt)
            created += 1
            print(f"  + {head}")
        except Exception as e:
            msg = str(e)
            # ORA-00955 name already used, ORA-02260/01408 index/constraint exists
            if "ORA-00955" in msg or "ORA-01408" in msg or "ORA-02275" in msg:
                print(f"  = {head} (уже есть)")
            else:
                print(f"  ! {head}: {msg[:200]}")
                raise
    return created


def migrate_legacy(be: CrediteBackend) -> None:
    """Copy YBIRO_CREDIT_* into TMS_CREDITE_* preserving IDs. Idempotent."""
    if not _exists(be, "YBIRO_CREDIT_ORG"):
        print("  = YBIRO_CREDIT_ORG отсутствует — миграция не нужна")
        return
    n = be.query("SELECT COUNT(*) CNT FROM TMS_CREDITE_ORG")[0]["cnt"]
    if int(n) > 0:
        print("  = TMS_CREDITE_ORG уже заполнена — миграция пропущена")
        return
    be.dml("INSERT INTO TMS_CREDITE_ORG (ID, NAME, ENABLED, ORG_MODE, API_URL, "
           "LOGO_URL, INFO, ORD) SELECT ID, NAME, ENABLED, ORG_MODE, API_URL, "
           "LOGO_URL, INFO, ORD FROM YBIRO_CREDIT_ORG")
    be.dml("INSERT INTO TMS_CREDITE_PLAN (ID, ORG_ID, NAME, MONTHS_MIN, MONTHS_MAX, "
           "AMOUNT_MIN, AMOUNT_MAX, MARKUP_PCT, ANNUAL_PCT, MONTHLY_FEE_PCT, "
           "ISSUE_FEE, AVANS_MIN_PCT, ENABLED, INFO) SELECT ID, ORG_ID, NAME, "
           "MONTHS_MIN, MONTHS_MAX, AMOUNT_MIN, AMOUNT_MAX, MARKUP_PCT, ANNUAL_PCT, "
           "MONTHLY_FEE_PCT, ISSUE_FEE, AVANS_MIN_PCT, ENABLED, INFO "
           "FROM YBIRO_CREDIT_PLAN")
    if _exists(be, "YBIRO_CREDIT_REQ"):
        be.dml("INSERT INTO TMS_CREDITE_REQ (ID, ORG_ID, PLAN_ID, MONTHS, PRODUCT_COD, "
               "PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, CLIENT_NAME, PHONE, "
               "STATUS, CREATED) SELECT ID, ORG_ID, PLAN_ID, MONTHS, PRODUCT_COD, "
               "PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, CLIENT_NAME, PHONE, "
               "STATUS, CREATED FROM YBIRO_CREDIT_REQ")
    for tab in ("ORG", "PLAN", "REQ"):
        seq = f"TMS_CREDITE_{tab}_SEQ"
        target = int(be.query(f"SELECT NVL(MAX(ID), 0) + 1 NX FROM TMS_CREDITE_{tab}")[0]["nx"])
        cur = int(be.query(f"SELECT {seq}.NEXTVAL NV FROM dual")[0]["nv"])
        delta = target - cur - 1
        if delta > 0:
            # RO: mutam secventa fara a o sterge — DROP+CREATE nu e atomic
            be.dml(f"ALTER SEQUENCE {seq} INCREMENT BY {delta}")
            be.query(f"SELECT {seq}.NEXTVAL NV FROM dual")
            be.dml(f"ALTER SEQUENCE {seq} INCREMENT BY 1")
        print(f"  ~ {seq} -> next {max(target, cur + 1)}")
    print("  + данные перенесены из YBIRO_CREDIT_*")


def resync_legacy(be: CrediteBackend) -> None:
    """Docoreste TMS_CREDITE_REQ cu rindurile noi din YBIRO_CREDIT_REQ.

    RO: migrate_legacy() ruleaza o singura data (sare daca TMS_CREDITE_REQ nu
    e goala). Intre aplicarea DDL si deploy-ul codului nou pe server, codul
    vechi de acolo poate continua sa scrie in YBIRO_CREDIT_REQ — acele rinduri
    nu ajung niciodata in TMS_CREDITE_REQ. resync_legacy() transfera DOAR
    rindurile cu ID > MAX(ID) curent din TMS_CREDITE_REQ, fara sa atinga cele
    deja migrate (evita coliziuni de PK). Idempotent — poate rula de mai multe
    ori; daca nu sint rinduri noi, nu face nimic.
    EN: one-shot migrate_legacy() only ever runs once; this catches rows the
    still-running legacy code wrote to YBIRO_CREDIT_REQ afterwards, copying
    only ID > current MAX(ID) in TMS_CREDITE_REQ (no PK collisions). Safe to
    re-run; no-op when there is nothing new."""
    if not _exists(be, "YBIRO_CREDIT_REQ"):
        print("  = YBIRO_CREDIT_REQ отсутствует — resync не нужен")
        return
    max_id = int(be.query("SELECT NVL(MAX(ID), 0) CNT FROM TMS_CREDITE_REQ")[0]["cnt"])
    cnt_rows = be.query(
        "SELECT COUNT(*) CNT FROM YBIRO_CREDIT_REQ WHERE ID > :m", {"m": max_id})
    n = int(cnt_rows[0]["cnt"]) if cnt_rows else 0
    if n == 0:
        print(f"  = новых строк в YBIRO_CREDIT_REQ (ID > {max_id}) нет — resync не нужен")
        return
    be.dml(
        "INSERT INTO TMS_CREDITE_REQ (ID, ORG_ID, PLAN_ID, MONTHS, PRODUCT_COD, "
        "PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, CLIENT_NAME, PHONE, "
        "STATUS, CREATED) SELECT ID, ORG_ID, PLAN_ID, MONTHS, PRODUCT_COD, "
        "PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, CLIENT_NAME, PHONE, "
        "STATUS, CREATED FROM YBIRO_CREDIT_REQ WHERE ID > :m", {"m": max_id})
    seq = "TMS_CREDITE_REQ_SEQ"
    target = int(be.query("SELECT NVL(MAX(ID), 0) + 1 NX FROM TMS_CREDITE_REQ")[0]["nx"])
    cur = int(be.query(f"SELECT {seq}.NEXTVAL NV FROM dual")[0]["nv"])
    delta = target - cur - 1
    if delta > 0:
        # RO: mutam secventa fara a o sterge — DROP+CREATE nu e atomic
        be.dml(f"ALTER SEQUENCE {seq} INCREMENT BY {delta}")
        be.query(f"SELECT {seq}.NEXTVAL NV FROM dual")
        be.dml(f"ALTER SEQUENCE {seq} INCREMENT BY 1")
    print(f"  + resync: перенесено {n} новых строк из YBIRO_CREDIT_REQ (ID > {max_id})")
    print(f"  ~ {seq} -> next {max(target, cur + 1)}")


def rename_legacy(be: CrediteBackend) -> None:
    for tab in ("YBIRO_CREDIT_ORG", "YBIRO_CREDIT_PLAN", "YBIRO_CREDIT_REQ"):
        if _exists(be, tab) and not _exists(be, tab + "_OLD"):
            be.dml(f"RENAME {tab} TO {tab}_OLD")
            print(f"  ~ {tab} -> {tab}_OLD")


def seed_providers(be: CrediteBackend) -> None:
    """Seed TMS_CREDITE_PROVIDER from data/*.json (приоритет) с фолбэком на
    .env (Config.*) — once."""
    from config import Config, _load_easycredit_overrides, _load_iute_overrides

    ec_over = _load_easycredit_overrides()
    iute_over = _load_iute_overrides()
    src = {
        "easycredit": {
            "env": ec_over.get("env") or Config.easycredit_env(),
            "base_url": ec_over.get("base_url") or Config.easycredit_base_url(),
            "params": {"api_user": ec_over.get("api_user")
                                   or Config.easycredit_api_user(),
                       "api_password": ec_over.get("api_password")
                                      or Config.easycredit_api_password()},
        },
        "iute": {
            "env": iute_over.get("env") or Config.iute_env(),
            "base_url": iute_over.get("base_url") or Config.iute_base_url(),
            "params": {"api_key": iute_over.get("api_key")
                                  or Config.iute_api_key(),
                       "pos_identifier": iute_over.get("pos_identifier")
                                        or Config.iute_pos_identifier(),
                       "salesman_identifier": iute_over.get("salesman_identifier")
                                              or Config.iute_salesman_identifier()},
        },
    }
    for code, spec in PROVIDER_DEFS.items():
        rows = be.query("SELECT ID FROM TMS_CREDITE_PROVIDER WHERE CODE = :c", {"c": code})
        if rows:
            print(f"  = провайдер {code} уже есть")
            continue
        s = src[code]
        be.dml("INSERT INTO TMS_CREDITE_PROVIDER (CODE, NAME, ENABLED, ENV, BASE_URL, "
               "ICON, COLOR, ORD) VALUES (:c, :n, '0', :e, :b, :i, :col, :o)",
               {"c": code, "n": spec["name"], "e": s["env"], "b": s["base_url"],
                "i": spec["icon"], "col": spec["color"], "o": spec["ord"]})
        pid = int(be.query("SELECT ID FROM TMS_CREDITE_PROVIDER WHERE CODE = :c",
                           {"c": code})[0]["id"])
        for pname, secret in spec["params"]:
            be.dml("INSERT INTO TMS_CREDITE_PROVIDER_PARAM (PROVIDER_ID, PARAM_NAME, "
                   "PARAM_VALUE, IS_SECRET) VALUES (:p, :n, :v, :s)",
                   {"p": pid, "n": pname, "v": s["params"].get(pname) or None,
                    "s": "1" if secret else "0"})
        print(f"  + провайдер {code} создан (ENABLED='0')")


def run(target: str, rename: bool = False, resync: bool = False) -> int:
    be: CrediteBackend = AdbBackend() if target == "adb" else Biro26Backend()
    print(f"\n=== {target} ===")
    try:
        create_objects(be, DDL_PATH[target])
        migrate_legacy(be)
        if resync:
            resync_legacy(be)
        seed_providers(be)
        if rename:
            rename_legacy(be)
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1
    missing = [t for t in TABLES if not _exists(be, t)]
    if missing:
        print(f"  FAIL: отсутствуют объекты {missing}")
        return 1
    print(f"  OK: все {len(TABLES)} таблиц на месте")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["adb", "biro26", "both"], default="both")
    ap.add_argument("--rename-legacy", action="store_true",
                    help="переименовать YBIRO_CREDIT_* -> *_OLD (отложено до Task 10, "
                         "пока remote-приложение читает старые таблицы)")
    ap.add_argument("--resync-legacy", action="store_true",
                    help="перенести из YBIRO_CREDIT_REQ только строки с "
                         "ID > MAX(ID) из TMS_CREDITE_REQ (по умолчанию выключено; "
                         "нужно, если старый код дописал в YBIRO_CREDIT_REQ уже "
                         "после однократной migrate_legacy() — идемпотентно, "
                         "не зависит от --rename-legacy)")
    a = ap.parse_args()
    targets = ["adb", "biro26"] if a.target == "both" else [a.target]
    return max(run(t, rename=a.rename_legacy, resync=a.resync_legacy) for t in targets)


if __name__ == "__main__":
    sys.exit(main())
