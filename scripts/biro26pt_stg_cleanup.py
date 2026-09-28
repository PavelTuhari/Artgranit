#!/usr/bin/env python3
"""RO: Curatarea periodica a staging-ului de import BIRO26PT (cerinta
echipei de import — RAPORT_IMPORT_SET9_SCOPE_FIX.md §2): incarcarile mai
vechi de 30 de zile se sterg din BIRO26PT_STG / BIRO26PT_RAW /
BIRO26PT_RAW_BLOB (+ MAP/HEADER). Staging-ul crestea la nesfirsit
(616k rinduri / 204 incarcari) — desi dupa fixul lor un import vede DOAR
incarcarea proprie (view BIRO26PT_STG_CUR), gunoiul ocupa spatiu degeaba.
EN: periodic BIRO26PT staging cleanup — drop loads older than 30 days.

Rulare (cron, duminica 04:30):
  30 4 * * 0  cd /home/ubuntu/artgranit && ./venv/bin/python scripts/biro26pt_stg_cleanup.py >> /home/ubuntu/backups_site/stg_cleanup.log 2>&1
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

APP_DIR = "/home/ubuntu/artgranit"
KEEP_DAYS = 30


def _load_env():
    p = os.path.join(APP_DIR, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    _load_env()
    os.chdir(APP_DIR)
    sys.path.insert(0, APP_DIR)
    from models.biro26_db import Biro26DB
    db = Biro26DB()
    print(f"== {datetime.now():%d.%m.%Y %H:%M} stg cleanup (> {KEEP_DAYS} zile)")
    old = ("(SELECT load_id FROM biro26pt_file "
           f" WHERE loaded_at < SYSDATE - {KEEP_DAYS})")
    # RO: ordinea: copiii intii, fisierul la urma
    for tbl in ("biro26pt_stg", "biro26pt_raw_blob", "biro26pt_raw",
                "biro26pt_map", "biro26pt_header", "biro26pt_log"):
        r = db.execute_dml(f"DELETE FROM {tbl} WHERE load_id IN {old}")
        print(f"  {tbl}: " + (f"{r.get('rowcount')} sterse" if r.get("success")
                              else "ERR " + str(r.get("message"))[:200]))
    r = db.execute_dml(
        f"DELETE FROM biro26pt_file WHERE loaded_at < SYSDATE - {KEEP_DAYS}")
    print("  biro26pt_file: " + (f"{r.get('rowcount')} sterse"
                                 if r.get("success")
                                 else "ERR " + str(r.get("message"))[:200]))
    left = db.execute_query("SELECT COUNT(*) c FROM biro26pt_stg").get("data")
    print("  ramase in stg:", left)


if __name__ == "__main__":
    main()
