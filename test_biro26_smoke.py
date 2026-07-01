#!/usr/bin/env python3
"""Biro26 — live smoke test against OfficePlus (Oracle 11g, via subprocess worker).

Verifies: connection works, required objects exist, YBIRO_Import_Marfa is VALID,
and the app-owned mapping tables (if deployed) are reachable.

Usage: ./venv/bin/python test_biro26_smoke.py
"""
from __future__ import annotations
import sys
from models.biro26_db import Biro26DB

REQUIRED = [
    "BIRO26_GOODS", "TMS_UNIVERS", "TMS_MPT", "TMS_UM",
    "VPR01M_GROUPS", "VPR1D_PRDATE", "TPR1D_PERPRLIST", "VTPR1D_PERPRLIST",
    "TMS_ORG", "TMS_SYSGRP",
]


def main() -> int:
    db = Biro26DB()
    tc = db.test_connection()
    print(f"[conn] success={tc['success']} version={tc.get('version')}")
    if not tc["success"]:
        print(f"  ERROR: {tc.get('error')}")
        return 1

    fails = []
    for name in REQUIRED:
        r = db.execute_query(
            "SELECT COUNT(*) FROM all_objects WHERE object_name=:n "
            "AND object_type IN ('TABLE','VIEW')", {"n": name})
        ok = bool(r["data"] and r["data"][0][0] > 0)
        print(f"[obj ] {name:22s} {'OK' if ok else 'MISSING'}")
        if not ok:
            fails.append(name)

    r = db.execute_query(
        "SELECT status FROM all_objects WHERE object_name='YBIRO_IMPORT_MARFA' "
        "AND object_type='PACKAGE'")
    status = r["data"][0][0] if r["data"] else "MISSING"
    print(f"[pkg ] YBIRO_IMPORT_MARFA   {status}")
    if status != "VALID":
        fails.append("YBIRO_IMPORT_MARFA")

    r = db.execute_query("SELECT COUNT(*) FROM BIRO26_GOODS")
    if r["success"]:
        print(f"[data] BIRO26_GOODS rows = {r['data'][0][0]}")

    # app-owned mapping tables are optional until Task 4 DDL is run
    r = db.execute_query(
        "SELECT COUNT(*) FROM all_objects WHERE object_name IN "
        "('YBIRO_MAP_PROFILE','YBIRO_MAP_PARAM')")
    n = r["data"][0][0] if r["success"] and r["data"] else 0
    print(f"[app ] mapping tables present: {n}/2 "
          f"({'ready' if n == 2 else 'run sql/biro26/01_biro26_app_tables.sql'})")

    if fails:
        print(f"\nFAILED objects: {fails}")
        return 1
    print("\nAll required ERP objects present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
