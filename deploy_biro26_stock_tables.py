#!/usr/bin/env python3
"""Deploy Biro26 stock-balance cache tables (officeplus, Oracle 11g).

Idempotent: skips if YBIRO_STOCK_CALC already exists. Runs the DDL from
sql/biro26/03_biro26_stock_tables.sql via the thick-mode subprocess worker
(no sqlplus required).

Usage: ./venv/bin/python deploy_biro26_stock_tables.py
"""
from __future__ import annotations
import sys
from models.biro26_db import Biro26DB

DDL_TABLE_CALC = """
CREATE TABLE YBIRO_STOCK_CALC (
  id           NUMBER PRIMARY KEY,
  run_at       TIMESTAMP DEFAULT SYSTIMESTAMP,
  data_doc     DATE,
  dep_filter   VARCHAR2(60),
  cont_filter  VARCHAR2(60),
  pfilt        VARCHAR2(30),
  src_table    VARCHAR2(100),
  row_count    NUMBER DEFAULT 0,
  is_latest    VARCHAR2(1) DEFAULT '1',
  status       VARCHAR2(10) DEFAULT 'OK',
  err_text     VARCHAR2(2000),
  created_by   VARCHAR2(60) DEFAULT USER
)"""

DDL_SEQ = "CREATE SEQUENCE YBIRO_STOCK_CALC_SEQ START WITH 1 INCREMENT BY 1 NOCACHE"

DDL_TRG = """
CREATE OR REPLACE TRIGGER YBIRO_STOCK_CALC_BI
  BEFORE INSERT ON YBIRO_STOCK_CALC FOR EACH ROW WHEN (NEW.id IS NULL)
BEGIN
  SELECT YBIRO_STOCK_CALC_SEQ.NEXTVAL INTO :NEW.id FROM dual;
END;"""

DDL_TABLE_ITEM = """
CREATE TABLE YBIRO_STOCK_CALC_ITEM (
  calc_id  NUMBER NOT NULL,
  sc       NUMBER NOT NULL,
  dep      NUMBER,
  cant     NUMBER,
  cant1    NUMBER,
  CONSTRAINT pk_ybiro_stock_item PRIMARY KEY (calc_id, sc, dep),
  CONSTRAINT fk_ybiro_stock_item_calc FOREIGN KEY (calc_id)
    REFERENCES YBIRO_STOCK_CALC(id)
)"""

DDL_INDEX = "CREATE INDEX IX_YBIRO_STOCK_ITEM_SC ON YBIRO_STOCK_CALC_ITEM(sc)"


def main() -> int:
    db = Biro26DB()
    ex = db.execute_query(
        "SELECT COUNT(*) FROM all_objects WHERE object_name='YBIRO_STOCK_CALC'")
    if ex["success"] and ex["data"] and ex["data"][0][0] > 0:
        print("YBIRO_STOCK_CALC already exists — nothing to do.")
        return 0

    print("Deploying Biro26 stock-balance cache tables to OfficePlus 11g...")
    steps = [
        ("table YBIRO_STOCK_CALC", DDL_TABLE_CALC, False),
        ("sequence YBIRO_STOCK_CALC_SEQ", DDL_SEQ, False),
        ("trigger YBIRO_STOCK_CALC_BI", DDL_TRG, True),
        ("table YBIRO_STOCK_CALC_ITEM", DDL_TABLE_ITEM, False),
        ("index IX_YBIRO_STOCK_ITEM_SC", DDL_INDEX, False),
    ]
    for label, sql, cap in steps:
        r = db.call_proc(sql) if cap else db.execute_dml(sql)
        ok = r.get("success")
        print(f"  [{'OK ' if ok else 'ERR'}] {label}" + ("" if ok else f" -> {r.get('message')}"))
        if not ok:
            return 1
    print("Done. YBIRO_STOCK_CALC / YBIRO_STOCK_CALC_ITEM ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
