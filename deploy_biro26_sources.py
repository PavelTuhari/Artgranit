#!/usr/bin/env python3
"""Deploy Biro26 source-definition table + verify CREATE VIEW privilege (officeplus 11g).

Idempotent: skips table creation if YBIRO_SRC_DEF exists. Always probes CREATE VIEW
first (Stage 3 materializes SELECTs as views and cannot work without it).

Usage: ./venv/bin/python deploy_biro26_sources.py
"""
from __future__ import annotations
import sys
from models.biro26_db import Biro26DB

DDL_TABLE = """CREATE TABLE YBIRO_SRC_DEF (
  id NUMBER PRIMARY KEY, name VARCHAR2(60) NOT NULL, select_sql CLOB,
  view_name VARCHAR2(40), md_path VARCHAR2(200),
  created_at TIMESTAMP DEFAULT SYSTIMESTAMP, created_by VARCHAR2(60) DEFAULT USER,
  CONSTRAINT uq_ybiro_src_def_name UNIQUE (name))"""
DDL_SEQ = "CREATE SEQUENCE YBIRO_SRC_DEF_SEQ START WITH 1 INCREMENT BY 1 NOCACHE"
DDL_TRG = """CREATE OR REPLACE TRIGGER YBIRO_SRC_DEF_BI
  BEFORE INSERT ON YBIRO_SRC_DEF FOR EACH ROW WHEN (NEW.id IS NULL)
BEGIN SELECT YBIRO_SRC_DEF_SEQ.NEXTVAL INTO :NEW.id FROM dual; END;"""


def main() -> int:
    db = Biro26DB()

    # 1) privilege probe — Stage 3 needs CREATE VIEW
    pv = db.execute_dml("CREATE VIEW V_BIRO26_SRC__PRIV AS SELECT 1 X FROM dual")
    if pv.get("success"):
        db.execute_dml("DROP VIEW V_BIRO26_SRC__PRIV")
        print("[priv] CREATE VIEW: OK")
    else:
        print("[priv] CREATE VIEW FAILED:", pv.get("message"))
        print("       -> grant CREATE VIEW to officeplus before using SELECT sources.")
        return 1

    # 2) table (idempotent)
    ex = db.execute_query(
        "SELECT COUNT(*) FROM all_objects WHERE object_name='YBIRO_SRC_DEF'")
    if ex["success"] and ex["data"] and ex["data"][0][0] > 0:
        print("YBIRO_SRC_DEF already exists — nothing to do.")
        return 0

    for label, sql, cap in [("table", DDL_TABLE, False),
                            ("sequence", DDL_SEQ, False),
                            ("trigger", DDL_TRG, True)]:
        r = db.call_proc(sql + ";") if cap else db.execute_dml(sql)
        ok = r.get("success")
        print(f"  [{'OK ' if ok else 'ERR'}] {label}" + ("" if ok else f" -> {r.get('message')}"))
        if not ok:
            return 1
    print("Done. YBIRO_SRC_DEF ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
